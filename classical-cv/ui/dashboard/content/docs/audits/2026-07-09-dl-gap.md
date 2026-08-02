# Audit: DL-track detection misses under heavy blur/rotation vs. classical

**Date:** 2026-07-09. Investigates a reported discrepancy: on the independence tests
(LFW + La Salle "heavy"-condition images), the DL track (`face-detection-g3-dl/` —
YuNet detector + SFace recognizer) fails to detect faces in heavily blurred or rotated
photos, while the classical track (`face-detection-g3/` — LBPH/Eigenfaces/Fisherfaces)
apparently does not. Read-only investigation; no code changed. Scope: the detection
stage only, both projects.

---

## TL;DR

This is not evidence that YuNet/DL detection is worse than classical detection under
degradation. Two pipeline differences compound to produce the symptom:

1. **Classical's independence tests never run a detector at all.** Every LBPH /
   Eigenfaces / Fisherfaces independence test and trainer hardcodes
   `ASSUME_INPUTS_ARE_CROPPED = True` (unanimous, 9/9 files — see Evidence §1). With
   that flag set, the whole input image is treated as the face crop; no detector is
   invoked, so blur/rotation cannot cause a detection failure — there is no detection
   step to fail.
2. **The DL track always runs a real detector, at a stricter threshold, with no
   fallback.** `feature-extract.py` / `dnn.py` call `cv.FaceDetectorYN.detect()` on
   every image at `score_threshold=0.9` (§2), and silently drop any image that misses
   (`print("No face detected...")`, `continue` — never reaches SFace, never counted).
   Blur and rotation are exactly the degradations that suppress a genuine face's YuNet
   confidence score below a fixed high bar.

Crucially, this repo already has **measured** evidence that YuNet is not the weak link:
`docs/reports/DETECTOR_COMPARISON.md` shows YuNet at `score_threshold=0.6` (the
classical project's own documented default,
`src/classical_faces/detection.py:48`) **strictly dominates Haar** on the same La
Salle set — 100.0% recall vs. Haar's 86.9%, zero false positives vs. Haar's 43 — and
specifically wins on the non-frontal poses and harsh lighting Haar misses. The DL
track's failures look like a threshold/config gap (0.9, no retry), not a capability
gap.

---

## Evidence

### 1. Classical bypasses detection entirely — confirmed in all 9 test/trainer files

```
src/eigenfaces/trainer_light_front.py:17        ASSUME_INPUTS_ARE_CROPPED = True
src/eigenfaces/independence_test.py:46          ASSUME_INPUTS_ARE_CROPPED = True
src/eigenfaces/independence_test_light_front.py:55  ASSUME_INPUTS_ARE_CROPPED = True
src/lbph/trainer_light_front.py:18              ASSUME_INPUTS_ARE_CROPPED = True
src/lbph/independence_test_light_front.py:55    ASSUME_INPUTS_ARE_CROPPED = True
src/lbph/independence_test.py:48                ASSUME_INPUTS_ARE_CROPPED = True
src/fisherfaces/independence_test.py:46         ASSUME_INPUTS_ARE_CROPPED = True
src/fisherfaces/independence_test_light_front.py:55  ASSUME_INPUTS_ARE_CROPPED = True
src/fisherfaces/trainer_light_front.py:17       ASSUME_INPUTS_ARE_CROPPED = True
```

`src/classical_faces/preprocess.py:199-223` (`extract_classical_face`) shows what the
flag does:

```python
if assume_already_cropped:
    x, y, fw, fh = 0, 0, w, h          # whole image = "the face", no detector call
else:
    ...
    face_box = active_detector.detect_largest(image_gray, image_bgr=image_bgr)
    if face_box is None:
        return FacePreprocessResult(face=None, reason="no_face", detected_face=False, ...)
```

