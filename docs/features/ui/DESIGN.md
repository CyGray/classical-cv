# Study Dashboard & Run Console — Design

**Status:** proposed, not yet built. **Owner:** Kyle (classical-CV track). **Scope:** this
document only — no code changes yet.

## 0. What this is

Two small, separately-deployed apps, not one:

1. **Researcher Dashboard** (`ui/dashboard/`) — a read-only Next.js site deployed on
   Vercel. Shows the current state of the study: what's been run, what the results say,
   the paper's draft, and every figure. For anyone on the team (or an advisor) to open
   and understand "where are we" without reading raw `reports/` output or asking Kyle.
2. **Local Run Console** (`ui/console/`) — a FastAPI app that only ever runs on
   `localhost`, on whichever machine is actually doing the work (this Windows box today,
   the Termux/Android phone per `AGENTS.md` on other days). It wraps `main.py` and the
   scripts under `scripts/`/`src/` so training, evaluation, independence tests, and
   benchmarks can be launched and watched from a browser tab instead of a raw terminal.

**These two do not talk to each other over the network.** The dashboard reads a small
JSON manifest that gets committed to the repo; the console never leaves localhost. A
person, running a script, is the bridge between them (§7).

This split — and everything else in this doc — comes directly from four decisions made
before writing it (recapped in §1), so if something here looks like it's avoiding an
obvious "nicer" architecture, it's because that architecture was considered and rejected
for a stated reason, not missed.

## 1. Decisions already made

| # | Question | Decision |
|---|---|---|
| 1 | How does the web UI trigger `main.py`'s ~38 actions? | **Both, permanently**: a Terminal tab wraps `main.py` itself (full coverage, zero logic duplication); a Dashboard/Forms tab adds guided forms only for the highest-traffic actions, still shelling out to the same scripts. |
| 2 | Do "live detect" actions get in-browser video? | **No, deferred.** They're listed with their logged FPS/recognition stats; no MJPEG/WebSocket video pipe in v1. |
| 3 | What does "visualize the codebase" mean? | **Not a code/dependency graph.** The goal is for *researchers* to understand *results, current study state, the paper, and figures* — not for developers to understand call graphs. This reframes the whole project from a code-viz tool to a research-status dashboard. |
| 4 | How does Vercel hosting relate to running experiments? | **Fully split.** Vercel hosts only the read-only dashboard. Running things happens only on localhost. No tunnel, no live connection between them. |

## 2. The problem this solves

Grounded in what's actually on disk right now, not a hypothetical:

- **The paper lags the data.** `docs/audits/STATE-07-10.md` (2026-07-10) found that
  `docs/PAPER.md` §4.1, §4.3, §4.5, and the abstract still say results are "pending"
  for runs that completed Jul 8–9. This has apparently happened more than once — it's
  the exact failure mode a status dashboard should make structurally harder, by making
  "what's actually done" visible without an audit doc.
- **A real, non-obvious finding is sitting in `reports/`, not the paper**: the joint
  independence sweeps show the CV and DL engines' false-accepts are *positively*
  associated (Yule's Q > 0 on every leg where it's estimable) — refuting the
  error-independence complementarity claim, even though the cascade still wins on FAR.
  That's the kind of thing a "current state" page should surface prominently, not bury.
- **Results are scattered**: `reports/independence/**`, `reports/benchmark/**`,
  `reports/evaluation/**`, `docs/figures/`, `docs/reports/*.md`, and hand-written audits
  in `docs/audits/` all hold pieces of "where are we," with no single index.
- **Running anything means a local interactive terminal.** `main.py` is a ~1,940-line
  `input()`-driven menu (`GROUPED_CHOICES` at `main.py:21`) that ends in
  `subprocess.run()` (`run_choice`, `main.py:1738`). That's fine solo, but isn't
  something you can point a teammate or advisor at.
