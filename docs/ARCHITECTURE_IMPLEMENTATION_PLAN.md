# LS-Face — Hybrid CV + DL Implementation Plan (Pi-5 Ready)

*The build checklist. Architecture rationale lives in
[`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md); the short visual version is
[`ARCHITECTURE_REPORT.md`](ARCHITECTURE_REPORT.md). This document is the **execution
plan**: every phase is a list of checkboxes pointing at real files, and ends with a
"done when" gate you can verify.*

**End goal:** one `HybridRecognizer` (LBPH fast path + SFace escalation behind a
gate) that runs the **gated cascade** on a Raspberry Pi 5 with an NPU accelerator,
hitting the Stage-3 budget: **≥95% accuracy / ≥30 fps / <100 ms latency / <1 KB
feature**.

> **No invented numbers.** Any accuracy/FPS figure in a deliverable must come from
> an actual run. Leave result cells as `TBD (run pending)` until measured. The fused
> hybrid TAR/FAR/FRR is a *projection* until Phase 4 runs on real data.

---

## How to use this document

- Work top-to-bottom; phases are ordered by dependency. Check a box only when the
  task is **done and verified**, not when started.
- Each phase has: **Goal → Tasks (checkboxes) → Deliverable → Done when (gate)**.
- `[ ]` = todo, `[~]` = in progress, `[x]` = done. Keep this file under version
  control so the checkmarks are the single source of truth for "where are we."
- Paths are relative to `face-detection-g3/` unless they start with
  `face-detection-g3-dl/`.

---

## Phase overview & dependency order

```
  P0 ─▶ P1 ─▶ P2 ─▶ P3 ─▶ P4 ─▶ P5 ─▶ P6
 setup  detect  SFace  gate   cal.  UI    Pi+NPU
              \________________/
            (P2 + P3 can overlap once
             the Recognizer protocol exists)
```

| Phase | Title | Outcome | Blocks |
|---|---|---|---|
| **P0** | Groundwork & conventions | repos, deps, layout, naming agreed | all |
| **P1** | Unify detection | YuNet vendored, one front-end | P2, P3 |
| **P2** | Port SFace wrapper | SFace usable like LBPH | P3 |
| **P3** | Protocol + HybridRecognizer + gate | fused `predict()` works offline | P4 |
| **P4** | Calibration + honest eval | thresholds set, fused numbers measured | P5 |
| **P5** | Launcher wiring | `main.py → Hybrid` menu | P6 |
| **P6** | Pi 5 + accelerator | INT8 on NPU, on-device budget met | ship |

---

## Phase 0 — Groundwork & conventions

**Goal:** lock the environment, the repo layout, and the naming/threshold
conventions so nothing drifts later. No recognizer logic yet.

### 0.1 Environment

- [ ] Confirm both repos are siblings under the workspace (`face-detection-g3/`,
      `face-detection-g3-dl/`) and both run on the same Python (3.10+).
- [ ] Confirm `opencv-contrib-python` is installed (needed for **both**
      `cv.face.LBPHFaceRecognizer_create` *and* `cv.FaceRecognizerSF` /
      `cv.FaceDetectorYN`). Pin the exact version that the DL track validated against.
- [ ] Confirm `numpy`, and add `onnxruntime` (CPU) for off-device SFace runs.
- [ ] Record the frozen dependency set in `requirements.txt` (or note it in the
      changelog) so the Pi build can reproduce it.

### 0.2 Repo layout decision (where the new code lives)

- [ ] Hybrid code lives **in the CV repo** (`face-detection-g3/`), treating the DL
      repo as the *reference* to port from (not an import dependency).
- [ ] Reserve the new package paths up front:
  - [ ] `src/sface/` — SFace wrapper (Phase 2)
  - [ ] `src/hybrid/` — protocol, gate, quality probes, calibrate, evaluate (Phase 3–4)
  - [ ] `models/yunet_mobilefacenet/` — already exists (empty); YuNet ONNX lands here (Phase 1)
  - [ ] `models/sface/` — SFace ONNX + INT8 variant land here (Phase 2 / 6)

### 0.3 Conventions (write these down once)

- [ ] **Identity casing & label format**: hybrid enrollment must produce the *same*
      identity strings for both galleries (LBPH `.yml`+labels JSON and SFace `.npy`).
- [ ] **Threshold vocabulary**: standardize on `tau_accept`, `tau_reject`,
      `tau_blur`, `luma_lo/hi`, `tau_noise`, `tau_pose`, `px_min` (match
      [`ARCHITECTURE_PLAN.md`](ARCHITECTURE_PLAN.md) §4.2).
- [ ] **Score direction note in code**: LBPH raw = distance (lower better); SFace raw
      = cosine (higher better). Every comparison must convert through `far_of()`
      (Phase 3), never compare raw scores directly.

**Deliverable:** agreed layout + conventions, dependencies reproducible.
**Done when:** a fresh checkout can `import cv2; cv2.face; cv2.FaceRecognizerSF` and
the reserved directories exist.

---

## Phase 1 — Unify detection (vendor the seam)

**Goal:** one detector front-end (YuNet) feeding both recognizers, with the weight
file physically present in the CV repo.

### 1.1 Vendor the weights

- [ ] Copy `face-detection-g3-dl/models/face_detection_yunet_2023mar.onnx` (228 KB)
      → `models/yunet_mobilefacenet/face_detection_yunet_2023mar.onnx`.
      *(This is the exact path `DEFAULT_YUNET_MODEL_PATH` in
      [detection.py:43](src/classical_faces/detection.py#L43) already expects.)*
- [ ] Verify checksum matches the DL copy (same weights, same 5 landmarks).
- [ ] Decide whether to commit the binary or document a fetch step (228 KB is small —
      committing is fine and keeps the repo self-contained).

### 1.2 Wire it as the hybrid default

- [ ] Confirm `create_face_detector("yunet", ...)` resolves the model with **no
      explicit `--yunet-model-path`** now that the file is in place.
- [ ] Smoke-test the existing CV live path with YuNet:
      `python main.py → LBPH → live detect` with `--detector yunet`
      (or `FACE_G3_DETECTOR=yunet`). Expect `detector.describe()` to report YuNet.
- [ ] Set `yunet` as the hybrid's default detector backend (the gate path assumes
      YuNet landmarks for the pose probe).

### 1.3 Parity & alignment contract

- [ ] Run `src/benchmark/compare_detectors.py` (Haar vs YuNet) on the clean split;
      confirm YuNet detection ≥ Haar and note the FPS delta (YuNet should *raise*
      FPS vs the Haar bottleneck called out in the benchmarks).
- [ ] **Lock the alignment contract** (PLAN §10 risk): Stage-0 emits *box + 5
      landmarks*; downstream each recognizer applies its own normalization —
      LBPH = grayscale 100×100 + Tan-Triggs, SFace = `alignCrop` 112×112 RGB. Write
      this split as a comment in the shared detect stage so neither silently changes.

**Deliverable:** YuNet ONNX in-repo, one detector front-end, parity confirmed.
**Done when:** `--detector yunet` runs with no model-path flag and
`compare_detectors` shows YuNet ≥ Haar on the clean split.

---

## Phase 2 — Port the SFace recognizer into a shared wrapper

**Goal:** SFace usable through the same shape as LBPH — `enroll → gallery`,
`score → match`, `far_of → calibrated FAR`. Port from the DL track; do not change
its math.

### 2.1 The wrapper (`src/sface/`)

- [ ] Create `src/sface/__init__.py` and `src/sface/recognizer.py`.
- [ ] Load `cv.FaceRecognizerSF.create(model_path, "")` pointing at
      `models/sface/face_recognition_sface_2021dec.onnx` (copy the 37.8 MB ONNX from
      `face-detection-g3-dl/models/`).
- [ ] Port the embed path from `face-detection-g3-dl/dnn.py` /
      `feature-extract.py`: `aligned = recognizer.alignCrop(img_bgr, face_row)` →
      `feat = recognizer.feature(aligned)` (128-D float32 = **512 B**).
- [ ] Port the match rule **exactly**: genuine iff
      `cosine ≥ 0.363` **AND** `L2 ≤ 1.128`
      (`recognizer.match(..., FR_COSINE)` / `FR_NORM_L2`).

### 2.2 Enrollment / gallery

- [ ] `enroll(faces, labels) -> Gallery`: build the 512-B embedding per identity,
      persist to `models/sface/gallery.npy` + `models/sface/labels.json`
      (mirror the DL `features-*.npy` format so existing tooling reads it).
- [ ] `score(face) -> Match`: cosine vs every gallery embedding → `(best_name,
      cosine, all_scores)`; apply the dual cosine/L2 rule for accept/reject.

### 2.3 FAR calibration hook

- [ ] `far_of(raw_cosine) -> float`: map a cosine onto empirical false-accept rate
      using the **SFace impostor distribution** (the N×(N−1) independence outputs the
      DL team already produced).
- [ ] Reuse the DL impostor arrays directly where possible:
      `face-detection-g3-dl/features-lfw.npy` (+ `results-lfw.json`) for the LFW
      impostor distribution; same for `features-lasalledb1.npy`,
      `features-lasalledb2.npy`.

### 2.4 Parity check (don't trust a silent port)

- [ ] Stand up `src/sface/independence_test.py` (or a thin script) that reproduces
      the DL track's headline: **LFW FP ≈ 0.07% at TP 100%**. If the CV-repo wrapper
      doesn't match the DL repo's number on the same data, the port is wrong —
      fix before proceeding.

**Deliverable:** `src/sface/` — SFace behind the same interface LBPH will use.
**Done when:** the wrapper reproduces DL's LFW independence number from inside the CV
repo, and `enroll`+`score` round-trips a known identity.

---

## Phase 3 — `Recognizer` protocol + `HybridRecognizer` + the gate

**Goal:** the gated cascade runs **offline** (on image folders / video files) and
returns a fused decision, telling you which engine decided and whether it escalated.

### 3.1 The protocol (`src/hybrid/recognizer.py`)

- [ ] Define the `Recognizer` Protocol (PLAN §3): `name`, `kind`,
      `enroll(faces, labels) -> Gallery`, `score(face) -> Match`,
      `far_of(raw) -> float`.
- [ ] **LBPH adapter** — additive wrapper over `RecognizerSpec`
      ([pipeline.py:78](src/classical_faces/pipeline.py#L78)) + `recognizer.predict()`.
      Do **not** alter `RecognizerSpec`, `run_training`
      ([pipeline.py:497](src/classical_faces/pipeline.py#L497)), or `run_evaluation`
      ([pipeline.py:613](src/classical_faces/pipeline.py#L613)) — they have 3 callers
      each and **no covering tests**; keep the change zero-behavior-change.
- [ ] **SFace adapter** — wrap `src/sface/` (Phase 2) to the same protocol.

### 3.2 Quality probes (`src/hybrid/quality.py`)

Cheap checks on the crop LBPH already holds, reusing YuNet's outputs:

- [ ] **Blur**: variance-of-Laplacian `< tau_blur` (targets LBPH motion_blur 68.5%).
- [ ] **Low light**: mean luma outside `[luma_lo, luma_hi]` (targets brightness_down 73.7%).
- [ ] **Noise**: high-frequency / noise estimate `> tau_noise` (targets gaussian_noise 47.8%).
- [ ] **Off-pose**: landmark asymmetry / eye-line angle `> tau_pose` (from YuNet's 5 landmarks).
- [ ] **Small face**: YuNet box side `< px_min`.
- [ ] Each probe returns a boolean flag + the raw measurement (for logging/tuning).

### 3.3 The gate (`src/hybrid/gate.py`)

- [ ] Implement the escalation rule (PLAN §4.2): escalate to SFace if **any** of —
      ambiguous score (`tau_accept < d_cv < tau_reject`), low top-1/top-2 margin
      (`m < m_min`), or **any** quality flag from 3.2.
- [ ] **Quality flag overrides a confident LBPH score** (in hard regimes LBPH's
      confidence is exactly what we measured as unreliable).
- [ ] Non-escalated path: `d_cv ≤ tau_accept` → accept; `d_cv ≥ tau_reject` → reject.

### 3.4 `HybridRecognizer.predict()` + modes

- [ ] `predict(face) -> HybridDecision` returning: final identity/Unknown, deciding
      engine (`lbph`/`sface`), `escalated: bool`, and both raw scores (for reports).
- [ ] Modes (PLAN §4.3): `cascade` (default), `parallel` (both every frame),
      `cv_only` (no-accelerator fallback), `dl_only`.
- [ ] Two-gallery handling: hybrid holds **both** the LBPH gallery and the SFace
      gallery for the same identities (see Phase 4 consistency check).

### 3.5 Offline sanity (before any calibration)

- [ ] Feed a clean frontal face → decision stays on LBPH, `escalated=False`.
- [ ] Feed a blurred / dark / noisy / off-pose face → `escalated=True`, SFace decides.
- [ ] Feed an out-of-gallery face → Unknown from whichever engine.

**Deliverable:** `src/hybrid/{recognizer,quality,gate}.py` — fused `predict()` works
on files with provisional thresholds.
**Done when:** the three sanity inputs in 3.5 route correctly with placeholder
thresholds (real thresholds come next).

---

## Phase 4 — Calibration + honest evaluation

**Goal:** replace placeholder thresholds with values **derived from the independence
test**, then measure the fused system for real. This is where projected numbers
become measured numbers.

### 4.1 Calibration (`src/hybrid/calibrate.py`)

- [ ] **LBPH gate edges** from LBPH independence vs LFW impostors:
      `tau_accept` = 100 ppm FAR (≈ **73.04**), `tau_reject` = band edge ≈ 1% FAR
      (≈ **76.85**). Reuse `src/independence_common.py` +
      `scripts/run_lfw_independence.py`.
- [ ] **SFace operating threshold** at the **same FAR budget**, from the SFace
      impostor distribution (Phase 2.3).
- [ ] **Quality-probe thresholds** via measured crossover on the La Salle DB2
      41-modification suite (`src/benchmark/accuracy_ratio.py`): for each
      modification, set the probe threshold at the point where LBPH AR drops below
      SFace AR — escalate exactly where DL starts winning. Not a guess; a crossover.
- [ ] Persist all thresholds to a single `src/hybrid/thresholds.json` (the deployed
      config), with a note recording which dataset/run produced each value.

### 4.2 Two-gallery consistency (PLAN §10 risk)

- [ ] Enrollment builds **both** galleries from the **same aligned crops** so LBPH
      and SFace describe the identical identity set. Add an assertion that the two
      label sets are equal.

### 4.3 Fused evaluation (`src/hybrid/evaluate.py` + `src/benchmark/compare_hybrid.py`)

- [ ] Report end-to-end **fused TAR / FAR / FRR** (hybrid as one system), reusing the
      independence + `src/benchmark/tar_at_far.py` machinery.
- [ ] Report **escalation rate** (fraction of frames that hit SFace) — the key
      FPS-vs-accuracy knob.
- [ ] Report **per-stage latency** (YuNet, LBPH+gate, SFace) so the Pi budget is
      predictable before hardware.
- [ ] Produce `reports/benchmark/hybrid_comparison.md`: **hybrid vs LBPH-only vs
      SFace-only** on the same split. Leave numbers `TBD (run pending)` until the run
      completes; fill from actual output only.

**Deliverable:** `thresholds.json` + `reports/benchmark/hybrid_comparison.md`
(measured).
**Done when:** the comparison table is filled from a real run and the hybrid's fused
accuracy ≥ LBPH-only while escalation rate is within the FPS budget.

---

## Phase 5 — Launcher wiring (make it a menu choice)

**Goal:** the hybrid is reachable the same way every other family is — through
`main.py`, no bespoke commands.

- [ ] Add a **`"Hybrid"`** group to `GROUPED_CHOICES`
      ([main.py:12](main.py#L12)) with actions:
  - [ ] `("enroll", "src/hybrid/enroll.py")` — builds both galleries from one crop set
  - [ ] `("evaluate", "src/hybrid/evaluate.py")`
  - [ ] `("live detect", "src/hybrid/detect.py")`
  - [ ] `("calibrate", "src/hybrid/calibrate.py")`
  - [ ] `("compare (hybrid vs lbph vs sface)", "src/benchmark/compare_hybrid.py")`
- [ ] Add a matching `"Hybrid"` entry to `MODEL_INFO_CONFIG`
      ([main.py:98](main.py#L98)) so the launcher shows model info.
- [ ] Build `src/hybrid/detect.py` by reusing the LBPH live loop
      ([src/lbph/detect.py:230](src/lbph/detect.py#L230)) — same detect/track/temporal-voting
      scaffold, but swap `recognizer.predict()` for `HybridRecognizer.predict()` and
      draw the deciding-engine + `escalated` flag on the overlay.
- [ ] Add a `--mode {cascade,parallel,cv_only,dl_only}` flag wired to the hybrid modes.
- [ ] Update `docs/changelogs/CHANGELOG.md` with the new group.

**Deliverable:** `python main.py → Hybrid → live detect` runs the gated cascade live.
**Done when:** all five Hybrid actions launch from the menu and live detect shows the
CV→DL escalation happening on-screen.

---

## Phase 6 — Pi 5 + accelerator readiness

**Goal:** the heavy CNN runs on the NPU as INT8, the CPU runs LBPH + gate, and the
whole thing holds the Stage-3 budget on-device — with a clean CPU-only fallback.

### 6.1 Choose & provision the accelerator

- [ ] Select the accelerator (PLAN §6): **Hailo-8 / 8L (Pi AI HAT+)** recommended;
      Coral USB as alternative. Record the choice + TOPS budget.
- [ ] Provision the Pi 5: 64-bit Pi OS, install the runtime
      (HailoRT for Hailo / `libedgetpu` for Coral), OpenCV, the frozen deps from P0.

### 6.2 Quantize SFace to INT8

- [ ] Build a representative calibration set (aligned crops spanning the DB2 regimes).
- [ ] Reuse the post-training-quantization recipe in
      [src/arcface_mobilenet_int8/quantize_model.py](src/arcface_mobilenet_int8/quantize_model.py)
      to produce INT8 SFace; save to `models/sface/face_recognition_sface_int8.*`.
- [ ] **Re-run SFace independence on the INT8 model** and re-derive its deployed
      threshold — quantization shifts the score distribution, so the float threshold
      from Phase 4 is **not** valid on-device (PLAN §10 "INT8 drift").
- [ ] Update `thresholds.json` with the INT8-derived SFace threshold; mark it as the
      deployed value.

### 6.3 Compile for the NPU & wire fallback

- [ ] Compile **YuNet + SFace** for the target NPU:
      Hailo (ONNX → HEF via Dataflow Compiler) **or** Coral (ONNX → TFLite → EdgeTPU).
- [ ] Put NPU inference **behind the SFace wrapper** (Phase 2) so callers don't change;
      detection runs on the NPU every frame, SFace only on escalated frames.
- [ ] **CPU fallback**: if no accelerator is detected, the system degrades to
      `cv_only` (LBPH on CPU) rather than attempting SFace on the CPU at 30 fps
      (PLAN §4.3 / §10). Verify the fallback path triggers when the HAT is unplugged.

### 6.4 On-device measurement (the real Stage-3 numbers)

- [ ] Measure on-device **FPS** (clean stream and escalation-heavy stream).
- [ ] Measure **end-to-end latency** per stage (YuNet/LBPH+gate/SFace on NPU).
- [ ] Measure **escalation rate** on a realistic feed; if FPS dips, re-tune probe
      thresholds toward a capped escalation budget (PLAN §10).
- [ ] Check thermals / sustained throughput over a multi-minute run.

**Deliverable:** hybrid running client-centered on the Pi 5 with INT8 SFace on the
NPU; on-device numbers recorded.
**Done when:** the Pi-5 readiness gate below passes.

---

## ✅ Pi-5 Integration Readiness Gate (the acceptance checklist)

The system is "ready to be integrated into the Pi 5" when **all** of these hold:

- [x] YuNet ONNX vendored in-repo; one detector front-end (P1).
- [x] SFace wrapper reproduces DL's LFW independence number from the CV repo (P2).
      *(Measured: LFW FP = 0.0747% vs DL 0.07% → parity PASS;
      `reports/independence/sface_lfw_parity.json`.)*
- [x] `HybridRecognizer.predict()` routes clean→CV and hard→DL correctly (P3).
- [~] All thresholds derived from the independence test + DB2 crossover, persisted to
      `thresholds.json` (P4). *SFace cosines + LBPH edges + clean-crop quality edges
      are measured/provenance-stamped; the full DB2 41-mod LBPH↔SFace per-probe
      crossover is deferred to on-device tuning (Phase 6.4).*
- [x] `reports/benchmark/hybrid_comparison.md` filled from a **real** run; fused
      accuracy ≥ LBPH-only (P4). *Clean: hybrid 100% rank-1 / 25% escalation.
      Degraded (41-mod medium): hybrid 97.96% vs LBPH-only 5.10% —
      `hybrid_comparison_degraded.md`.*
- [x] `main.py → Hybrid` menu works for enroll/evaluate/live/calibrate (P5).
      *CPU-only `cv_only` fallback implemented + auto-degrades when the SFace gallery
      is absent; on-device verification with the accelerator unplugged is P6.3.*
- [ ] SFace re-quantized to INT8 **and** re-calibrated on-device (P6.2).
- [ ] CPU-only fallback verified with the accelerator absent (P6.3).
- [ ] On-device budget met: **≥30 fps, <100 ms latency, ≥95% accuracy, <1 KB feature**
      (the SFace 512 B gallery feature satisfies the size spec LBPH's 64 KB fails).

---

## Files at a glance

**Create**
- [ ] `models/yunet_mobilefacenet/face_detection_yunet_2023mar.onnx` *(vendored)*
- [ ] `models/sface/face_recognition_sface_2021dec.onnx` *(vendored)* + `…_int8.*` *(P6)*
- [ ] `src/sface/{__init__,recognizer,independence_test}.py`
- [ ] `src/hybrid/{__init__,recognizer,quality,gate,calibrate,evaluate,enroll,detect}.py`
- [ ] `src/hybrid/thresholds.json`
- [ ] `src/benchmark/compare_hybrid.py`
- [ ] `reports/benchmark/hybrid_comparison.md`

**Edit (additive, no behavior change)**
- [ ] `main.py` — add `"Hybrid"` to `GROUPED_CHOICES` + `MODEL_INFO_CONFIG`
- [ ] `src/classical_faces/pipeline.py` — expose LBPH behind the `Recognizer` protocol (adapter only)
- [ ] `docs/changelogs/CHANGELOG.md`

**Reuse as-is**
- [ ] `src/classical_faces/detection.py` — YuNet backend, `create_face_detector`
- [ ] `src/independence_common.py` + `scripts/run_lfw_independence.py` — threshold calibration
- [ ] `src/benchmark/{tar_at_far,accuracy_ratio,compare_detectors}.py` — eval machinery
- [ ] `src/arcface_mobilenet_int8/quantize_model.py` — INT8 recipe
- [ ] `face-detection-g3-dl/{dnn,feature-extract,loader,ldb2-independence}.py` + `features-*.npy` — SFace reference & impostor data

---

## Risk register (carry from PLAN §10 — check when mitigated)

- [ ] **Escalation rate vs FPS** — calibrate probes at the measured LBPH↔SFace
      crossover (4.1); cap escalation as a tuned budget; re-tune on-device (6.4).
- [ ] **Two galleries, one identity set** — build both from the same aligned crops;
      assert equal label sets (4.2).
- [ ] **INT8 drift** — deployed SFace threshold comes from an independence run on the
      **quantized** model, never the float numbers (6.2).
- [ ] **No-accelerator fallback** — degrade to `cv_only`, verified unplugged (6.3).
- [ ] **Alignment contract** — Stage-0 emits box+landmarks; each recognizer keeps its
      own normalization explicit (1.3).
- [ ] **Don't invent fused numbers** — every result cell is `TBD` until its run
      completes; report measured-only.
