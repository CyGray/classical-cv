# `ui/` — Study Dashboard & Run Console

Two small, independent apps (design: [`docs/ui/DESIGN.md`](../docs/ui/DESIGN.md), plan:
[`docs/ui/BUILD.md`](../docs/ui/BUILD.md)). They do **not** talk to each other over the
network — a person running `build_study_manifest.py` is the only bridge.

```
ui/
  dashboard/   Next.js, read-only, deploys to Vercel — "where are we?" for the whole team
  console/     FastAPI, localhost-only — run main.py's actions from a browser tab
```

## A. Researcher Dashboard (`ui/dashboard/`)

Read-only mirror of the study: status, paper coverage, docs, figures. Static export —
no server, no API, nothing runs from the public URL.

**Update its data, then run locally:**

```bash
# 1. Edit the hand-maintained source of truth when a run finishes or the paper changes:
#    docs/ui/study_status.yml
# 2. Regenerate the manifest + copy docs/figures/results into the dashboard:
python scripts/build_study_manifest.py
# 3. Preview:
cd ui/dashboard
npm install        # first time only
npm run dev        # http://localhost:3000
npm run build      # static export into ui/dashboard/out/
```

`data/manifest.json`, `content/**`, and `public/figures/**` are **generated but committed**
(so Vercel's shallow clone has them). Re-run step 2 whenever `study_status.yml` or the
underlying `reports/`/`docs/` change. Deploy notes: [`ui/dashboard/README.md`](dashboard/README.md).

## B. Local Run Console (`ui/console/`)

Runs on `127.0.0.1:8756` only, on whichever machine is doing the work. Wraps `main.py`.

```bash
# from the repo root:
python -m ui.console
#   or: python -m uvicorn ui.console.app:app --host 127.0.0.1 --port 8756
```

Then open <http://127.0.0.1:8756>:

- **Terminal** — `main.py`'s own interactive menu, streamed live, with Stop/Restart.
  Full coverage of all 38 actions; it *is* the menu, unmodified.
- **Forms** — guided forms for train / evaluate / independence tests across LBPH,
  Eigenfaces, Fisherfaces, and Hybrid. Builds the same argv the menu would, streams
  output live, enforces one-run-at-a-time, and records history to
  `run_history.jsonl` (gitignored).

The bind host is a hardcoded literal (`127.0.0.1`) — never reachable off the machine.
Run history is local only and never travels to the dashboard.

Deps (already in [`requirements.txt`](../requirements.txt)): `fastapi`, `uvicorn[standard]`,
`jinja2`, `PyYAML`.
