# Study Dashboard & Run Console — Build Plan

**Status:** ready to execute. **Input:** `docs/ui/DESIGN.md` (read that first — this
plan doesn't re-explain the architecture, only sequences building it). **Scope:** no
product code exists yet under `ui/` or `scripts/build_study_manifest.py` as of
2026-07-11 — everything below is new work.

Every checkbox is meant to be executable without re-deriving intent from `DESIGN.md`.
Where a step depends on an unresolved call, that's noted inline as a **BLOCKER**.

---

## Phase 0 — Data prerequisites

Nothing in Phase 1 can render real numbers until this phase produces
`docs/ui/study_status.yml` and a working `build_study_manifest.py`. No code in `ui/`
yet.

### 0.1 Resolve the three open calls from DESIGN.md §10

- [x] **Confirmed by Kyle, 2026-07-11** — all three recommended defaults stand:
      (a) Kyle maintains `study_status.yml` manually, as-needed, same cadence as the
      audits it replaces; (b) the `face-detection-g3/` DL-track folder is **excluded**
      from v1; (c) the `.gitignore` question is **summarize-only** (leave
      `reports/benchmark/**` and `reports/evaluation/**` ignored; copy numbers into the
      manifest instead of tracking the raw files). Nothing here is provisional anymore —
      proceed on this basis.

### 0.2 Fix the actual (not assumed) `.gitignore` gap

- [ ] **`git add reports/figures/data/`** (currently `reports/figures/data/roc_scores.json`,
      761 KB) and commit it. This directory was **never gitignored** — `.gitignore`
      line 171 is blank; `git status --ignored=matching reports/` confirms nothing
      under `reports/figures/data/` is excluded. It was simply never `git add`-ed. No
      `.gitignore` edit needed for this one. (Verified 2026-07-11 — see `DESIGN.md` §7
      correction.)
- [ ] If 0.1(c) was overridden to "carve tracked exceptions" instead of
      "summarize-only": edit `.gitignore` to remove/negate the specific lines for
      `reports/benchmark/accuracy_ratio_hybrid.md`, `reports/benchmark/evidence_matrix.{json,md}`,
      `reports/benchmark/gate_operating_curve.{md,png}` (add `!`-prefixed exceptions
      after the existing `reports/benchmark/*.json`/`*.md` rules at lines 121-122), then
      `git add` those specific files. Skip this step entirely if 0.1(c) stayed
      "summarize-only" (the default) — in that case `.gitignore` is not touched at all.

### 0.3 Validate the Vercel monorepo assumption before building around it

- [ ] Create a throwaway Vercel project pointed at this repo with **Root Directory**
      set to a placeholder subdirectory (any existing one, e.g. `docs/ui/`) containing
      a trivial `package.json` + `index.html`. Attempt to read a file from `../../docs`
      in a build script and observe whether the build fails, and whether an "Include
      source files outside of the Root Directory" toggle is visible in
      **Settings → Build and Deployment → Root Directory**. This directly resolves the
      conflict noted in `DESIGN.md` §6.5 between the official Root Directory doc
      ("cannot use `..`") and a community-sourced mention of a bypass checkbox.
      **Record the outcome as a one-line comment at the top of
      `scripts/build_study_manifest.py`** (e.g. `# Vercel Root Directory sandboxes
      builds; verified 2026-07-XX; content/, public/figures/ copy-step below is
      required, not optional`) so Phase 1 doesn't re-litigate this.
- [ ] Regardless of the outcome: proceed with the copy-into-`ui/dashboard/` approach
      from `DESIGN.md` §6.5 (steps 0.6-0.8 below) — it works either way, so this
      validation step is a confirmation, not a gate that blocks Phase 0 from finishing
      if inconclusive. Note the outcome and move on.

### 0.4 Reconcile `study_status.yml` with what's *actually* on disk, not just STATE-07-10.md

- [ ] Before transcribing, check current `git status` for already-completed work that
      post-dates `STATE-07-10.md` (2026-07-10): as of this review, the working tree has
      untracked `reports/independence/hybrid/{lsdb1_i10,lsdb2_light_i10,lsdb2_medium_i10}/`
      (the 10-iteration paper-protocol reruns — STATE-07-10.md §5.4 numbers), an
      untracked `scripts/sweep_gate_curve.py`, and modified `docs/PAPER.md`,
      `src/benchmark/accuracy_ratio_hybrid.py`, `src/stats_utils.py`. These represent
      audit-session work that is done but not yet committed or reflected in any
      `[status: done]` entry. Write `study_status.yml`'s `legs[]`/`checklist[]` against
      the **current** state (mark the `*_i10` legs as `status: done`, `superseded_by`
      pointing from the Jul-8 `iterations=1` legs to them), not a stale transcription.
- [ ] Commit or at least `git add` the above untracked artifacts first (or explicitly
      decide not to and note why in `study_status.yml`) — the manifest script in 0.7
      can only report on what's in the artifact paths it scans; uncommitted-but-present
      files still get picked up by a local run of the script (it reads the filesystem,
      not git), but won't survive to Vercel until committed.

### 0.5 Write `docs/ui/study_status.yml`

- [ ] Create `docs/ui/study_status.yml` using the exact schema in `DESIGN.md` §7.1
      (`updated`, `updated_by`, `legs[]`, `checklist{}`, `paper_sections[]`,
      `headline_finding`). Populate from `STATE-07-10.md` §1 (per-leg table), §2
      (master checklist), §1.7 (paper coverage table), plus the 0.4 reconciliation.
      Every `legs[].artifact_path` must be a real repo-relative path — the build script
      in 0.7 will hard-fail (not warn) if one doesn't exist, by design, so a fake path
      is caught immediately rather than silently rendering "done" for nothing.

### 0.6-0.8 Write `scripts/build_study_manifest.py`

- [ ] Add `PyYAML` to `requirements.txt` (new dependency — nothing currently parses
      YAML in this repo; `rg -l yaml src/ scripts/` returns nothing).
- [ ] Create `scripts/build_study_manifest.py`. Responsibilities, in order:
  1. Load `docs/ui/study_status.yml` (`yaml.safe_load`).
  2. For each `legs[]` entry, resolve `artifact_path` relative to repo root; record
     `artifact_exists`, `artifact_mtime` (newest file under the path), `artifact_files`
     (top-level listing), `artifact_size_bytes` (sum). Hard-fail (non-zero exit,
     printed path) if `artifact_exists` is false — a stale/typo'd path in the yml
     should break the build loudly, not render wrong.
  3. If the gitignore decision (0.1c) is "summarize-only": read
     `reports/benchmark/accuracy_ratio_hybrid.json`, `reports/benchmark/evidence_matrix.json`,
     `reports/benchmark/gate_operating_curve.json` (whichever exist locally) and emit
     the `benchmark_summary[]` block per the field shape in `DESIGN.md` §7.2 — pull
     only `overall_ar_percent`, `mean_latency_ms`, `complementarity_battery` headline
     numbers, `evidence_matrix`'s `legs`/`thresholds_sha256`, and
     `gate_operating_curve`'s deployed-point AR/escalation numbers. Never copy the full
     JSON.
  4. Enumerate `docs/figures/*.png`, `reports/figures/*.png`,
     `docs/presentation/**/*.png` into `figures[]`.
  5. Write `ui/dashboard/data/manifest.json` (schema: `DESIGN.md` §7.2), pretty-printed
     (`json.dump(..., indent=2)`) so diffs are reviewable.
  6. **Copy step (the §6.5 monorepo fix):** copy every doc listed in `DESIGN.md` §6.2
     into `ui/dashboard/content/docs/**` (mirroring the `DOC_SOURCES` slug map's disk
     paths from `DESIGN.md` §6.2), copy the figure files referenced in step 4 into
     `ui/dashboard/public/figures/**`, and copy every tracked
     `reports/independence/**/summary.json` into `ui/dashboard/content/results/**`
     (skip `_raw_runs/` subdirectories — only the top-level per-leg `summary.json`).
     Use `shutil.copy2` (preserves mtime), never a symlink (Windows requires elevated
     privileges for symlinks; Termux/Android doesn't support them reliably either).
  7. Print a summary line count of what changed (files copied, manifest size) so a
     human running it locally can eyeball the diff before `git add`.
- [ ] Run it: `python scripts/build_study_manifest.py`. Fix any hard-fail path errors
      by correcting `study_status.yml`, not by loosening the script's validation.
- [ ] `git add docs/ui/study_status.yml scripts/build_study_manifest.py requirements.txt ui/dashboard/data/manifest.json ui/dashboard/content/ ui/dashboard/public/figures/` and commit.

### Phase 0 — Definition of done

- [ ] `python scripts/build_study_manifest.py` runs clean (exit 0) from a fresh clone
      of the current commit.
- [ ] `ui/dashboard/data/manifest.json` exists, is valid JSON, and every `legs[]` entry
      in it has `artifact_exists: true`.
- [ ] `ui/dashboard/content/docs/`, `ui/dashboard/content/results/`, and
      `ui/dashboard/public/figures/` are populated and `git status` shows them as
      tracked (not `??`).
- [ ] The Vercel Root Directory behavior from 0.3 is recorded somewhere durable (a
      comment in the script, or a line added to `DESIGN.md` §6.5) — even if the
      answer is "inconclusive, copy-step is load-bearing regardless."

---

## Phase 1 — Dashboard (Vercel, read-only)

**Prerequisite: Phase 0 complete** (manifest + content/ + public/figures/ populated and
committed — the dashboard has nothing real to render otherwise).

### 1.1 Scaffold the Next.js app

- [ ] `npx create-next-app@latest ui/dashboard --typescript --tailwind --app --eslint --src-dir=false --import-alias "@/*"` (or hand-write `package.json`/`tsconfig.json`/`tailwind.config.ts` if offline — either way, App Router, no `src/` wrapper to keep paths short).
- [ ] Add to `ui/dashboard/package.json` dependencies: `react-markdown`, `gray-matter`
      (frontmatter-free here, but handles edge-case `---` in the audit docs safely),
      `js-yaml` (only if any page needs to re-parse yaml client-side — otherwise skip,
      the manifest is already JSON).
- [ ] Do **not** set a Vercel Root Directory build command that assumes repo-root
      access beyond what Phase 0 already copied into `ui/dashboard/` — the whole point
      of the 0.6 copy step is that `ui/dashboard/` is self-contained from here on.

### 1.2 Data-loading libraries

- [ ] `ui/dashboard/lib/manifest.ts` — reads `data/manifest.json` at build time
      (`import manifest from "@/data/manifest.json"` works directly in Next.js/TS, no
      fs call needed since it's inside the Root Directory).
- [ ] `ui/dashboard/lib/docs.ts` — implements the explicit `DOC_SOURCES` slug map from
      `DESIGN.md` §6.2 (paths now relative to `content/docs/**` post-copy, e.g.
      `content/docs/read-this/BRIEFING.md` — decide at copy-time in 0.6 whether to
      preserve the "READ THIS" space in the copied path or normalize it to
      `read-this/` during the copy itself; **recommended: normalize during copy** so
      `lib/docs.ts` never has to special-case a space at all — simpler than keeping the
      space and slug-mapping around it). Exports `getAllDocSlugs()` and
      `getDocBySlug(slug)`.

### 1.3 Pages (routes per `DESIGN.md` §6.6)

- [ ] `ui/dashboard/app/layout.tsx` — root layout, nav linking the 5 routes below.
- [ ] `ui/dashboard/app/page.tsx` — `/`, headline finding banner + links.
- [ ] `ui/dashboard/app/status/page.tsx` — `/status`, the 3 Study Status sub-views
      (tabs or stacked sections): per-leg table, checklist, paper-coverage table.
- [ ] `ui/dashboard/app/status/legs/[slug]/page.tsx` — `/status/legs/[slug]`, uses
      `generateStaticParams()` over `manifest.legs` (slug = slugified
      `${model}-${dataset}-${test_type}`).
- [ ] `ui/dashboard/app/docs/page.tsx` and `app/docs/[...slug]/page.tsx` — `/docs`
      index + `/docs/[...slug]` detail, per 1.2's `lib/docs.ts`.
- [ ] `ui/dashboard/app/paper/page.tsx` — `/paper`, renders `content/docs/paper.md`
      with a sidebar built from `manifest.paper_sections`.
- [ ] `ui/dashboard/app/figures/page.tsx` — `/figures`, grid over `manifest.figures`,
      client-side filter input (prefix match on filename).
- [ ] Skip `/results` (Phase 4 stretch) for now.

### 1.4 Styling

- [ ] Tailwind base + a single shared `<StatusBadge>` component (`done` = green,
      `in_progress` = amber, `open` = red, `superseded` = gray strikethrough) reused
      across the per-leg table, checklist, and paper-coverage table for visual
      consistency.

### 1.5 Deploy

- [ ] Push to GitHub, connect the repo in Vercel, set **Root Directory** =
      `ui/dashboard`, Framework Preset = Next.js (auto-detected). Deploy.
- [ ] Confirm auto-redeploy on push (Vercel's default GitHub integration, no extra
      config).

### Phase 1 — Definition of done

- [ ] `cd ui/dashboard && npm run build` succeeds locally with zero fs calls outside
      `ui/dashboard/` (grep the build output / source for `../..` to confirm none
      snuck in).
- [ ] The Vercel deployment URL loads `/`, `/status`, `/docs`, `/paper`, `/figures` and
      each renders real content from the current `manifest.json` (not placeholder
      text) — specifically confirm the `/status` page shows the Yule's-Q positive-
      association headline finding from `STATE-07-10.md`, proving the "paper lags the
      data" problem from `DESIGN.md` §2 is now visible without opening a terminal.
- [ ] A second push (e.g. editing `study_status.yml`, rerunning
      `build_study_manifest.py`, pushing) triggers an automatic redeploy and the
      change appears live within Vercel's normal build time.

---

## Phase 2 — Console: Terminal tab

**Prerequisite:** none from Phase 1 (fully independent — this is the local-only half).
Runs on whichever machine is doing experiments (Windows now, Termux later per
`AGENTS.md`).

### 2.1 Scaffold FastAPI app

- [ ] Add to `requirements.txt`: `fastapi`, `uvicorn[standard]` (pulls in `websockets`
      and `httptools`), `jinja2`.
- [ ] Create `ui/console/app.py`:
  ```python
  import uvicorn
  from fastapi import FastAPI
  app = FastAPI(title="LS-Face Run Console")
  # ...routers included here (2.3, 2.4)...
  if __name__ == "__main__":
      uvicorn.run(app, host="127.0.0.1", port=8756)  # literal, not env-configurable by default
  ```
- [ ] Create `ui/console/templates/` (Jinja2) and `ui/console/static/` directories.

### 2.2 Vendor xterm.js (no CDN)

- [ ] Download `xterm.js` + `xterm.css` (and the `xterm-addon-fit` package for
      resizing) from npm (`npm pack @xterm/xterm @xterm/addon-fit` in a scratch dir,
      then copy the built `lib/` files) into `ui/console/static/vendor/xterm/`. Commit
      these — no `npm install` step required to run the console, consistent with the
      "no Node build toolchain" tech-stack decision (`DESIGN.md` §5.5).

### 2.3 Action registry — parse `GROUPED_CHOICES` from `main.py`, don't hand-copy it

- [ ] Create `ui/console/action_registry.py`. Import `main` as a module
      (`sys.path` already has repo root since `ui/console` sits under it) and read
      `main.GROUPED_CHOICES` directly — this is the "single source of truth" mechanism
      `DESIGN.md` §5.2 requires. Expose `list_groups() -> list[dict]` matching the
      `/api/actions` response shape in `DESIGN.md` §5.6.
  - **Caution:** importing `main.py` executes any module-level code in it. Check
    `main.py`'s top-level statements (outside `if __name__ == "__main__":` guards)
    before doing a plain `import main` — if anything at module scope has side effects
    (e.g. reads a file, prints), either guard the import with
    `importlib.util.spec_from_file_location` + selectively exec'ing just the
    `GROUPED_CHOICES` assignment via AST parsing, or confirm the plain import is side-effect-free first. Prefer the AST-based extraction if in doubt — safer than a full
    module import for a file this large (1,942 lines).
- [ ] Write a smoke test: `python -c "from ui.console.action_registry import list_groups; assert len(list_groups()) == 5"` (5 groups per `GROUPED_CHOICES`'s current shape — confirmed via codegraph 2026-07-11: LBPH, Eigenfaces, Fisherfaces, Hybrid, Benchmark, 38 actions total).

### 2.4 Terminal relay route

- [ ] `ui/console/routes/terminal.py` — `GET /terminal` (Jinja2 page embedding
      vendored xterm.js) and `WS /api/terminal`.
- [ ] WebSocket handler: on connect, `subprocess.Popen([sys.executable, "main.py"],
      stdin=PIPE, stdout=PIPE, stderr=STDOUT, text=True, bufsize=1, cwd=PROJECT_ROOT,
      env=<inherit + PYTHONPATH as main.py's own build_subprocess_env does>)`. Spawn
      two tasks: one reading `proc.stdout` line-by-line and forwarding to the
      WebSocket, one reading WebSocket messages and writing to `proc.stdin` (+
      flushing). Close cleanly on `proc.poll() is not None`.
- [ ] **Process-group termination for Cancel**, cross-platform (Windows dev box today,
      Termux/Linux later, per `AGENTS.md`):
  - POSIX: spawn with `start_new_session=True`, cancel via
    `os.killpg(os.getpgid(proc.pid), signal.SIGTERM)`.
  - Windows: spawn with `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`, cancel via
    `proc.send_signal(signal.CTRL_BREAK_EVENT)` (plain `.terminate()` as a fallback if
    the child doesn't honor `CTRL_BREAK_EVENT` within a short timeout).
  - Branch on `os.name` at the call site; both paths tested manually per this phase's
    Definition of Done.

### 2.5 Bind-host enforcement

- [ ] Confirm `ui/console/app.py`'s `uvicorn.run(..., host="127.0.0.1", ...)` call has
      no env-var or CLI-flag override path in this phase (per `DESIGN.md` §5.5's
      hardening note) — grep the file for `os.environ` / `argparse` touching `host`
      before considering this step done; there should be none.
- [ ] `GET /api/health` route returning `{"status": "ok", "bound_host": "127.0.0.1"}`
      per the contract in `DESIGN.md` §5.6.

### Phase 2 — Definition of done

- [ ] `python -m uvicorn ui.console.app:app --port 8756` starts, and
      `curl http://127.0.0.1:8756/api/health` returns the expected JSON.
- [ ] `curl http://<this-machine's-LAN-IP>:8756/api/health` from another device on the
      same network **fails to connect** (proves the bind is actually loopback-only,
      not just documented as such).
- [ ] Opening `/terminal` in a browser, typing the number for an LBPH `evaluate` menu
      choice, and pressing Enter runs `main.py`'s existing interactive flow to
      completion, with output visibly streaming into the xterm.js widget in real time
      (not appearing all at once at the end).
- [ ] Clicking Cancel mid-run actually kills the subprocess (verify via OS task
      manager / `ps`, not just that the UI stops showing output) on the current dev
      machine (Windows) — Termux/Linux path can be verified opportunistically when
      next on that machine, per `AGENTS.md`'s dual-environment note.

---

## Phase 3 — Console: guided forms

**Prerequisite: Phase 2 complete** (forms submit through the same execution/streaming
plumbing built there — §5.3's "same WebSocket mechanism as the terminal tab").

### 3.1 Form-field extraction

- [ ] `ui/console/form_fields.py` — for the 4 in-scope model families (LBPH,
      Eigenfaces, Fisherfaces, Hybrid) × {train, evaluate, independence test,
      independence test (light front)}, hand-write the field list mirroring
      `main.py`'s `prompt_core_dataset_args`, `prompt_augmented_dataset_args`,
      `prompt_detector_args` (`main.py:1267` onward). This is the one place a
      hand-maintained table is unavoidable (form widgets need types/defaults/labels
      that `GROUPED_CHOICES` alone doesn't carry) — but keep the **action set** (which
      model×action combos exist) sourced from `action_registry.py` (2.3), and add the
      assertion from `DESIGN.md` §5.2: a test that every `(model, action)` pair in
      `form_fields.py` is a subset of `action_registry.list_groups()`'s pairs, so a
      typo'd or removed `main.py` action fails CI/a local check instead of drifting
      silently.
- [ ] `GET /api/actions/form-fields` route per the contract in `DESIGN.md` §5.6.

### 3.2 Trained-model check

- [ ] `ui/console/model_status.py` — scans `models/<family>/*.{yml,onnx}` +
      `models/<family>/labels_*.json`, exposes `GET /api/models/trained` per
      `DESIGN.md` §5.6.
- [ ] Before submitting an evaluate/independence-test form, call the equivalent of
      `main.py`'s `warn_if_missing_auto_artifacts` (`main.py:832`) against the
      submitted `--model-path`/`--labels-path`/`--enrollment-path` values; surface any
      warning in the form UI before the run starts (not just print it to the log after
      the subprocess is already running).

### 3.3 Forms page + submission

- [ ] `ui/console/templates/forms.html` (Jinja2) — per-model tabs, field widgets
      generated from `form_fields.py`'s type info (`path` → text input + "browse
      existing" dropdown sourced from 3.2; `int`/`float` → number input; `flag` →
      checkbox).
- [ ] `POST /api/runs` route: builds argv exactly as `run_choice` (`main.py:1738`)
      would — `[*get_python_command(), str(resolve_path(rel_script)), *args]` — and
      reuses the **same** subprocess-spawn + WebSocket-streaming code path built in
      2.4, not a second implementation. Single-slot queue: reject with `409` if a run
      is already active (mirrors `build_subprocess_env`'s BLAS/OpenMP-thread-capping
      rationale in `main.py:1713` — DESIGN.md §5.3).

### 3.4 Run history

- [ ] `ui/console/run_history.py` — append-only JSON-lines file
      `ui/console/run_history.jsonl` (simplest option per `DESIGN.md` §5.3; upgrade to
      SQLite only if the JSONL file's line count becomes a real scroll-performance
      problem in the `/api/runs` history route). Each line: `{run_id, model, action,
      argv, start, end, exit_code}`.
- [ ] `GET /api/runs` and `GET /api/runs/{run_id}` routes per `DESIGN.md` §5.6.
- [ ] Add `ui/console/run_history.jsonl` to `.gitignore` (this is local run-log data,
      explicitly **not** part of the manifest that reaches Vercel — `DESIGN.md` §5.3).

### Phase 3 — Definition of done

- [ ] From `/forms`, submitting an LBPH "evaluate" form with valid paths starts a run,
      streams output live, and appends one entry to `run_history.jsonl` with the
      correct `exit_code`.
- [ ] Submitting an "evaluate" form pointing at a `--model-path` that doesn't exist
      surfaces the missing-artifact warning in the UI **before** the subprocess starts.
- [ ] Submitting a second form while one run is active gets a `409`, not a second
      concurrent process (verify via task manager that only one Python child process
      of the submitted script exists at a time).
- [ ] `GET /api/runs` returns the history list and matches what's in
      `run_history.jsonl`.

---

## Phase 4 — Stretch: live-detect stats, raw-results browser

Optional; only start once Phases 0-3 are stable and someone actually wants these.

### 4.1 Live-detect stat surfacing

- [ ] `ui/console/live_detect.py` — launching a `live detect` action (any of the 4
      `cv.imshow`-using scripts: `src/{lbph,eigenfaces,fisherfaces,hybrid}/detect.py`)
      through the same `/api/runs` path as any other action, but additionally polling
      the `fps_summary_dir` JSON (or `session_log_json` if the form specifies one) and
      pushing parsed stats as extra WebSocket frames (`{"type": "stat", "fps": ...,
      "recognition_fps": ...}`) alongside the raw stdout lines.
- [ ] On a headless machine, `cv.imshow`/`cv.VideoCapture` failures surface as a
      distinct, clearly-labeled error in the run's log (not swallowed) — confirms
      `DESIGN.md` §5.4's "surface the gap, don't hide it" intent is actually
      implemented, not just described.

### 4.2 Raw results browser (dashboard, `/results`)

- [ ] `ui/dashboard/app/results/page.tsx` — table/JSON toggle over
      `content/results/**/summary.json` (copied in Phase 0.6). No re-plotting, no new
      analytics — table view of existing JSON fields only, per `DESIGN.md` §6.4's
      explicit scope limit.

### Phase 4 — Definition of done

- [ ] Launching a live-detect action from the console on the current (Windows, has a
      webcam) machine shows FPS numbers updating in the browser during the run.
- [ ] Launching the same action in a way that simulates no display (or documenting
      what happens on Termux next time that environment is available) shows a clear
      error message in the console UI rather than a silent hang.
- [ ] `/results` on the deployed dashboard lists every tracked `summary.json` and can
      render at least one full leg's contents as a table.
