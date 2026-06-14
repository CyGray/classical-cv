# Face Detector Comparison — Viola-Jones (Haar) vs YuNet

*Classical CV track, Group 3. Companion to `docs/SPEC_COMPARISON.md`. Detector
stage of the 7-stage pipeline (`docs/READ THIS/BRIEFING.md` §3, milestone
"face-detection selection ~6/16").*

This report covers the new **toggle-able face detector** for the classical
recognizers and the head-to-head measurements that motivate it. The recognizers
(LBPH / Eigenfaces / Fisherfaces) historically used **Viola-Jones (Haar cascade)**
for the face-detection stage. They can now run **YuNet** (a small CNN detector)
instead, switched with a single flag, env var, or menu choice — Haar stays the
default, so nothing changes unless you opt in.

---

## TL;DR

- **YuNet detects more faces, with fewer false positives, and runs faster** than
  Haar at the same input resolution on this hardware. On the primary La Salle set
  it found a face in **100% of photos with zero false positives**, vs Haar's
  **86.9% with 43 false positives**.
- **It's a drop-in toggle.** `--detector haar|yunet` on every
  `trainer.py` / `evaluate.py` / `detect.py`, a global `FACE_G3_DETECTOR` env
  var, and a prompt in `python main.py`. Default is **Haar** ("for now").
- **The headline recognition number is unaffected.** The clean held-out La Salle
  loop feeds pre-cropped 100×100 tiles (`--assume-cropped`), which skip detection
  entirely — so the detector choice only changes the **raw-photo** and **live
  webcam** paths, which is exactly where it matters for the Smart Gate.
- YuNet also emits a **confidence score** and **5 facial landmarks** (eyes, nose,
  mouth corners) that Haar cannot, opening the door to landmark-based alignment.

---

## 1. Background

| | Viola-Jones (Haar cascade) | YuNet |
|---|---|---|
| Type | Hand-crafted Haar features + AdaBoost cascade (2001) | Compact CNN (libfacedetection, 2023) |
| OpenCV API | `cv.CascadeClassifier` | `cv.FaceDetectorYN` |
| Weights | `haar/haarcascade_frontalface_default.xml` (~941 KB) | `models/yunet_mobilefacenet/face_detection_yunet_2023mar.onnx` (~227 KB) |
| Output | Bounding boxes only | Boxes **+ confidence + 5 landmarks** |
| Designed for | Upright frontal faces | Arbitrary pose / scale / lighting |
| Colour | Grayscale | Colour (BGR) |

The YuNet ONNX is already vendored in this repo (shared with the
`yunet_mobilefacenet` deep-learning track), so no new download is required.

---

## 2. How to toggle (the "easily switchable" part)

The detector backend resolves in this order: **explicit CLI flag → `FACE_G3_DETECTOR`
env var → `haar`**.

| Surface | Use Haar (default) | Use YuNet |
|---|---|---|
| **Per-run CLI flag** | `--detector haar` (or omit) | `--detector yunet` |
| **Global env var** (Git Bash) | `unset FACE_G3_DETECTOR` | `export FACE_G3_DETECTOR=yunet` |
| **Global env var** (PowerShell) | `Remove-Item Env:FACE_G3_DETECTOR` | `$env:FACE_G3_DETECTOR='yunet'` |
| **Launcher** `python main.py` | choose `1. Haar` at the prompt | choose `2. YuNet` at the prompt |

The flag is exposed on all classical `trainer.py`, `evaluate.py` and `detect.py`
scripts. Two YuNet knobs are also available: `--yunet-score-threshold` (default
`0.6`) and `--yunet-nms-threshold` (default `0.3`), plus `--yunet-model-path` to
point at alternate weights.

Examples:

```bash
# Evaluate LBPH on raw La Salle with YuNet detection
python src/lbph/evaluate.py --no-assume-cropped --include-raw \
  --base-data-dir data --raw-dir-name lasalle_db1 --detector yunet

# Live LBPH webcam loop with YuNet
python src/lbph/detect.py --detector yunet

# Make YuNet the default everywhere for this shell
export FACE_G3_DETECTOR=yunet
python main.py
```

Every evaluation report now records which backend ran, under
`config.detector_backend` / `config.detector_detail` and `detection.detector_backend`,
so results are self-describing and never silently mixed.

