# Batch campaign — member guide

You have been assigned a small slice of a much larger face-recognition test.
This page tells you exactly what to run and what to send back. No CV/ML
background needed.

## 1. What you need

- The repo, cloned at the commit Kyle gives you (he will tell you the exact
  commit hash; do not use a different one).
- Python 3.10 or newer.
- About 1 GB of free disk space (LFW download plus your results).
- Internet access, at least for the first run (LFW downloads once, about
  173 MB).

## 2. One-time setup

From the repo root:

```
python -m pip install -r requirements-batch.txt
```

This installs the exact pinned `numpy` / `opencv-contrib-python` /
`matplotlib` versions. Do not substitute other versions — the worker
checks these on every run and refuses to continue if they don't match.

## 3. Run your batch

```
python scripts/lfw2_worker.py --member <your_name>
```

Replace `<your_name>` with the name Kyle gave you (must match a key in
`docs/BATCH_WORK/assignments.json`).

The script runs in phases and prints one line per phase:

- `[PHASE] PREFLIGHT` — checks your Python/numpy/opencv versions and the
  pinned model/threshold files against `docs/BATCH_WORK/batch_pins.json`.
  If this fails, **stop and send Kyle the exact error** — see section 6.
- `[PHASE] DATASET` — downloads/verifies the LFW dataset if it isn't
  already present (about 173 MB, one time only).
- `[PHASE] CANARY` — a small fixed timing/sanity sweep. This tells Kyle
  how fast your machine is; it also catches setup problems early.
- `[PHASE] UNIT ...` — your actual assigned work, one line per assigned
  (variant, segment). This is the part that takes real time.
- `[PHASE] PACKAGE ...` — zips up your results.

If the script is interrupted (crash, closed terminal, power loss), just run
the exact same command again. Finished phases print `[SKIP] ... already
done` and are not redone — only the interrupted part resumes.

### How long will it take?

There is no fixed number — it depends entirely on your machine. The canary
phase measures your machine's actual speed and records it; Kyle uses that
to size everyone's workload. Do not extrapolate a runtime yourself; let the
canary tell the real story.

## 4. Where results go

Everything lands under `reports/batch_results/` (or wherever you passed via
`--results-dir`):

```
reports/batch_results/
  canary/                 (timing/sanity run)
  <variant>_seg<i>of<N>/  (your assigned work, one folder per unit)
  uploads/                (the zips you actually send to Kyle)
```

## 5. What to send Kyle

Every file under `reports/batch_results/uploads/*.zip`. One zip per
assigned unit, named like:

```
systematic_lfw2_2026-07_motion_blur_5_seg3of8_<your_name>.zip
```

Upload these (Drive, however Kyle asks) and let him know they're up. Do not
edit, rename, or re-zip them — the merge step checks their contents.

## 6. If PREFLIGHT (or anything else) fails

**Do not try to fix it yourself** — do not edit thresholds, models, or the
pinned files, and do not install a different numpy/opencv version to make
the check pass. Silently-different inputs are exactly what this pinning is
meant to prevent.

Instead:

1. Copy the full error message the script printed.
2. Send it to Kyle along with what command you ran.
3. Wait for instructions before re-running.

## 7. FAQ

**Can I close the terminal partway through?** Yes — see the resume note in
section 3. Just re-run the same command later.

**Can I run this on a laptop that sleeps overnight?** If your OS pauses the
process during sleep it will just resume when you wake it; if it kills the
process, re-run the same command and it resumes from the last completed
phase.

**Do I need a GPU?** No. Everything here runs on CPU by design (mixing
GPU and CPU backends across members would introduce numeric drift the
pinning is meant to prevent).