- **`live detect` doesn't actually work everywhere already.** `AGENTS.md`'s execution
  environment section says the Termux/Android runtime is headless — `cv.imshow` has
  nowhere to draw. This isn't a new problem the UI creates; it's an existing gap (hence
  decision #2: don't try to solve it in v1, just be honest about it).

## 3. Non-goals (explicit, per §1)

- No dependency graph / call-graph visualization, despite this repo having a
  `.codegraph/` index that could trivially feed one. Not what was asked for.
- No in-browser webcam streaming in v1.
- No execution reachable from the Vercel URL — not now, not via tunnel.
- No multi-user accounts/auth. The console is single-user by construction (bound to
  `127.0.0.1`); the dashboard has no login because it holds nothing more sensitive than
  what's already in the git repo.
- No attempt to auto-infer research judgment calls (pass/fail, "is this in the paper
  yet") from heuristics. See §7 — status is hand-stated, not guessed.

## 4. Architecture overview

```
                 ┌───────────────────────────────────────────┐
                 │   whichever machine is doing the work      │
                 │   (Windows now / Termux phone per AGENTS)  │
                 │                                             │
                 │   ui/console (FastAPI, 127.0.0.1 only)     │
                 │   ├── Terminal tab  → pty/pipe → main.py   │
                 │   ├── Forms tab     → subprocess → src/*   │
                 │   └── reads reports/, docs/, models/ live  │
                 │                                             │
                 │   scripts/build_study_manifest.py          │
                 │   reads reports/ + docs/ui/study_status.yml│
                 │   writes ui/dashboard/data/manifest.json   │
                 └───────────────────┬─────────────────────────┘
                                     │ git commit + push
                                     ▼
                 ┌───────────────────────────────────────────┐
                 │   GitHub repo (this repo)                  │
                 └───────────────────┬─────────────────────────┘
                                     │ Vercel's normal GitHub
                                     │ integration (auto-redeploy)
                                     ▼
                 ┌───────────────────────────────────────────┐
                 │   ui/dashboard (Next.js, on Vercel)         │
                 │   Study Status · Docs/Paper · Figures      │
                 │   — static build, no backend, no API       │
                 └───────────────────────────────────────────┘
```

The only thing that crosses from "local" to "public" is a small JSON file plus whatever
figures it references — both committed like any other file. There's no API call, no
database, no shared credential between the two halves.

## 5. Part A — Local Run Console (`ui/console/`)

### 5.1 Terminal tab

`main.py` is plain `input()`/`print()` — no curses, no `isatty()` branching, no cursor
control (confirmed by reading `main.py:1776` `main()` and `run_choice` at `main.py:1738`).
That means a full pseudo-terminal isn't actually required, which matters because Python's
`pty` module is POSIX-only and this project runs on both Windows and Termux/Linux:

- Spawn `main.py` with `subprocess.Popen(..., stdin=PIPE, stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)`.
- A WebSocket relays browser keystrokes → the subprocess's stdin, and stdout lines →
  the browser, rendered through **xterm.js** (vendored locally, not CDN-loaded, so it
  still works with no internet on the phone) purely as a display widget — it doesn't
  need a real pty underneath to render ANSI colors.
- **Re-verified 2026-07-11, corrected:** `tqdm==4.68.4` is in `requirements.txt` but
  `rg -l tqdm src/ scripts/ main.py` (and the nested `face-detection-g3/` folder) finds
  **zero imports** — it's an unused/orphaned dependency today, not "already used for
  progress bars" as originally drafted here. Also re-checked for manual `\r`-based
  progress rendering and ANSI color codes (`colorama`, raw `\x1b[`) across the same
  scope: none found either. Net effect on the design is actually *more* favorable to
  the plain-pipe approach than originally argued: every script in scope today does
  plain `print()` line output, so there is no carriage-return-overwrite behavior to
  worry about falling back from. If a script later adopts `tqdm`, its non-tty fallback
  (line-per-update) would still make it web-log-friendly automatically — that part of
  the original reasoning is correct as a forward-looking note, just not as a statement
  about current scripts.
- If a future script genuinely needs real tty semantics, the fallback is `pywinpty` on
  Windows / stdlib `pty` on POSIX — deliberately not built until something actually
  requires it.

This tab alone satisfies "run whatever `main.py` can run" completely and immediately,
since it *is* `main.py`, unmodified.

### 5.2 Dashboard / Forms tab

v1 scope: guided forms only for the actions people run most — **train**, **evaluate**,
and **independence test** (incl. "light front") for LBPH, Eigenfaces, Fisherfaces, and
Hybrid. Everything else in `GROUPED_CHOICES` (`main.py:21`) — the `Benchmark` group's 13
actions, `Hybrid`'s calibrate/compare, etc. — stays terminal-only for v1; promote
individual actions to forms later if they're used enough to be worth it.

To avoid the two surfaces drifting apart (main.py's menu changing without the forms
noticing): **`GROUPED_CHOICES` stays the single source of truth for what actions exist.**
The console imports/parses it directly from `main.py` rather than hand-copying the
model→action→script table, and a small check asserts the forms' action set is a subset
of it. The form fields themselves mirror what `main.py`'s `prompt_core_dataset_args`,
`prompt_augmented_dataset_args`, `prompt_detector_args`, etc. (`main.py:1323` onward)
already ask for interactively — same questions, form widgets instead of `input()` prompts.

Submitting a form builds the same argv `run_choice` would have built, and executes it
the same way (subprocess, streaming output) — it does not go through `main.py`'s `input()`
loop at all; it calls the target script (e.g. `src/lbph/trainer.py`) directly. Before
submission, the console re-uses `main.py`'s existing `warn_if_missing_auto_artifacts`
check so "evaluate without a trained model" gets caught the same way it is today.

### 5.3 Execution model

- **One job at a time.** `main.py`'s `build_subprocess_env` (`main.py:1713`) already
  caps BLAS/OpenMP threads specifically because oversubscribing a resource-constrained
  machine has caused stalls before — running two heavy jobs concurrently from the
  console would fight that same problem. A single-slot queue, not a pool, matches the
  existing design intent rather than fighting it.
- Live stdout/stderr streamed to the browser (same WebSocket mechanism as the terminal
  tab), plus a **Cancel** button (terminate the subprocess group).
- **Run history**: start/end time, exit code, full argv, which model/action — kept
  locally (e.g. a small SQLite file or even a JSON-lines log under `ui/console/`), not
  part of the manifest that goes to Vercel.

### 5.4 Live-detect actions

Per decision #2: listed like any other action, but the console doesn't attempt to
display the camera feed. Launching one runs the script headlessly; its logged FPS/
recognition numbers are polled and shown as a small live-updating stat block. Re-checked
against the actual source (`src/lbph/detect.py`): `fps_log_path` is opened/appended at
lines 293–295 and written to incrementally at lines 443–456 during the capture loop;
`session_log_json` is a separate one-shot summary written once at the very end,
lines 511–514 (the original "290-296" citation only covered the fps-log half — corrected
here). Both `src/eigenfaces/detect.py` and `src/fisherfaces/detect.py` mirror the same
shape; `src/hybrid/detect.py` too. All four detect scripts (`src/lbph`, `src/eigenfaces`,
`src/fisherfaces`, `src/hybrid`) call `cv.imshow` — confirmed via `rg -l imshow src/
scripts/`, exactly these four and no others — so the "no display" problem is scoped
exactly to the four `live detect` actions, nothing else in `GROUPED_CHOICES`. On a
machine with no display attached (the Termux/Android case `AGENTS.md` describes),
`cv.imshow` inside the script will fail or no-op — the console surfaces that as a clear
error rather than hiding it, instead of pretending the action fully works.

### 5.5 Tech stack

- **FastAPI + uvicorn** — async, native WebSocket support (needed for streaming logs
  and the terminal relay), fits the all-Python stack already in `requirements.txt`,
  free OpenAPI docs.
- **Server-rendered templates (Jinja2) + a little vanilla JS**, not React/Next — this
  needs to start with one command on any teammate's machine, including the Termux
  phone, with no Node build toolchain in the loop. xterm.js is the one JS library
  pulled in, vendored rather than CDN-loaded.
- New deps to add: `fastapi`, `uvicorn`, `websockets`, `jinja2`. No native/OpenCV-adjacent
  build pain — nothing here touches `opencv-contrib-python`'s C++ side.
- **Bind host is hardcoded, not just documented.** `uvicorn.run(app, host="127.0.0.1",
  port=8756)` — the host string is a literal in `ui/console/app.py`'s entrypoint, not
  read from an env var or CLI flag by default. If a `--host` override is ever added for
  a legitimate LAN-debugging case, it must require an explicit non-default flag *and*
  print a loud one-line warning to stderr on startup when the bound host isn't
  `127.0.0.1`/`localhost` — never a silent config-file toggle. This closes the gap
  where "should be 127.0.0.1 by default" was previously only a design intent (§1
  decision #4), not enforced anywhere in code.

### 5.6 API contract

No routes exist yet (`ui/console/` doesn't exist on disk as of 2026-07-11). This is the
concrete contract to build against — not a sketch. All routes are prefixed `/api`;
non-API routes serve the Jinja2 pages.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/` | Home page — links to Terminal tab and Forms tab, shows current run status if one is active |
| `GET` | `/terminal` | Terminal tab page (xterm.js shell) |
| `GET` | `/forms` | Forms tab page (train/evaluate/independence-test pickers, §5.2) |
| `GET` | `/api/actions` | List every `GROUPED_CHOICES` entry (model, action label, script path) parsed live from `main.py` — the "single source of truth" mechanism (§5.2). Response: `{"groups": [{"model": "LBPH", "actions": [{"label": "train", "script": "src/lbph/trainer.py"}, ...]}]}` |
| `GET` | `/api/actions/form-fields?model=LBPH&action=evaluate` | Returns the field list a form needs for this action, mirroring what `prompt_core_dataset_args`/`prompt_augmented_dataset_args`/`prompt_detector_args` (`main.py:1267` onward) ask interactively. Response: `{"fields": [{"name": "--model-path", "type": "path", "default": "models/lbph/lasalle_clean.yml", "required": true}, ...]}` |
| `GET` | `/api/models/trained` | Which models currently have artifacts on disk — scans `models/<family>/*.yml`/`*.onnx` + matching `labels_*.json`. Response: `{"LBPH": [{"path": "models/lbph/lasalle_clean.yml", "exists": true, "mtime": "..."}], ...}` — backs the "evaluate without a trained model" pre-check (§5.2's reuse of `warn_if_missing_auto_artifacts`) |
| `POST` | `/api/runs` | Submit a run. Body: `{"model": "LBPH", "action": "evaluate", "args": {"--model-path": "...", ...}}`. Builds the argv `run_choice` would have built, enqueues it (single-slot queue, §5.3). Response: `{"run_id": "20260711T090000Z-abc123", "status": "queued"}`. Returns `409` if a run is already in progress (one-job-at-a-time, §5.3) |
| `WS` | `/api/runs/{run_id}/stream` | WebSocket, streams stdout/stderr lines as `{"type": "stdout", "line": "..."}` frames as they're produced, then a final `{"type": "exit", "code": 0}` frame |
| `POST` | `/api/runs/{run_id}/cancel` | Terminates the subprocess (group), response `{"status": "cancelled"}` or `409` if already finished |
| `GET` | `/api/runs` | Run history list: `[{"run_id": "...", "model": "LBPH", "action": "evaluate", "argv": [...], "start": "...", "end": "...", "exit_code": 0}, ...]` — reads the local run-history store (§5.3: SQLite or JSONL under `ui/console/`) |
| `GET` | `/api/runs/{run_id}` | Single run detail incl. full captured log (for re-viewing after the WebSocket closed) |
| `WS` | `/api/terminal` | The Terminal tab's raw relay: browser keystrokes in, `main.py`'s combined stdout/stderr lines out. Separate from `/api/runs/*` because the Terminal tab *is* `main.py`'s own `input()` loop (interactive), not a fire-and-forget scripted run |
| `GET` | `/api/health` | `{"status": "ok", "bound_host": "127.0.0.1"}` — trivial liveness/host-sanity check, useful for a Phase-2 smoke test |

Not in scope for any phase here: auth routes (single-user by construction, §3), any
route that writes to `ui/dashboard/data/manifest.json` (that stays a manual/local script
per §7, not an API call from the console — keeps the "no live link between the two
apps" invariant from §1 decision #4 structurally true, not just a policy).

## 6. Part B — Researcher Dashboard (`ui/dashboard/`)

### 6.1 Study Status (the flagship view)

This is directly modeled on `docs/audits/STATE-07-10.md`, because that document is
already the right shape by hand — the goal is to make *that kind of view* durable and
current instead of a dated snapshot that goes stale the moment the next run happens.
Three parts, matching that audit's own structure:

1. **Per-leg status table** (mirrors §1.1–§1.6): rows are
   `model × dataset × test-type` (e.g. "LBPH × La Salle DB1 × independence test"),
   columns are artifact path, run date, protocol notes, status. Example row, transcribed
   from STATE-07-10.md §1.1 as a concrete illustration of the shape (not a live number):

   | Leg | Artifact | Run date | Status |
   |---|---|---|---|
   | LFW full (5,749 ids, 33,045,252 pairs) | `reports/independence/lbph_lfw1/` | Jul 8 | ✅ Run — the spec point is rank 330,453 = 10,000 ppm (θ = 19.18 raw) |

2. **Master checklist** (mirrors §2): Done / To-do-for-paper (writing only, data in
   hand) / To-do-open (needs a run, e.g. LFW-scale legs deferred to the "D: machine") /
   Deliberately out of scope (Paper 2). Rendered as a simple checklist or kanban board.

3. **Paper coverage table** (mirrors §1.7 — directly answers "does the paper lag the
   data"): section of `docs/PAPER.md` → state (stale / partial / rewrite needed / data
   ready) → what's needed. This is the piece that would have made the Jul-10 audit's
   headline finding ("paper is now behind the data") visible continuously, instead of
   needing a dedicated audit to notice.

**Deliberately not auto-inferred.** All three come from a small hand-maintained file,
`docs/ui/study_status.yml` (§7), that Kyle (or whoever else contributes results) updates
the same way these audits already get written — the dashboard's job is to render that
state well, not to guess it from file timestamps. STATE-07-10.md itself shows why:
distinguishing "Q > 0, significant, refutes complementarity" from "Q saturated,
degenerate, uninformative" is a judgment call a script would get wrong. A supplementary,
clearly-separate **artifact inventory** (file exists / mtime / size, no interpretation)
can sit alongside for anyone who wants the mechanical facts too.

### 6.2 Docs & Paper viewer

Renders as formatted pages, with working cross-links (the audits already link to each
other, e.g. STATE-07-10.md → `RECOMMENDATION.md` → `WHY_AND_HOW.md`):

- `docs/PAPER.md` (plain markdown, no LaTeX — confirmed by reading it; a standard
  markdown renderer is enough, no KaTeX/MDX math plugin needed)
- `docs/RECOMMENDATION.md`, `docs/DL_ERROR.md`
- `docs/READ THIS/*.md` — re-verified 2026-07-11, exactly 4 files: `BRIEFING.md`,
  `CLASSICAL_TRACK_AUDIT.md`, `INSTRUCTIONS.md`, `IW-FCV_2026_Call_for_Papers.md`
- `docs/reports/*.md` — re-verified, exactly 6 files: `ARCHITECTURE_REPORT.md`,
  `CLASSICAL_IMPROVEMENT_RESEARCH.md`, `DATASET_MATRIX.md`, `DETECTOR_COMPARISON.md`,
  `HYBRID_CV_DL_REPORT.md`, `SPEC_COMPARISON.md` (matches the "six finished write-ups"
  claim exactly)
- `docs/changelogs/*.md` (3 files), `docs/audits/*.md` (4 files, incl. `STATE-07-10.md`)
- `docs/presentation/**` (complementarity battery: 4 figs + `WHY_AND_HOW.md`;
  independence test expansion: 5 figs + `WHY_AND_HOW.md`)

Grouped by folder in the nav, matching the structure `AGENTS.md` already documents.

**The `docs/READ THIS/` space is a real build-time hazard, not just cosmetic** — this
was an open question in the original draft; resolved here. Node's `fs.readdir`/`readFile`
handle the literal space in the path fine (it's a normal filesystem path, not a URL) —
the risk is entirely on the *routing* side, once that folder's contents become
Next.js page URLs. Fix: **never derive a URL segment directly from a directory or file
name.** The docs-loader (Phase 1, `ui/dashboard/lib/docs.ts`) builds an explicit
slug map by hand instead of a generic slugify-the-path function:
```ts
const DOC_SOURCES: { slug: string; diskPath: string; title: string }[] = [
  { slug: "read-this/briefing", diskPath: "docs/READ THIS/BRIEFING.md", title: "Briefing" },
  { slug: "read-this/classical-track-audit", diskPath: "docs/READ THIS/CLASSICAL_TRACK_AUDIT.md", title: "Classical Track Audit" },
  { slug: "read-this/instructions", diskPath: "docs/READ THIS/INSTRUCTIONS.md", title: "Instructions" },
  { slug: "read-this/cfp-2026", diskPath: "docs/READ THIS/IW-FCV_2026_Call_for_Papers.md", title: "IW-FCV 2026 Call for Papers" },
  // ...one entry per doc across all the folders above; see BUILD.md Phase 1
];
```
The disk path (with the space, read via Node `fs`, never shell-globbed) is never
exposed in a URL; the slug (no space, explicit) is what App Router uses for
`app/docs/[...slug]/page.tsx`. This also sidesteps any Windows-vs-POSIX path-separator
or case-sensitivity surprises between whoever authors on Windows and Vercel's Linux
build image.

### 6.3 Figures gallery

`docs/figures/*.png` and `reports/figures/*.png` (both already git-tracked — verified,
see §7), browsable/filterable by experiment or model name. `docs/presentation/**`'s
images included the same way.

### 6.4 Raw results browser (stretch, not v1)

A light viewer for the tracked `reports/independence/**/summary.json` files — table/JSON
view only, for anyone who wants a number that isn't in a figure yet. Explicitly not a
re-plotting or analytics tool; that scope creep is exactly what would turn this into the
code-viz project that decision #3 ruled out.

### 6.5 Tech stack

- **Next.js (App Router)**, statically generated — reads `docs/**/*.md`, the manifest
  JSON, and figure files straight off the filesystem at build time (this is a monorepo;
  no separate CMS or API needed). Redeploys automatically on push via Vercel's normal
  GitHub integration.
- Plain markdown rendering (e.g. `react-markdown`) — no math plugin needed (§6.2).
- Tailwind for styling, to move fast on something whose whole value is legibility, not
  visual novelty.

**Monorepo build risk — checked against Vercel's docs 2026-07-11, not assumed.**
Vercel's own "Root Directory" doc (`vercel.com/docs/deployments/configure-a-build`,
page dated 2026-07-01) states plainly: *"Your app will not be able to access files
outside of \[the Root Directory\]. You also cannot use `..` to move up a level."* That
directly contradicts the "reads `docs/**` straight off the filesystem" plan above if
Vercel's Project **Root Directory** setting is pointed at `ui/dashboard/` (the obvious
way to configure this in the dashboard). A separate community-sourced mention of an
"Include source files outside of the Root Directory in the Build Step" checkbox
surfaced in search results, but it does **not** appear on the primary Root Directory
doc page fetched directly — so its current existence/behavior is **unconfirmed**, not
verified false, not verified true. Rather than gamble the whole dashboard on an
unconfirmed checkbox, the fix adopted here removes the dependency entirely:

**Fix: make the dashboard self-contained inside its own Root Directory.**
`scripts/build_study_manifest.py` (§7) is extended beyond just writing
`manifest.json` — it also **copies** (not symlinks; Windows/Termux-hostile) the exact
set of files the dashboard needs into `ui/dashboard/`:
- `docs/**/*.md` (incl. `docs/READ THIS/*.md`, `docs/reports/*.md`, `docs/changelogs/*.md`,
  `docs/audits/*.md`, `docs/presentation/**/*.md`) → `ui/dashboard/content/docs/**`
- `docs/figures/*.png`, `reports/figures/*.png`, `docs/presentation/**/*.png` →
  `ui/dashboard/public/figures/**`
- `reports/independence/**/summary.json` (for the stretch raw-results browser, §6.4) →
  `ui/dashboard/content/results/**`

This means: (a) the dashboard works identically whether or not Vercel's Root Directory
sandboxing turns out to forbid `..` reads, because it never needs to read outside its
own directory once the copy step has run; (b) the copied files are committed
(`ui/dashboard/content/`, `ui/dashboard/public/figures/` are **not** gitignored) so
Vercel's shallow `git clone --depth=10` (Vercel's own documented clone behavior) always
has them regardless of Root Directory; (c) it costs one more thing for the sync script
to do, already being run manually per §7's rollout. **Still worth validating directly
in the Vercel dashboard during Phase 0** (create the project, set Root Directory,
attempt a build) before deciding this fix is even necessary — if the checkbox does
exist and works, direct `../../docs` reads would also be fine and the copy step becomes
a (harmless) belt-and-suspenders. Treat that validation as a Phase 0 exit item, not an
assumption baked into Phase 1.

### 6.6 Page / route list

Concrete Next.js App Router paths (all statically generated, no server runtime):

| Route | Renders | Data source |
|---|---|---|
| `/` | Landing — headline finding banner, links to the 4 sections below, "last updated" from manifest | `manifest.json` (`study_status`, `headline_finding`) |
| `/status` | Study Status flagship view (§6.1): per-leg table, master checklist, paper-coverage table, tab-switchable | `manifest.json` (`legs`, `checklist`, `paper_sections`) |
| `/status/legs/[slug]` | Single leg detail (artifact contents, full protocol/result note, link to raw `summary.json` if tracked) | `manifest.json` (`legs[]`) + direct fetch of the tracked JSON |
| `/docs` | Docs index, grouped by folder per §6.2 | `content/docs/**` (copied `.md` files, §6.5 fix) via the `DOC_SOURCES` slug map |
| `/docs/[...slug]` | One rendered markdown doc | same, single file |
| `/paper` | `docs/PAPER.md` rendered, with a persistent "coverage" sidebar cross-linking each section to its `paper_sections[]` state | `content/docs/paper.md` + `manifest.json` (`paper_sections`) |
| `/figures` | Figures gallery (§6.3), filterable by filename prefix (`fig_hybrid_*`, `fig1_*`, etc.) | `manifest.json` (`figures[]`) + `public/figures/**` |
| `/results` (stretch, Phase 4) | Raw results browser (§6.4) — table/JSON toggle per tracked `summary.json` | `content/results/**` + `manifest.json` (`benchmark_summary[]`) |

No dynamic API routes anywhere in `ui/dashboard/` — everything above is either a static
page or a static-JSON fetch resolved at build time, consistent with §1 decision #4
("no API call" crossing from local to public).

## 7. The sync bridge: `study_status.yml` → `manifest.json`

```
docs/ui/study_status.yml          (hand-maintained: the source of truth)
        │
        ▼  scripts/build_study_manifest.py
        │  (reads the yml + scans reports/ for artifact paths/dates)
        ▼
ui/dashboard/data/manifest.json   (generated, committed, small)
```

Run manually for now (`python scripts/build_study_manifest.py`); could become a button
in the console (§5) or a `main.py` menu action later, but isn't required for v1.

**A concrete blocker found while writing this doc, not a hypothetical one:**
`.gitignore` lines 121–125 ignore `reports/benchmark/*.json`, `*.md`, `**/*.json`,
`**/*.jsonl`; lines 117–120 ignore `reports/evaluation/*.json`/`*.txt`. Re-verified
2026-07-11 with `git check-ignore` and `git status --ignored=matching` against every
path in `reports/`: **exactly** the `reports/benchmark/*.{json,md}` and
`reports/evaluation/*.{json,txt}` families are ignored (94 files currently) — confirmed
e.g. `reports/benchmark/accuracy_ratio_hybrid.md` is ignored, while
`reports/independence/hybrid/lsdb1_i10/summary.json` and `docs/figures/*.png` are not.

**Correction to the original draft of this section:** it also claimed "line 171 ignores
`reports/figures/data/`." That line is blank (confirmed three ways: raw byte split,
`awk`, PowerShell `Get-Content` all agree line 171 is empty; `rg figures .gitignore`
finds no match anywhere in the file). `git status --ignored=matching reports/` does
**not** list anything under `reports/figures/data/` as ignored — `roc_scores.json`
(761 KB) there is simply **untracked**, never `git add`-ed, not excluded by any rule.
So that specific file has an uncomplicated fix with no `.gitignore` decision attached:
just `git add` it (see Phase 0 in `docs/ui/BUILD.md`) — it was never blocked. This
changes the shape of the remaining problem: the only real "no path into a git-based
Vercel deploy" gap is `reports/benchmark/**` and `reports/evaluation/**`.
STATE-07-10.md §5.7 flagged the benchmark half of this independently: the Jul 9 hybrid
AR report, the evidence matrix, and the gate-curve outputs exist only on whichever
machine ran them.

This means, **as of today, the Benchmark action group's results (and the standalone
per-model evaluation JSONs) have no path into a git-based Vercel deploy** — but the
figures-data directory does. Two ways to close the benchmark/evaluation gap:

- **(Recommended) Leave `.gitignore` alone; summarize instead of tracking raw files.**
  `build_study_manifest.py` reads the local (gitignored-but-present) benchmark JSON/MD
  and copies just the numbers/figure-paths it needs into the tracked `manifest.json`.
  The bulky raw artifacts stay untracked and local, exactly as today; only the small
  derived summary travels to Vercel. Lower risk, no repo-size/`.gitignore`-semantics
  change.
- **Carve exceptions in `.gitignore`** for the canonical files only (`accuracy_ratio_hybrid.md`,
  `evidence_matrix.{json,md}`, `gate_operating_curve.{md,png}`) — what STATE-07-10.md
  itself already suggested. Simpler pipeline, but changes what's tracked in git, which
  is the team's call, not this doc's.

### 7.1 `study_status.yml` — complete hand-authored schema

Every field below is what the three Study Status sub-views (§6.1) actually need to
render — not illustrative. Kyle (or whoever edits it) hand-writes this; nothing here is
inferred from file timestamps (§6.1's "deliberately not auto-inferred" rule).

```yaml
# docs/ui/study_status.yml
# Hand-maintained. Re-edit this whenever a run finishes or a paper section changes —
# it is the ONLY source for the dashboard's Study Status page (manifest.json is
# generated FROM this + a scan of reports/, never edited by hand).

updated: "2026-07-11"          # ISO date, shown as "last updated" on the dashboard
updated_by: "Kyle"              # free text, whoever last touched this file

# --- Sub-view 1: per-leg status table (§6.1.1) ---------------------------------
legs:
  - model: LBPH                 # one of: LBPH | Eigenfaces | Fisherfaces | Hybrid
    dataset: "La Salle DB1"      # free text, matches how STATE-07-10.md names it
    test_type: independence      # one of: independence | independence_light_front |
                                  #   joint_independence | 41mod_ar | evidence_matrix |
                                  #   tar_far | other
    artifact_path: "reports/independence/lbph_lasalle/"   # repo-relative; build script
                                                             # verifies this exists and
                                                             # records mtime/size (§7.2)
    run_date: "2026-06-10"       # ISO date the run was executed
    status: done                 # one of: done | in_progress | open | superseded
    protocol_note: "1 deterministic light_front run, canonical."
    result_note: >
      Threshold 21.35 raw / 85.88 norm at the 8th pair (10,582 ppm realized).
    superseded_by: null          # artifact_path of the leg that replaces this one,
                                  # or null — e.g. lsdb1's iterations=1 Jul-8 run is
                                  # superseded_by the lsdb1_i10 10-iteration rerun

  - model: Hybrid
    dataset: "La Salle DB1"
    test_type: joint_independence
    artifact_path: "reports/independence/hybrid/lsdb1_i10/"
    run_date: "2026-07-10"
    status: done
    protocol_note: "10 iterations, paper protocol (pooled over 7,560 comparisons)."
    result_note: >
      LBPH FP 0.661%, SFace FP 1.799%, cascade FP 1.389%, Q +0.66,
      Fisher p_pos 0.012 (co-occurrence significant).
    superseded_by: null

# --- Sub-view 2: master checklist (§6.1.2) --------------------------------------
checklist:
  done:
    - "LBPH independence — La Salle DB1 canonical 10-run (Jun 10)"
    - "Joint sweep rerun at 10 iterations — lsdb1/lsdb2_light/lsdb2_medium (Jul 10)"
  todo_paper:                    # writing only — data already in hand
    - "§4.3: insert hybrid AR table + Wilson CIs + winner tags"
  todo_open:                     # needs a new run before it can be written
    - "LFW-DB2 41-mod leg (LFW-scale, open — run on the D: machine)"
  out_of_scope:
    - "Pi-5 port, INT8 SFace, on-device FPS (Paper 2)"

# --- Sub-view 3: paper coverage table (§6.1.3) -----------------------------------
paper_sections:
  - section: "Abstract"
    state: stale                 # one of: stale | partial | rewrite_needed | data_ready | current
    needed: >
      Says the joint test + 41-mod suite "complete the argument" as if pending;
      update after §4.5 rewrite; add co-occurrence finding + cascade-FAR win.
  - section: "§4.5 Joint independence"
    state: rewrite_needed
    needed: >
      Fill with the 6-leg reframed panel; lead cascade-FP vs double-fault floor,
      then obs/exp + Fisher (positive association!), then Q/phi captioned.
  - section: "§4.3 Hybrid AR [PENDING]"
    state: data_ready
    needed: "Insert the Jul 9 hybrid AR table + winner tags + cascade-vs-parallel line."

# --- Cross-cutting: the finding banner (§2, "a real finding sitting in reports/") --
headline_finding:
  active: true
  title: "Error-independence complementarity: refuted at scale"
  summary: >
    Joint sweeps show LBPH/SFace false-accepts are positively associated
    (Yule's Q > 0) on every leg where estimable; the cascade still wins on FAR
    via the gate, not via error independence.
  source_doc: "docs/audits/STATE-07-10.md"
```

### 7.2 `ui/dashboard/data/manifest.json` — generated output schema

Written by `scripts/build_study_manifest.py`. Next.js reads this at build time (or,
once copied per §6.5's monorepo fix below, from inside its own Root Directory). It is
`study_status.yml`'s content **plus** mechanical facts the script derives by scanning
`reports/` (the "supplementary artifact inventory" §6.1 mentions) — never judgment
calls; those only ever come from the yml.

```jsonc
{
  "generated_at": "2026-07-11T09:00:00Z",        // ISO 8601, script run time
  "source_yml_hash": "sha256:...",                 // detects stale manifest vs yml
  "study_status": {
    "updated": "2026-07-11",
    "updated_by": "Kyle",
    "headline_finding": { /* verbatim from yml */ }
  },
  "legs": [
    {
      // verbatim fields from study_status.yml's `legs[]`, plus:
      "model": "LBPH", "dataset": "La Salle DB1", "test_type": "independence",
      "artifact_path": "reports/independence/lbph_lasalle/",
      "run_date": "2026-06-10", "status": "done",
      "protocol_note": "...", "result_note": "...", "superseded_by": null,
      // derived by the script, not hand-authored:
      "artifact_exists": true,
      "artifact_mtime": "2026-06-10T14:22:00Z",
      "artifact_files": ["summary.json", "comparisons.csv"],
      "artifact_size_bytes": 48213
    }
  ],
  "checklist": { "done": [...], "todo_paper": [...], "todo_open": [...], "out_of_scope": [...] },
  "paper_sections": [
    { "section": "§4.5 Joint independence", "state": "rewrite_needed", "needed": "..." }
  ],
  "benchmark_summary": [
    // ONLY populated if the §7 .gitignore decision is "summarize-only" (recommended):
    // the script reads the locally-present-but-gitignored reports/benchmark/*.json
    // files and copies out just the headline numbers + a pointer, never the raw file.
    {
      "artifact": "reports/benchmark/accuracy_ratio_hybrid.json",
      "tracked_in_git": false,
      "headline": {
        "overall_ar_percent": { "cv": 85.43, "dl": 96.50, "cascade": 96.11, "parallel": 96.50 },
        "mean_latency_ms": { "cv": 5.62, "dl": 22.44, "cascade": 15.99, "parallel": 22.77 }
      },
      "run_date": "2026-07-10"
    }
  ],
  "figures": [
    // every file under docs/figures/*.png and reports/figures/*.png, for the gallery
    { "path": "docs/figures/fig_hybrid_accuracy.png", "label": "fig_hybrid_accuracy" }
  ]
}
```

**Field-to-view mapping** (so an implementer knows exactly what each page reads):

| Dashboard view (§6.1) | Reads from manifest |
|---|---|
| Per-leg status table | `legs[]` (all fields) |
| Master checklist / kanban | `checklist.{done,todo_paper,todo_open,out_of_scope}` |
| Paper coverage table | `paper_sections[]` |
| Headline-finding banner | `study_status.headline_finding` |
| Figures gallery | `figures[]` |
| Raw results browser (stretch, §6.4) | `benchmark_summary[]` + direct fetch of tracked `reports/independence/**/summary.json` |

## 8. New directories this introduces

```
docs/ui/
  DESIGN.md              (this file)
  BUILD.md                (phased implementation plan)
  study_status.yml        (hand-maintained source of truth, §7)
scripts/
  build_study_manifest.py (new — the sync script, §7)
ui/
  console/                 (new — FastAPI local run app, §5)
    app.py, routes/, static/xterm/ (vendored), run_history.{db,jsonl}
  dashboard/               (new — Next.js app, deployed to Vercel, §6)
    data/manifest.json     (generated, committed)
    content/docs/**         (generated, committed — copied .md, §6.5 fix)
    content/results/**      (generated, committed — copied summary.json, §6.5 fix)
    public/figures/**       (generated, committed — copied .png, §6.5 fix)
```

Nothing under `src/`, `scripts/` (existing files), or `main.py` needs to change for
Phase 1–2 below — the console calls existing scripts as-is; `main.py` is wrapped, not
modified.

## 9. Phased rollout

| Phase | Delivers | Touches execution? |
|---|---|---|
| **0** | Write `docs/ui/study_status.yml` by hand (transcribe current `STATE-07-10.md` state); decide the `.gitignore` question (§7) | No |
| **1** | Dashboard: Study Status + Docs/Paper viewer + Figures gallery, on Vercel | No — read-only, ships without touching `main.py` at all |
| **2** | Console: Terminal tab wrapping `main.py` | Yes, but zero logic duplication |
| **3** | Console: guided forms for train/evaluate/independence-test | Yes |
| **4** (stretch) | Live-detect stats surfacing; raw-results browser | Yes |

Phase 1 is deliberately first and is the highest-value/lowest-risk slice: it directly
targets the "paper lags the data" problem from §2 without writing a single line that
touches `main.py`, a subprocess, or a webcam.

**Per-phase verification is not implicit** — each phase in `docs/ui/BUILD.md` ends with
a "Definition of done" checklist: a manual step that proves the phase actually works
end to end (e.g. Phase 2's is "launch `main.py` from the Terminal tab and complete an
LBPH evaluate run"), not just "code compiles" or "build succeeds."

## 10. Open questions for the team — confirmed by Kyle, 2026-07-11

These three were genuine product/architecture calls, not implementation details. A
review pass proposed the defaults below; **Kyle confirmed all three as-is** in a
follow-up AskUserQuestion round the same day — nothing here is provisional. `docs/ui/BUILD.md`
Phase 0.1 already reflects this.

- **Who maintains `study_status.yml` going forward?**
  **Default: Kyle, manually, same cadence as the audit docs it replaces** (this repo's
  memory notes him as the classical-CV track's audit-driven owner) — updated as part of
  finishing each run or paper edit, not on a schedule. Revisit if the team grows past
  one active experimenter. Alternative considered: infer `status`/`run_date` from
  artifact mtimes automatically — rejected for the same reason §6.1 rejects it
  elsewhere: distinguishing "done" from "superseded" from "needs a rerun at the paper's
  protocol" is a judgment call, not a file-timestamp fact.
- **Does the DL track (`face-detection-g3/`) belong in the same dashboard?**
  **Default: excluded from v1.** Re-verified 2026-07-11: it's untracked (`git status`
  shows `?? face-detection-g3/`), has no `.git` of its own (plain directory, not a
  submodule), and its `results/*.json` schema has not been cross-checked against
  anything this doc's schemas assume. Including it would require understanding that
  schema first and is explicitly a "does the DL track belong in *this* dashboard"
  scope call, which is squarely the kind of fork only Kyle (or the DL teammate) should
  make. Revisit as a Phase-4-or-later add-on once/if that schema is documented.
- **The `.gitignore` question from §7** — sharpened by this review's correction (§7):
  `reports/figures/data/` was never actually gitignored (fix: just `git add` it,
  zero-risk, no decision attached). The real remaining decision is scoped to
  `reports/benchmark/*.{json,md}` and `reports/evaluation/*.{json,txt}` only.
  **Default: (Recommended, unchanged from the original draft) summarize-only** —
  leave `.gitignore` alone, `build_study_manifest.py` reads the local gitignored files
  and copies just the numbers into the tracked `manifest.json`'s `benchmark_summary[]`
  (§7.2). Lower risk, no repo-size change, and STATE-07-10.md's own alternative
  suggestion (carve exceptions for the 3 canonical files) remains available later
  without redoing anything if Kyle prefers it instead.
