# LS-Face — Classical CV Track Briefing (Kyle, Group 3)

*A self-contained context primer for the LS-Face / Smart Gate project. Use it as your own reference and paste the "Model Context Block" at the bottom into any new Opus 4.8 conversation to bring it up to speed.*

---

## 1. Project Identity

**LS-Face (La Salle Facial Recognition Software)** — *Facial recognition software using hybrid technologies based on an independence test.* Built for the USLS Computer Vision course (Group 3). The end goal is a **hybrid CV + DL recognizer**, with the winning combination selected via independence testing, deployed on a **Raspberry Pi 5 as a "Smart Gate."**

The project compares **classical computer-vision recognizers** against **deep-learning recognizers**, uses **independence testing** to fix match thresholds at a defined false-alarm rate, then fuses the strongest candidates into a hybrid for on-device inference.

---

## 2. Staged Master Plan

| Step | Window | System | Architecture | Key targets |
|---|---|---|---|---|
| 1 | ~5/19 | Computer-vision-based | Server-centered (PC + webcam) | Accuracy ↑90%, Speed 1 face/sec |
| 2 | 5/1–6/30 | Deep-learning-based | Server–client (PC + Pi 5) | — |
| 3 | 7/1–7/30 | Hybrid (CV + DL) | Client-centered (Pi 5) | Accuracy ≥95%, Speed ≥30 fps (real time) |
| 4 | 8/1–8/30 | Real-world recognition | Client-centered (Pi 5) | Accuracy ↑90%, Speed real time |

Stage I target overall: **Smart Gate (image-based), ~September 2026.** Two derived papers are planned (both submission ~8/15): Paper 1 on the hybrid/independence-test method, Paper 2 on a real-time edge-computing home-security system.

---

## 3. System Architecture (7-stage pipeline)

```
Input Image
   → (1) Image Pre-processing        [noise reduction, contrast enhancement]
   → (2) Face Detection & Pre-proc   [detection, 2D alignment, grayscale, resize]
   → (3) Image Database  ⇄  (4) Feature Database
   → (5) Independence Test           [threshold determination]
   → (6) Face Recognition            [identification / verification]
   → (7) Evaluation & Analysis       [performance eval, problem analysis, improvements]
```

The classical recognizers all use **Haar cascade** for detection feeding the OpenCV recognizers.

---

## 4. Kyle's Role & Responsibilities

**Owner of the classical CV recognizer track.** Specifically responsible for:

- **Three classical pipelines** — LBPH, Eigenfaces, Fisherfaces (`src/lbph/`, `src/eigenfaces/`, `src/fisherfaces/`).
- **Independence tests** for each of the three classical models.
- **The `independence_failure_check/` post-hoc analysis** — occlusion analysis, regional collapse detection, multi-image verification, and visual report generation.

Teammates own the deep-learning recognizers (MobileFaceNet, EdgeFace, ArcFace, ArcFace INT8) and the shared database work.

