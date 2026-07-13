# DL-track fix plan — consistency & soundness with the classical track

**Date:** 2026-07-09. **Status:** plan only — no `face-detection-g3-dl/` code has been
changed. The DL track is untracked by git, hardcodes `D:/FILES/PROGRAMMING/...` paths,
and its datasets are not reachable from this machine, so it cannot be edited or re-run
here. This document is the executable spec for whoever runs it on the DL machine.

Companion to the read-only audit
[`docs/audits/2026-07-09_dl_track_detection_gap.md`](audits/2026-07-09_dl_track_detection_gap.md),
which diagnosed *why* the DL track appears to miss faces the classical track "keeps."
That audit's conclusion stands: the symptom is a threshold/pipeline artifact, not a
YuNet weakness. This plan turns that plus four additional issues found while verifying
it into concrete edits.

All file paths below are in the sibling repo **`face-detection-g3-dl/`** unless prefixed
otherwise. Line numbers are as of 2026-07-09.

---

## Guiding principle

The classical repo (`face-detection-g3/`) has already been audited for correctness,
consistency, and statistical honesty (see
[`docs/audits/2026-07-08_improvement_spec_implementation.md`](audits/2026-07-08_improvement_spec_implementation.md)).
It even contains a **sound SFace-based independence test already** —
[`src/hybrid/independence_test.py`](../src/hybrid/independence_test.py) uses
`create_face_detector("yunet")` (inherits the validated `0.6` threshold),
`SFaceRecognizer()`, `detect_largest`, and incremental pair accumulation. The DL track
should be brought up to that same standard rather than inventing a new one. The mapping:

| DL-track gap | The classical repo already does it right in |
|---|---|
| Detects at `0.9`, no fallback | `src/classical_faces/detection.py:48` (`DEFAULT_YUNET_SCORE_THRESHOLD = 0.6`); `src/hybrid/independence_test.py:557` |
| Uses `faces[0]` (highest score) | `detect_largest` / `detect_largest_face_box` (largest box) — `src/classical_faces/preprocess.py` |
| Silently drops missed faces | Wilson-interval / honest-drop accounting — `2026-07-08` log §B1, `docs/presentation/independence_test_expansion/PITCH_OUTLINE.md` |
| Counts ordered N×(N−1) pairs | Unique-pair convention with `assert n % 2 == 0` — `src/independence_common.py:error_pair_report_from_topk` |
| SFace independence, end to end | `src/hybrid/independence_test.py` (the reference to mirror) |

---

## Priority tiers

### P0 — soundness (can invalidate a headline number)