### Where it plugs in

A single tiny interface, `src/classical_faces/detection.py`, hosts both backends:

```
FaceDetector.detect(gray, bgr) -> [Detection(box, score, landmarks)]
              .detect_largest(gray, bgr) -> (x, y, w, h) | None
   ├── HaarFaceDetector   (wraps cv.CascadeClassifier)
   └── YuNetFaceDetector  (wraps cv.FaceDetectorYN)
   create_face_detector("haar"|"yunet", ...)   # factory
```

Because both return the largest face as a plain `(x, y, w, h)` box in
full-resolution coordinates, they are interchangeable for every stage. The shared
preprocessing (`extract_classical_face`) and the pipeline (`build_detectors`)
take a detector object; the legacy raw-cascade call path still works unchanged
(it is wrapped into a `HaarFaceDetector` internally), so the independence-test and
benchmark scripts were not touched.

---

## 3. Methodology

- **Datasets** (both are single-face-per-image, so a miss is a false negative):
  - **La Salle DB1** — the project's primary set: all **336** raw photos (28
    subjects × 12 poses/lighting: `{light,dark}_{front,left,right,up,down,name}`),
    native **6928×6928 px**, controlled capture, plain background.
  - **LFW** — **600**-image random sample (seed 42) of the 13,233 in-the-wild
    news photos, native **250×250 px**.
- **Input resolution.** Each image is downscaled to a **640 px** longest side
  before detection (mirrors the live loop and keeps both detectors fast and fair);
  LFW is already smaller, so it is unchanged.
- **Timing.** Detection time is measured **separately from image decode**.
  Decoding one 48 MP La Salle JPEG averages **~203 ms** — far more than detection
  itself — so the speed column reflects the detector, not disk I/O. Single-thread
  CPU, same machine, both backends on identically decoded frames.
- **Metric meanings** (single-face images):
  - *Detection rate* = images with ≥1 detected face = **recall** proxy.
  - *Exactly-one rate* = images with precisely one box.
  - *Extra detections* = Σ `max(0, faces − 1)` = a **false-positive proxy** on
    controlled data (see the LFW caveat in §5).
- Reproduced by `src/benchmark/compare_detectors.py` →
  `reports/benchmark/detector_comparison_<dataset>.{json,md}`.

---

## 4. Comparison table — all important metrics

Master table (higher is better unless noted; **bold** = better backend per column):

| Metric | La Salle · Haar | La Salle · YuNet | LFW · Haar | LFW · YuNet |
|---|---:|---:|---:|---:|
| Images | 336 | 336 | 600 | 600 |
| **Detection rate** (recall) | 86.9% | **100.0%** | 98.7% | **100.0%** |
| Exactly-one-face rate | 75.3% | **100.0%** | **92.2%** | 83.0% † |
| Extra detections (count) | 43 | **0** | 46 | 128 † |
| Images w/ extra box (FP proxy ↓) | 11.6% | **0.0%** | 6.5% | 17.0% † |
| Mean detection time (↓) | 26.9 ms | **20.6 ms** | 7.8 ms | **2.8 ms** |
| Throughput (detection only) | 37.2 fps | **48.6 fps** | 128.8 fps | **359.1 fps** |
| Mean detected face size | 1217 px | 1176 px | 115 px | 109 px |
| Mean confidence | n/a | 0.937 | n/a | 0.928 |
| 5-point landmarks | no | **yes** | no | **yes** |
| Model file size (↓) | 941 KB | **227 KB** | 941 KB | **227 KB** |
| ≥30 fps (detection)? | yes | yes | yes | yes |

† **LFW caveat:** LFW photos are in-the-wild news images that frequently contain
**real bystanders** in the background. YuNet's higher "extra" count on LFW is
largely *genuine secondary faces it correctly finds and Haar misses* — not false
positives. On the **controlled** La Salle set (one subject, plain background) the
extra-detection column is a clean false-positive measure, and there YuNet scores
a perfect **0**. The recognizer always uses the **largest** face, so secondary
faces do not corrupt single-subject recognition.

### Capability matrix (qualitative)