**Critical-path deliverables (Kyle's):**

| Deliverable | Due | Notes |
|---|---|---|
| CV recognizer selection | 6/30 | Pick the best of LBPH / Eigenfaces / Fisherfaces from validated benchmarks |
| CV independence + threshold | 7/15 | Determine independency condition + match threshold per spec |
| Hybrid method input | 7/30 | Feed the selected CV recognizer + threshold into the hybrid fusion |

Earlier supporting milestones from the schedule: face-detection selection & face pre-processing (~6/16), feature DB build (~6/30).

---

## 5. The Three Classical Algorithms

| Algorithm | Basis | Detection | OpenCV recognizer |
|---|---|---|---|
| **LBPH** | Local Binary Patterns Histograms | Haar cascade | `LBPHFaceRecognizer` |
| **Eigenfaces** | PCA | Haar cascade | `EigenFaceRecognizer` |
| **Fisherfaces** | LDA | Haar cascade | `FisherFaceRecognizer` |

Each classical model trains a **`.yml` model file + `.json` label map**. (DL models instead build an enrollment JSON of face embeddings / identity centroids.)

Each pipeline has the same four scripts: `trainer.py`, `evaluate.py`, `detect.py` (or `face_detect.py`), and optionally `independence_test.py`.

---

## 6. Target Specs (from the project spec sheet)

| Metric | Target |
|---|---|
| TAR (True Acceptance Rate / accuracy) | 90–95% |
| FAR (False Acceptance Rate) | < 0.01% (100 ppm) |
| FRR (False Rejection Rate) | 1–5% |
| Latency (capture → result) | < 100 ms |
| Speed | ≥ 30 fps |
| Feature vector size | < 1 KB |

> **Realistic caveat:** On-device Pi 5 throughput for the classical models will be lower than the desktop ≥30 fps target. The classical models are the lightest candidates for the port, which is part of why they matter for the hybrid.

---

## 7. Datasets

| Dataset | DB1 (independence / threshold) | DB2 (recognition testing) |
|---|---|---|
| **La Salle** (`lasalle_db1`) — primary | 28 persons × 10 cases = 280 photos | 280 × 41 modifications ≈ 11,480 photos |
| **LFW** — supplementary, processed only | 5,749 persons, 13,233 photos | 13,233 × 41 modifications ≈ 542,553 photos |

La Salle has raw (`lasalle_db1`) and cropped/aligned (`lasalle_db1_processed`) variants. **Augmented splits** (`light` / `medium` tiers) are generated via `augment_split_light_medium.py`. Evaluation reports embed a `dataset_profile` so cross-dataset runs are never mixed.

DB1 sets are used for the **independence test and threshold determination**; DB2 sets (the 41-modification variants) are used for **recognition accuracy testing**.

---

## 8. Independence Testing & Threshold Determination

Independence tests verify that recognition accuracy is **not inflated by data leakage** between train/test identities. The threshold is set at a target false-alarm rate.

| DB | Comparisons (self-comparison excluded) | Threshold rule |
|---|---|---|
| **La Salle DB1** | 756 = 28 × 27 | Feature distance of the **8th error pair** (10,000 ppm) |
| **LFW DB1** | 33,045,252 = 5,749 × 5,748 | Feature distance of the **331st error pair** (10 ppm) |

The independency *condition* is the chosen false-alarm rate (e.g., 100 ppm = 100 errors in 1 million; 1 ppm = 1 in 1 million). The *threshold* is the feature distance at the corresponding error-pair rank above.

Eigenfaces/Fisherfaces independence tests can run against up to 6 cross-slice LFW segments. A known failure mode to watch is **annotation error** — the same identity name attached to genuinely different images (or vice versa), which corrupts true-positive / false-positive pair labeling.

---

## 9. Accuracy Ratio (AR) Measurement

Recognition performance is measured per modification and level using **AR = K / M**:

- For a given modification and level, every original image has a modified version (M total modified images — 78,120 for La Salle DB2 by this scheme, 542,553 for LFW DB2).
- The algorithm compares each original against its modified version; **K** = number of detected matches.
- **AR** is the proportion of modified images correctly matched to their original.
- Repeat across all levels per modification, take the mean per modification, then average across modifications for overall performance.

AR is determined at a **pre-determined false-positive rate** (set by the independence threshold).

---

## 10. Conventions & Technical Details

- **Entry point:** the interactive launcher `python main.py`. It handles model selection, dataset selection, artifact paths, and duplicate-run warnings. Actions: train / evaluate / live detect / independence test.
  - Windows interpreter override: `set FACE_G3_PYTHON=path/to/python`.
- **Evaluation reports:** written to `reports/evaluation/` as structured JSON containing `hit_rate_percent`, a **threshold sweep**, per-identity breakdown, plus `dataset_profile`, `model_variant`, `entity_key`, and `run_tag`.
- **Benchmark utilities:**
  - `src/benchmark/compare_models.py` — side-by-side comparison
  - `src/benchmark/aggregate_evaluation_reports.py` — groups reports by entity, writes summary JSON + Markdown
  - `src/benchmark/aggregate_live_fps.py` — aggregates live-detect FPS logs
  - The launcher's **Benchmark** menu shows a live overview table (hit rate, accuracy, FPS, model size) across evaluated models.
- **Shared utilities:** `src/dataset_layout.py`, `src/reporting/identity.py`, `src/independence_common.py`.
- **Key dependencies:** `opencv-contrib-python` (needed for the legacy face recognizers), `insightface`, `onnxruntime`, `numpy`, `scikit-learn`, `tqdm`.

---

## 11. Open Questions / Things to Watch

- **FPS target ambiguity (unresolved).** The spec sheet lists **≥30 fps** as the overall evaluation target, and the README has been corrected to reflect that. The staged master plan, however, lists **"1 face/sec"** for the Step-1 CV-based stage and **≥30 fps** only for the Step-3 hybrid/real-time stage. So "≥30 fps" reads as the final hybrid/real-time goal rather than a hard per-stage requirement for classical models on the Pi. If a "3 FPS" figure surfaces in project materials, confirm with the team whether it's an intentional on-device classical target or a typo — this hasn't been settled.
- **A prior README goal line ("≥100% accuracy at ≥3 FPS") was wrong** — ≥100% accuracy is impossible, and it was inconsistent with the real spec sheet. It's been corrected to the actual targets in §6. Keep an eye out for the same garbling resurfacing in docs.
- **Data leakage** inflating recognition accuracy — the whole reason the independence tests exist. Flag any recognition result that looks suspiciously high relative to the independence-test distance distribution.
- **No invented results.** Benchmark numbers should come from actual runs. Distinguish "planned" from "run" before reporting anything as a result.

---

## 12. Model Context Block (paste this into new Opus 4.8 chats)

> I'm Kyle, Group 3, USLS Computer Vision course. Project: **LS-Face / Smart Gate** — a hybrid (CV + DL) face recognizer, selected via independence testing, deployed on a Raspberry Pi 5. I own the **classical CV track**: LBPH, Eigenfaces, Fisherfaces (`src/lbph`, `src/eigenfaces`, `src/fisherfaces`), their independence tests, and `independence_failure_check/`. Teammates own the DL recognizers and shared DB work.
>
> **Target specs:** TAR 90–95%, FAR <0.01% (100 ppm), FRR 1–5%, latency <100 ms, speed ≥30 fps, feature vector <1 KB. (On-device Pi 5 throughput for classical models will be lower.)
>
> **Conventions:** entry point is the interactive launcher `main.py`. Eval reports → `reports/evaluation/` as JSON with `hit_rate_percent`, threshold sweep, `dataset_profile`, `model_variant`, `entity_key`, `run_tag`. Classical models output a `.yml` model + `.json` label map.
>
> **Independence thresholds:** La Salle DB1 = 756 (28×27) comparisons, threshold = feature distance of the **8th error pair** (10,000 ppm); LFW DB1 = 33,045,252 (5,749×5,748) comparisons, threshold = feature distance of the **331st error pair** (10 ppm).
>
> **Datasets:** La Salle DB1 = 28×10 = 280 photos; DB2 = 280×41 ≈ 11,480. LFW DB1 = 5,749 persons / 13,233 photos; DB2 ≈ 542,553.
>
> **My critical path:** CV recognizer selection (6/30), CV independence + threshold (7/15), hybrid method input (7/30).
>
> When I share code or errors, be specific and concise. Flag anything that looks like data leakage inflating recognition accuracy. Don't invent results — ask what's actually been run vs. planned.