**P0.1 — Verify the LFW 1:1 test is not comparing each image to itself.**
[`dnn.py:63-88`](../../face-detection-g3-dl/dnn.py) loads the gallery from
`features-lfw.npy`, then extracts the probe from `{person}_0001.jpg` and compares them.
If `features-lfw.npy` was *also* built from `_0001.jpg` (there is no other selection
logic, and the comment at `dnn.py:24` literally says *"trigger your 'Training=Testing'
logic"*), then every genuine comparison is an image against **itself** → distance ≈ 0 →
`tp_percent` is a meaningless 100%.

- **Action:** find/confirm the script that built `features-lfw.npy` and check which image
  per identity it used. If it is `_0001.jpg`, the 1:1 genuine test is a self-match and
  must be re-designed to be **image-disjoint** (gallery from one image, probe from a
  different image of the same identity — LFW identities with ≥2 images only), exactly the
  closed-set protocol the classical track adopted (`2026-07-08` log §A6).
- **Until confirmed, do not report the DL LFW TP number.**

**P0.2 — Select the *largest* face, not `faces[0]`.**
YuNet returns faces ordered by detection score, so `faces[0]` is the highest-confidence
face, not the largest. On LFW news photos with background bystanders this can enroll or
probe the **wrong person**; the classical track always uses the largest box, so the two
tracks currently disagree on which face they even look at.

- [`feature-extract.py:30`](../../face-detection-g3-dl/feature-extract.py) and
  [`dnn.py:74`](../../face-detection-g3-dl/dnn.py): replace `faces[0]` with the
  largest-area row. YuNet rows are `[x, y, w, h, ...5 landmarks..., score]`, so:
  ```python
  # faces: (N, 15); columns 2,3 are w,h
  largest = faces[int(np.argmax(faces[:, 2] * faces[:, 3]))]
  aligned = recognizer.alignCrop(img, largest)
  ```
  This matches `detect_largest` in the classical pipeline and makes the two tracks pick
  the same face.

### P1 — consistency with the classical repo's validated configuration

**P1.1 — Align the YuNet score threshold to `0.6`** (the audit's headline
recommendation).
- [`dnn.py:38`](../../face-detection-g3-dl/dnn.py): `default=0.9` → `default=0.6`.
- [`feature-extract.py:10`](../../face-detection-g3-dl/feature-extract.py): the bare
  `cv.FaceDetectorYN.create(YUNET_PATH, "", YUNET_IMG_SIZE)` inherits OpenCV's built-in
  `0.9`. Pass the threshold explicitly:
  ```python
  detector = cv.FaceDetectorYN.create(YUNET_PATH, "", YUNET_IMG_SIZE, 0.6, 0.3)
  ```
  `0.6`/`0.3` are `DEFAULT_YUNET_SCORE_THRESHOLD` / `DEFAULT_YUNET_NMS_THRESHOLD` from
  `face-detection-g3/src/classical_faces/detection.py:48-49`.

**P1.2 — Fix the SFace `config` argument.**
[`dnn.py:59`](../../face-detection-g3-dl/dnn.py) passes `IMG_NAME`
(`"light_front__orig.jpg"`) as SFace's second positional argument, which is the network
*config* path, not an image name. The other two scripts already pass `""`
([`feature-extract.py:11`](../../face-detection-g3-dl/feature-extract.py),
[`ldb2-independence.py:14`](../../face-detection-g3-dl/ldb2-independence.py)). Change to:
```python
recognizer = cv.FaceRecognizerSF.create(args.face_recognition_model, "")
```
Harmless for the ONNX backend today, but it is an inconsistency and a latent bug.

### P2 — honest accounting (the audit's statistical-validity point)

**P2.1 — Persist dropped images instead of `print()`.**
[`feature-extract.py:40`](../../face-detection-g3-dl/feature-extract.py) and the
equivalent branch in [`dnn.py`](../../face-detection-g3-dl/dnn.py) send misses only to
stdout. Silently dropping the *hardest* examples before computing the false-positive rate
inflates the DL track's numbers relative to the classical track (which drops nothing).
Collect `{img_path, reason}` into a list and write it alongside the `features-*.npy`
(e.g. `skipped-<dataset>.json`) with a printed skip count, so the skip rate is a
reportable number.

**P2.2 — Count unique impostor pairs, not ordered ones.**
The N×(N−1) loops ([`dnn.py:95-116`](../../face-detection-g3-dl/dnn.py),
[`ldb2-independence.py:24-44`](../../face-detection-g3-dl/ldb2-independence.py)) count
each unordered pair twice. SFace's match is symmetric, so `fp_percent` (a ratio) is
unaffected, but `n_fp` and `pairs_fp` are doubled and every false-positive pair is listed
twice (A-vs-B and B-vs-A). Either iterate `j in range(i+1, N)` or de-duplicate `pairs_fp`,
matching the classical track's unique-pair convention
(`src/independence_common.py`, which even `assert`s `n % 2 == 0`).

**P2.3 — Stop mislabeling the plots.**
[`loader.py:18`](../../face-detection-g3-dl/loader.py) and
[`loader.py:53`](../../face-detection-g3-dl/loader.py) always save
`frequency_distance_plot_lfw.png` / `fp_top3_lfw.png`. The LaSalle-DB2 run
([`ldb2-independence.py:61-62`](../../face-detection-g3-dl/ldb2-independence.py))
therefore overwrites the **LFW** plots with DB2 data under an LFW filename. Add a
`dataset` argument to `plot()` / `plot_fp_images()` and build the filename from it so each
run's figures are correctly named.

### P3 — reproducibility (not a results bug, but blocks trust/replication)

- Put `face-detection-g3-dl/` under git; add a `.gitignore` for `venv/`, `__pycache__/`,
  and the generated `features-*.npy` / `results-*.json` / `*.png`; remove the committed
  `venv/`.
- De-hardcode the absolute `D:/FILES/PROGRAMMING/face-detection/...` paths
  ([`dnn.py:10-11`](../../face-detection-g3-dl/dnn.py),
  [`loader.py:6`](../../face-detection-g3-dl/loader.py),
  [`loader.py:58`](../../face-detection-g3-dl/loader.py)) behind a CLI flag / env var with
  a relative default, so the track runs from a clean clone.
- Document the recognizer operating point (`cosine ≥ 0.363`, `L2 ≤ 1.128` — OpenCV's
  published SFace thresholds) and its provenance in a short report, for parity with the
  classical track's documented threshold derivation.

---

## Measured re-runs (do after the code edits, on the DL machine)

Changing the threshold and face-selection makes every committed `features-*.npy` /
`results-*.json` **stale** — they are the outputs of a specific `0.9` + `faces[0]` run.
Regenerate them, in order:

1. `python feature-extract.py` → rebuilds `features-lasalledb2.npy` at `0.6`, with the
   skip log from P2.1.
2. Re-run the LFW / DB2 independence scripts (`dnn.py`, `ldb2-independence.py`) to refresh
   `results-*.json` and the (now correctly-named) plots.
3. **Quantify the before/after** the audit asked for. The classical benchmark tool now
   supports a clean threshold sweep without clobbering its own output (see the CV-side
   change below), so run it on the actual heavy/blurred split:
   ```bash
   # in face-detection-g3/
   python src/benchmark/compare_detectors.py --dataset <abs path to heavy split> --yunet-score-threshold 0.6
   python src/benchmark/compare_detectors.py --dataset <abs path to heavy split> --yunet-score-threshold 0.9
   ```
   → `reports/benchmark/detector_comparison_<set>.md` (0.6) and
   `..._yunet0.9.md` (0.9). The recall delta between the two is the hard number for the
   paper, replacing the audit's inference-from-separate-runs.

---

## Already done on the classical (CV) side

To enable step 3 above soundly, one CV-repo change was made and verified on
`data/lasalle_db1_processed` (2026-07-09):

- `face-detection-g3/src/benchmark/compare_detectors.py`: a non-default
  `--yunet-score-threshold` now stamps the threshold into the default output filename
  (`..._yunet0.9.json/.md`), so a `0.9`-vs-`0.6` sweep on the same dataset no longer
  silently overwrites its own canonical `0.6` report. The markdown provenance line now
  prints the real dataset directory and the YuNet threshold used, instead of a hardcoded
  `data/<name>`, so each report is self-describing. Backward compatible: at the default
  `0.6` the canonical filename is unchanged.

No other classical-track code was changed — the `2026-07-09` audit correctly found the
rest of that track sound by design (notably, do **not** change
`ASSUME_INPUTS_ARE_CROPPED`; it is a deliberate clean-loop choice).

---

## Checklist

- [ ] P0.1 Confirm/curb the LFW self-match; do not report DL LFW TP until resolved
- [ ] P0.2 `faces[0]` → largest-area face (`feature-extract.py`, `dnn.py`)
- [ ] P1.1 YuNet threshold `0.9` → `0.6` (`dnn.py:38`, `feature-extract.py:10`)
- [ ] P1.2 SFace `config` arg `IMG_NAME` → `""` (`dnn.py:59`)
- [ ] P2.1 Persist dropped-image log (`feature-extract.py`, `dnn.py`)
- [ ] P2.2 Unique-pair counting (`dnn.py`, `ldb2-independence.py`)
- [ ] P2.3 Dataset-tagged plot filenames (`loader.py`)
- [ ] P3   git-track, de-hardcode paths, drop committed `venv/`
- [ ] Re-runs Regenerate `features-*.npy` / `results-*.json`; run the 0.6-vs-0.9 heavy-split benchmark