| Capability | Haar | YuNet |
|---|:--:|:--:|
| Detects upright frontal faces | ✅ | ✅ |
| Robust to pose (profile / tilt / up-down) | ⚠️ weak | ✅ |
| Robust to low light / harsh light | ⚠️ weak | ✅ |
| Confidence score per face | ❌ | ✅ |
| Facial landmarks (for alignment) | ❌ | ✅ (5 pts) |
| Training-free, deterministic | ✅ | ✅ |
| No external weights beyond repo | ✅ | ✅ (vendored) |
| CPU real-time | ✅ | ✅ |

---

## 5. Discussion

**La Salle (controlled, primary set).** This is the decisive comparison. With
identical inputs, **YuNet found every face (100%) with zero false positives**,
while Haar missed **13.1%** of faces and fired **43 false boxes** (an 11.6%
false-positive rate). Haar's misses concentrate on the non-frontal poses
(`left`/`right`/`up`/`down`) and the `dark_*` lighting — precisely the variation a
Smart Gate must tolerate — whereas the `front`/`name` frontal shots are easy for
both. YuNet was also **~30% faster** (20.6 vs 26.9 ms) and its model file is
**~4× smaller** (227 KB vs 941 KB).

**LFW (in-the-wild).** On easy 250×250 frontal crops both detectors essentially
saturate recall (Haar 98.7%, YuNet 100%), and YuNet is **far faster** (359 vs 129
fps). YuNet reports more boxes per image, but as noted these are mostly real
background people; this is a property of the dataset, not a YuNet weakness.

**Integrated pipeline check.** Running the real LBPH evaluator on raw La Salle
(detection ON) end-to-end confirmed the toggle: Haar yielded **89.3%** detection
(50/56 sampled), YuNet **100%** (56/56), with `detector_backend` correctly
recorded in each report. (Recognition accuracy there is not meaningful — the clean
model is trained on cropped tiles — but it proves the wiring.)

**Speed context.** At a 640 px detection size both detectors clear the 30 fps
detection target comfortably, so **the face detector is not the FPS bottleneck**
for the classical recognizers. For the huge raw La Salle photos, JPEG *decode*
(~203 ms) dominates end-to-end latency far more than either detector.

---

## 6. Recommendation

- **Use YuNet for the raw-photo and live (Smart Gate) paths.** It strictly
  dominates Haar here: higher recall, fewer false detections, faster, smaller
  model, and it adds landmarks + confidence. This directly serves the
  detection-selection milestone (~6/16).
- **Keep Haar as the default for now** (per the request) so existing runs and
  docs reproduce unchanged; switch per-run with `--detector yunet` or globally
  with `FACE_G3_DETECTOR=yunet`.
- **No change to the clean-split headline.** The leakage-free rank-1 numbers in
  `SPEC_COMPARISON.md` come from pre-cropped tiles and never invoke a detector, so
  they remain comparable across this change.
- **Next step (out of scope here):** feed YuNet's 5 landmarks into a
  similarity-transform alignment, replacing the unreliable Haar-eye alignment at
  small sizes. The landmarks are already returned by `YuNetFaceDetector`.

---

## 7. Reproduce

```bash
# Detector benchmark (writes reports/benchmark/detector_comparison_<dataset>.{json,md})
python src/benchmark/compare_detectors.py --dataset lasalle_db1
python src/benchmark/compare_detectors.py --dataset lfw-dataset --max-images 600
# or via the launcher: main.py -> Benchmark -> "compare detectors (haar vs yunet)"
```

Tunables: `--downscale-max-side` (default 640), `--min-face-size` (20),
`--max-images` (0 = all), `--yunet-score-threshold` (0.6), `--random-seed` (42).

---

## 8. Limitations & honesty notes

- Numbers are **measured**, not estimated, on the dev machine; absolute fps will
  differ on a Raspberry Pi 5 — but the **relative** ordering (YuNet faster + more
  accurate at equal input size) should hold. No on-Pi numbers are claimed yet.
- "Detection rate" assumes a findable face exists per image (true for both sets);
  it is recall, not a PASCAL-style IoU accuracy (no ground-truth boxes are
  annotated for these datasets).
- The LFW "extra detections" conflate genuine bystanders with false positives;
  La Salle is the clean false-positive measure. Stated explicitly so the table is
  not over-read.
- This compares the **detection** stage only. Recognition accuracy, TAR@FAR, and
  the independence threshold are separate deliverables and are unchanged by the
  detector toggle on the cropped clean loop.
```
