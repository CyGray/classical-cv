This folder contains the scripts and fully-trained models for the LBPH + SFace hybrid cascade (trained on LSDB 1, all identities) meant for porting to the Raspberry Pi environment.

### Staged LBPH descriptor rollout

The currently deployed profile is `r1_n8_g8x8` (radius 1, neighbors 8, 8x8
grid). `config/thresholds.json` records that compatibility explicitly, and
all numeric thresholds remain unchanged. The ablation-selected candidate is
`r3_n8_g6x6` (radius 3, neighbors 8, 6x6 grid), but it is not calibrated for
this bundle yet.

Enrollment makes the choice explicit:

```bash
python enroll.py --rebuild-only --descriptor-profile deployed
python enroll.py --rebuild-only --descriptor-profile selected
```

The default is `deployed`. Do not publish or select a `selected` release for
an active Pi deployment until matching LFW and hardware thresholds have been
installed in `config/thresholds.json`. The runtime reads the serialized model
parameters after `LBPHFaceRecognizer.read()` and refuses to start when the
model and threshold metadata disagree. Older active manifests without
descriptor metadata remain runnable with a clear legacy warning when their
serialized model matches the threshold profile.

### Folder Structure:

- **`models/`**:
  1. `face_detection_yunet_2023mar.onnx` - YuNet ONNX face detection model.
  2. `face_recognition_sface_2021dec.onnx` - SFace ONNX face recognition feature extractor.
- **`artifacts/`**:
  1. `lbph_seed42_manifest731bcf52fec2_cropped.yml` - LBPH trained model on cropped LSDB 1.
  2. `lbph_labels_seed42_manifest731bcf52fec2_cropped.json` - LBPH labels mapping for the trained LBPH model.
  3. `sface_gallery_seed42_manifest731bcf52fec2_cropped.npy` - SFace pre-computed gallery embeddings for LSDB 1.
  4. `sface_labels_seed42_manifest731bcf52fec2_cropped.json` - SFace labels mapping for the gallery embeddings.
- **`config/`**:
  1. `thresholds.json` - Contains the crucial deployment thresholds for the LBPH gate and SFace.
- **`archives/`**:
  1. `cascade-porting.zip` - Original zip archive backup.
- **`test/`**:
  1. `live_test.py` & `live_test.log` - Webcam live test harness & logs.

### Core Scripts:
- `hybrid_rpi.py` - A lightweight, zero-dependency (other than OpenCV) standalone script that executes the full hybrid cascade logic (detector -> LBPH fast-path -> Gate -> SFace escalation) directly on the Pi.
- `cascade.py` - Contains the `PiCamera` wrapper class, similar to what was previously used in `sface.py`.
- `enroll.py` - Hardware enrollment. Accepts one image, one person's folder, or `captures/<identity>/` folders. It writes pickle-free `enrollment/enrollment.npz`, rebuilds both runtime artifacts, and publishes the active release used automatically by `hybrid_rpi.py`.

Each new enrollment release contains a stable `descriptor_id` and the full
`lbph_descriptor` parameter block in `manifest.json`. A release built with the
selected candidate is therefore safe to test separately, but remains blocked
from active use until its thresholds are calibrated and installed.

### Hardware enrollment

```bash
# One photo / one identity
python enroll.py --identity Alice --input captures/alice.jpg

# A folder containing images for one identity
python enroll.py --identity Alice --input captures/alice/

# Multiple identities: captures/Alice/*.jpg, captures/Bob/*.jpg
python enroll.py --input captures/

# One named image per identity from a dataset tree
python enroll.py --input ../classical-cv/data/lasalle_db1_processed --include-name light_front.jpg --min-samples 1
```

Use at least three single-face images per identity. The central `.npz` saves space versus a raw `.yml` archive and is sufficient to rebuild models, but OpenCV still needs a generated LBPH `.yml` while recognition is running. Do not delete the active release. `hybrid_rpi.py` falls back to legacy bundled artifacts only when no enrollment release exists.

*Note: In previous porting folders, file extensions were occasionally scrambled (e.g. ONNX models named as `.py` or `.npy`). This folder uses correct extensions to prevent confusion during hardware integration.*