This matches the project's own `docs/reports/DETECTOR_COMPARISON.md:26-28`, which
states plainly: *"The clean held-out La Salle loop feeds pre-cropped 100×100 tiles
(`--assume-cropped`), which skip detection entirely."* So classical's independence
tests are, by construction, immune to detection failure — not because Haar (or
classical's optional YuNet backend) is more robust to blur/rotation, but because they
never look for a face in the first place on this path.

### 2. DL track always detects, at 0.9, with no fallback

`face-detection-g3-dl/dnn.py:38` — explicit CLI default:
```python
parser.add_argument('--score_threshold', type=float, default=0.9)
```
(comment above it: *"These thresholds are taken directly from your project table"* —
i.e. 0.9 is a deliberate, documented operating point for this track, not an oversight.)

`face-detection-g3-dl/feature-extract.py:10` doesn't pass a threshold at all:
```python
detector = cv.FaceDetectorYN.create(YUNET_PATH, "", YUNET_IMG_SIZE)
```
`cv.FaceDetectorYN.create`'s own built-in default for `score_threshold` is also `0.9`,
so this call lands on the same strict bar.

`feature-extract.py:26-40` — the per-image loop, one shot, no retry:
```python
detector.setInputSize((img.shape[1], img.shape[0]))
_, faces = detector.detect(img)

if faces is not None:
    aligned = recognizer.alignCrop(img, faces[0])
    feature = recognizer.feature(aligned)
    features_db2.append({...})
else:
    print(f"No face detected: {img_path}")   # sample silently excluded, nothing logged
```
Same pattern in `dnn.py:68-88` for the LFW 1:1 and N×(N-1) loops. There is no
downscale-and-retry, no threshold relaxation, and no fallback to the full frame — one
`.detect()` call at a fixed 0.9, pass or the image vanishes from the run.

### 3. The 0.9 threshold is inconsistent with this repo's own recommended value

`src/classical_faces/detection.py:48`:
```python
DEFAULT_YUNET_SCORE_THRESHOLD = 0.6
```
This is the *same* vendored ONNX model — `detection.py:167`'s error message calls it
explicitly "shared with the yunet DL track" — used at `0.6` by
`src/benchmark/compare_detectors.py:78` and `src/hybrid/independence_test.py:557`
(`create_face_detector("yunet")`, no override → inherits `0.6`). Nothing in
`face-detection-g3/` runs YuNet at `0.9`; only the standalone DL-track scripts do. A
real face that scores, say, 0.65-0.85 confidence under blur or an off-axis rotation
would pass everywhere in `face-detection-g3/` and be silently rejected only in
`face-detection-g3-dl/`.

### 4. Corroborating measured data already in this repo

`docs/reports/DETECTOR_COMPARISON.md` (Haar vs. YuNet at `score_threshold=0.6`, La
Salle DB1, 336 raw photos across 12 poses/lighting conditions per subject):

| Metric | Haar | YuNet (0.6) |
|---|---:|---:|
| Detection rate (recall) | 86.9% | **100.0%** |
| Images w/ extra box (FP proxy) | 11.6% | **0.0%** |
| Mean confidence | n/a | 0.937 |

Per that report's Discussion (§5): *"Haar's misses concentrate on the non-frontal
poses (left/right/up/down) and the dark_\* lighting — precisely the variation a Smart
Gate must tolerate."* I.e. on the exact category of hard, non-frontal/degraded inputs
this audit is about, YuNet at its documented threshold already measurably beats Haar,
not the other way around. That result plus §§1-3 above is why the DL track's observed
behavior reads as a threshold/pipeline artifact rather than a real YuNet weakness.

---

## What's proven vs. still a hypothesis

**Proven (read from code + existing measured report):**
- Classical's independence tests skip detection entirely (§1).
- The DL track always detects and silently drops misses, no fallback (§2).
- The DL track's threshold (0.9) is stricter than this repo's own validated YuNet
  operating point (0.6) (§3).
- At 0.6, YuNet already beats Haar on non-frontal/harsh-lighting La Salle shots (§4).

**Not yet directly measured (would need a targeted run, not just code reading):**
- `docs/reports/DETECTOR_COMPARISON.md`'s benchmark was run on **undistorted** La
  Salle/LFW photos, not the specific heavily-blurred/rotated variants the DL track
  processes (e.g. the `LaSalleDB1/heavy/` condition folder `loader.py:load_ldb2`
  reads, on `D:/FILES/PROGRAMMING/face-detection/...` — a path local to the DL
  track's own machine, not reachable from this environment to inspect directly).
- No one has yet re-run `compare_detectors.py` at `--yunet-score-threshold 0.9` vs.
  `0.6` specifically on the augmented/heavy-condition images to get a hard before/after
  number for *this* symptom. §§1-4 make the causal story well-supported, but the exact
  recovered-detection-rate delta at 0.6 vs 0.9 on the heavy/blurred set is still an
  estimate, not a measurement.

---

## Secondary findings (not the main issue, worth a line each)

- **No skip bookkeeping in the DL track.** Detection misses only go to `print()` —
  nothing is counted or persisted (no CSV/JSON), so today there's no artifact
  quantifying how many/which images were silently excluded from `features-lasalledb2.npy`
  / `features-lfw.npy`. This also has a statistical-validity angle: silently dropping
  the hardest examples before computing the false-positive rate inflates the DL
  track's apparent numbers relative to classical's (which drops nothing) — the same
  class of concern as the Wilson-interval honesty argument in
  `docs/presentation/independence_test_expansion/PITCH_OUTLINE.md`.
- **`face-detection-g3-dl/` is untracked by git** (confirmed: `git status` inside it
  and inside its parent both report "not a git repository"), hardcodes absolute
  `D:/FILES/PROGRAMMING/face-detection/...` paths (`dnn.py:10-11`, `loader.py:6`,
  `ldb2-independence.py` reads relative `.npy` files produced by such a run), and
  ships a committed `venv/` directory. Not the cause of the detection gap, but it
  means the DL track isn't reproducible from a clean clone or on this machine as-is.

---

## Recommendation

1. **Align the DL track's YuNet threshold to this repo's own validated default
   (`0.6`)** in `dnn.py`'s `--score_threshold` default and the bare
   `cv.FaceDetectorYN.create(...)` call in `feature-extract.py`. This is the
   single highest-leverage, lowest-risk change — it's already the value this
   project's own measured comparison recommends.
2. **Log what gets dropped.** Turn the `else: print("No face detected: ...")`
   branches in `feature-extract.py` / `dnn.py` into a persisted list (path + reason),
   written alongside `features-*.npy`, so the skip rate is a reportable number instead
   of scrollback.
3. **Run the existing comparison tool on the actual hard set** —
   `src/benchmark/compare_detectors.py --dataset <heavy/blurred split> --yunet-score-threshold 0.9`
   vs. `--yunet-score-threshold 0.6` — to convert §§1-4's causal story into a real
   before/after detection-rate number for the paper/report, rather than leaving it as
   an inference from separate runs.
4. **Don't change classical's `ASSUME_INPUTS_ARE_CROPPED` default** — that's a
   deliberate, documented design choice for the clean cropped-tile loop (per
   `DETECTOR_COMPARISON.md`), not a bug. If a true apples-to-apples
   detection-inclusive comparison is wanted, use the already-existing
   `--no-assume-cropped --detector yunet|haar` path instead of changing the default.

None of the above has been implemented — this document is the write-up + suggestion
only, per request.
