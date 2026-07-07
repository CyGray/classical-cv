# LS-Face — Hybrid CV + DL Architecture Plan

*How the classical CV track (`face-detection-g3`) and the deep-learning track
(`face-detection-g3-dl`) combine into one recognizer, how the system switches
between them at runtime, and how it lands on a Raspberry Pi 5 "Smart Gate."*

Status: **design** (Stage 3 of the master plan — hybrid, target ≥95% accuracy /
≥30 fps real-time). This document is the contract for the fusion work; it does
not change either track's internals, it defines the seam between them.

---

## 0. TL;DR

- **Detection is already unified.** Both tracks run **YuNet** (`face_detection_yunet_2023mar.onnx`).
  The classical pipeline already has a pluggable YuNet backend
  (`src/classical_faces/detection.py`); the DL track uses YuNet natively. One
  detector front-end feeds both recognizers — this is the existing seam we build on.
- **Recognition is where they differ, and that difference is the asset.**
  Classical = **LBPH** (cheap, deterministic, 100% rank-1 on clean frontal faces,
  but brittle to noise/blur/low-light and a 64 KB feature that *fails* the <1 KB
  spec). DL = **SFace** (CNN embedding, robust to the exact conditions LBPH fails,
  512-byte feature that *passes* the spec, but heavier to compute).
- **Fusion = a gated cascade.** LBPH decides the easy, clean cases on the CPU at
  high FPS. The gate **escalates to SFace only when LBPH is uncertain or the
  input is in a known-hard regime** (blur / low light / off-pose / small face).
  This is exactly the professor's suggestion #1 — *DL compensates for CV's
  weaknesses* — implemented as a runtime policy, not a vague aspiration.
- **The Pi accelerator (suggestion #2) makes the escalation path affordable.**
  YuNet + SFace are ONNX; they offload to a Hailo-8 (Pi AI HAT+) or Coral Edge
  TPU. LBPH stays on the CPU. The NPU absorbs the heavy "large-feature" CNN cost
  that would otherwise sink the 30 fps target on the Pi 5 CPU.

---

## 1. What each track actually is today (grounded in our benchmarks)

These are measured numbers from each repo's own reports, not targets.

### Classical track — `face-detection-g3` (Kyle)

| Recognizer | Rank-1 (held-out) | TAR@100ppm FAR | EER vs LFW | Overall AR (41-mod) | Model | Feature | <1 KB? | Live FPS |
|---|---:|---:|---:|---:|---:|---:|:--:|---:|
| **LBPH** (Tan-Triggs) | **100.00%** | **98.21%** / FRR 1.79% | **0.07%** | **85.43%** | 33.3 MB | 64 KB | ❌ | 19.9 |
| Eigenfaces | 75.00% | 23.21% | 31.77% | 47.69% | 82.6 MB | 1.1 KB | ❌ | 29.0 |
| Fisherfaces | 66.07% | 10.71% | 35.71% | 30.54% | 8.2 MB | 108 B | ✅ | 27.8 |

LBPH is the selected classical recognizer (`reports/benchmark/classical_comparison.md`).
Its **measured weak spots** (Accuracy Ratio per modification, deployable threshold):

- `gaussian_noise` → **47.8%**
- `motion_blur` → **68.5%**
- `brightness_down` → **73.7%**

Detection feeding it is interchangeable Haar / YuNet
(`src/classical_faces/detection.py`); the FPS bottleneck today is the **Haar
detector**, not the recognizer.

### DL track — `face-detection-g3-dl` (teammates)

| Component | What | File / weight | Size |
|---|---|---|---:|
| Detector | **YuNet** (`cv.FaceDetectorYN`) | `models/face_detection_yunet_2023mar.onnx` | 228 KB |
| Recognizer | **SFace** (`cv.FaceRecognizerSF`), 128-D embedding | `models/face_recognition_sface_2021dec.onnx` | 37.8 MB |
| Match rule | cosine ≥ **0.363** *and* L2 ≤ **1.128** | (SFace defaults) | — |

Independence-test results (same N×(N−1) methodology as the classical track —
this is the shared evaluation backbone):

| Dataset | Persons / images | Comparisons | TP | FP |
|---|---|---:|---:|---:|
| LFW | 5,685 | 32,313,540 | 100.0% | **0.07%** |
| La Salle DB1 | 28 | 756 | 100.0% | **2.65%** |
| La Salle DB2 | 9,732 imgs | 91,306,856 | — | **1.83%** |

The SFace embedding is **128 × 4 B = 512 B → passes the <1 KB feature spec that
LBPH fails.** It is robust to pose / illumination / scale by construction (CNN
trained with margin loss), and YuNet's `alignCrop` uses the 5 landmarks to
canonicalize the face before embedding — directly addressing the
`SUGGESTION.md` note to *focus on the eyes / eyebrows / nose / mouth*.

### The complementarity, in one line

> LBPH is fast, deterministic, and perfect on clean frontal faces but collapses
> on noise/blur/low-light and overflows the feature budget. SFace is robust on
> exactly those hard cases and fits the feature budget, but costs a CNN forward
> pass. **Each one's strength is the other's weakness** — which is what makes a
> hybrid worth building instead of just picking one.

---

## 2. The two seams that already exist (we are not starting from zero)

1. **Shared detector.** YuNet is the common front-end. The classical track wraps
   it behind a `FaceDetector` interface returning `(box, score, landmarks)`; the
   DL track calls `FaceDetectorYN` directly. **Same weight file, same 5
   landmarks.** Unifying detection is mostly *vendoring the ONNX into the CV repo*
   (it is referenced at `models/yunet_mobilefacenet/...` but not yet present —
   it currently lives only in `face-detection-g3-dl/models/`).

2. **Shared evaluation method.** Both tracks fix their match threshold with the
   **independence test** (k-th error pair at a target FAR) and report TAR/FAR/FRR.
   That gives us a *common currency* to fuse on (see §4): every engine can
   express a raw score as a **calibrated FAR**, and the gate compares FARs, not
   raw distances on incompatible scales.

The fusion work lives **in the gap between these seams**: a shared recognizer
interface + a decision gate. Neither recognizer's internals change.

---

## 3. Unified recognizer contract

Today the classical track already has a clean contract object — `RecognizerSpec`
in `src/classical_faces/pipeline.py` (family, factory, threshold, feature-size
formula). We generalize that idea to **one `Recognizer` protocol** both tracks
satisfy, so the hybrid engine holds a list of recognizers behind one interface:

```python
class Recognizer(Protocol):
    name: str                       # "lbph" | "sface"
    kind: str                       # "classical" | "embedding"
    def enroll(self, faces, labels) -> Gallery: ...
    def score(self, face) -> Match:  # -> (best_name, raw_score, all_scores)
        ...
    def far_of(self, raw_score) -> float:  # calibrated FAR for this score
        ...
```

- **LBPH** wraps `RecognizerSpec` + `recognizer.predict()` (raw = distance,
  lower is better). `far_of` reads the LBPH impostor distribution from its
  independence run.
- **SFace** is a new wrapper ported from the DL track's `dnn.py` /
  `feature-extract.py` (raw = cosine, higher is better; gallery = 128-D
  embeddings). `far_of` reads the SFace impostor distribution.

`far_of` is the keystone: it converts each engine's incompatible raw score onto
**one axis (empirical false-accept rate)** so the gate can reason about both
engines uniformly. Both impostor distributions already exist — they are the
independence-test outputs.

---

## 4. The hybrid decision architecture (how they combine + switch)

**Recommended: a gated cascade** (CV first, escalate to DL on demand). This is
the default runtime mode. Two alternatives (§4.3) exist for special cases.

### 4.1 Pipeline

```
                ┌─────────────────────────────────────────────────────────┐
                │  Stage 0 — Capture + Detect + Align   (shared, on NPU)   │
                │  frame ─▶ YuNet ─▶ box + score + 5 landmarks ─▶ align     │
                └───────────────────────────┬─────────────────────────────┘
                                            │ aligned face crop
                                            ▼
                ┌─────────────────────────────────────────────────────────┐
                │  Stage 1 — LBPH  (classical, on CPU — cheap, fast)       │
                │  predict() ─▶ distance d_cv , top-2 margin m            │
                │  quality probe ─▶ blur / luma / pose / face-size flags  │
                └───────────────────────────┬─────────────────────────────┘
                                            ▼
                                  ╔═══════════════════╗
                                  ║   DECISION GATE   ║   (§4.2)
                                  ╚═════════╤═════════╝
              confident match / reject  ◀───┤───▶  ambiguous OR hard-regime
                       │                                     │
                       ▼                                     ▼
              ┌──────────────────┐        ┌──────────────────────────────────┐
              │  Accept / Reject │        │  Stage 2 — SFace (DL, on NPU)    │
              │  on LBPH alone   │        │  embed ─▶ cosine/L2 ─▶ decide at  │
              │  (the fast path) │        │  SFace independence threshold     │
              └──────────────────┘        └──────────────────────────────────┘
                                                          │
                                                          ▼
                                            ┌──────────────────────────┐
                                            │  Final identity / Unknown │
                                            └──────────────────────────┘
```

The **common case** (clean, frontal, well-lit) never touches SFace → the system
runs at LBPH+YuNet speed. SFace fires **only on the minority of hard frames**,
so average latency stays low while worst-case accuracy gets the CNN.

### 4.2 The gate (the actual switching logic)

Escalate from LBPH to SFace when **any** of:

| Trigger | Condition | Why |
|---|---|---|
| **Ambiguous score** | `τ_accept < d_cv < τ_reject` (LBPH FAR between 100 ppm and ~1%) | LBPH is in the band where it produces false accepts |
| **Low margin** | top-1 vs top-2 distance gap `m < m_min` | two enrolled identities are nearly tied — unstable |
| **Blur** | variance-of-Laplacian `< τ_blur` | LBPH `motion_blur` AR = 68.5% |
| **Low light** | mean luma out of `[lo, hi]` | LBPH `brightness_down` AR = 73.7% |
| **Noise** | high-frequency energy / noise estimate `> τ_noise` | LBPH `gaussian_noise` AR = 47.8% |
| **Off-pose** | landmark asymmetry / eye-line angle `> τ_pose` | subspace + LBPH degrade off-frontal |
| **Small face** | YuNet box side `< px_min` | low effective resolution |

Otherwise decide on LBPH alone:

- `d_cv ≤ τ_accept` (calibrated ≤ 100 ppm FAR, i.e. **distance ≤ 73.04**) → **accept**.
- `d_cv ≥ τ_reject` → **reject (Unknown)**.

The quality probes are cheap (they run on the same crop LBPH already has) and
they reuse the signals YuNet already emits (score, landmarks, box size). Crucially,
**a quality flag overrides a confident-looking LBPH score** — because in those
regimes LBPH's confidence is exactly what we measured to be unreliable.

### 4.3 Alternative modes (configurable, same interface)

- **Parallel score-level fusion** ("max-accuracy" mode): run LBPH *and* SFace on
  every face, fuse on the common FAR axis (e.g. accept if either clears its
  100 ppm threshold, or a weighted rule). More accurate, but pays the CNN every
  frame — only sensible when the NPU makes SFace effectively free. Good for the
  *enrollment* and *offline benchmark* paths, and for a "high-security" gate mode.
- **Condition / mode switch** (degraded fallback): a global mode picks CV-only
  (daylight, near, no accelerator present) vs DL-only (night, far) vs hybrid.
  This is the **graceful-degradation path when no accelerator is attached** —
  the Pi falls back to LBPH-only on CPU rather than failing.

We ship the **gated cascade as default**, expose **parallel** as a config flag,
and keep **CV-only** as the no-accelerator fallback.

---

## 5. Suggestion #1 — DL compensates for CV's weaknesses (where & how)

This is the gate's whole reason to exist. Concretely, the escalation triggers in
§4.2 are derived **one-to-one from LBPH's measured failure modes**:

| LBPH measured weakness | Number | Compensating DL behavior | Gate trigger that routes it to SFace |
|---|---:|---|---|
| Gaussian noise | AR 47.8% | CNN learned noise-invariant features | noise probe |
| Motion blur | AR 68.5% | margin-loss embedding robust to blur | blur probe |
| Brightness down | AR 73.7% | illumination-invariant by training | luma probe |
| Off-pose / rotation | (subspace collapse) | landmark-aligned + pose-robust | pose probe |
| Near-threshold impostors | FAR band | sharper genuine/impostor separation (EER far lower at scale) | ambiguous-score / low-margin |
| **Feature > 1 KB** (64 KB) | **fails spec** | **512-byte embedding passes spec** | (enrollment uses SFace gallery) |

Note the last row: DL also fixes a **spec failure**, not just an accuracy gap.
The hybrid can keep LBPH's *speed* for the common case while adopting SFace's
*compact gallery* (512 B/identity) for the enrolled feature database — so the
system as a whole satisfies the <1 KB feature target that LBPH alone cannot.

---

## 6. Suggestion #2 — Raspberry Pi accelerator (speed vs. "feature size")

### The problem, stated precisely

"Processing-speed issues caused by feature size" shows up in two places:

1. **Heavy DL features are expensive on CPU.** SFace is a 37.8 MB float CNN; a
   per-face forward pass on the Pi 5 CPU is far too slow to run every frame and
   still hit ≥30 fps. The richer the feature, the heavier the inference.
2. **LBPH's 64 KB histogram doesn't shrink the problem.** It's small to *store*
   but matching scales with the enrolled gallery, and its detector (Haar) is the
   measured FPS bottleneck. On the Pi CPU even the "light" path is throughput-limited.

We don't want to *shrink the feature to fit the CPU* (that's what cripples the
classical subspace methods). We want to **keep the rich feature and move it off
the CPU.**

### The placement (what runs where)

```
   Raspberry Pi 5
   ┌───────────────────────────────┐        ┌──────────────────────────────┐
   │ CPU                            │        │ NPU accelerator (HAT/USB)    │
   │  • frame capture               │        │  • YuNet detect   (ONNX)     │
   │  • LBPH predict() (fast path)  │  ⇄     │  • SFace embed    (ONNX/INT8)│
   │  • quality probes + gate       │        │    (only on escalated frames)│
   │  • gallery match (dot product) │        │                              │
   └───────────────────────────────┘        └──────────────────────────────┘
```

- **YuNet + SFace are ONNX → they compile to the accelerator.** Detection runs
  there every frame; SFace runs there **only when the gate escalates**, so the
  NPU is never the per-frame bottleneck for clean inputs.
- **LBPH stays on the CPU** (it's a legacy OpenCV recognizer, not an NPU graph;
  but it's cheap, so that's fine).
- **Gallery match is a dot product** over 512-byte embeddings — trivial on CPU,
  independent of accelerator.

### Accelerator options

| Option | Form factor | Precision | Notes |
|---|---|---|---|
| **Hailo-8 / 8L (Pi AI HAT+)** — *recommended* | M.2 on Pi 5 | INT8 (compile ONNX → HEF) | Official Pi 5 path, 13–26 TOPS, highest headroom for SFace + YuNet together |
| **Google Coral USB** | USB | INT8 TFLite (Edge TPU compiler) | Needs ONNX → TFLite → EdgeTPU + INT8 quant |
| (Intel NCS2 / Myriad) | USB | — | Deprecated; do not target |

### INT8 quantization — we already have the muscle memory

The accelerators want INT8. The CV repo already ships an INT8 quantization flow
for a different model (`src/arcface_mobilenet_int8/quantize_model.py`) — the same
post-training-quantization recipe (representative calibration set → INT8) applies
to SFace. **Reuse that pipeline** to produce the on-device SFace weights, and
re-run the **independence test on the quantized model** so the deployed threshold
reflects INT8, not float (quantization can shift the score distribution).

### Expected effect

- Common-case frames: cost ≈ YuNet(NPU) + LBPH(CPU) → meets the high-FPS budget.
- Hard-case frames: add one SFace(NPU) forward → bounded by NPU throughput, not
  CPU; the accelerator is what keeps escalation from blowing the latency budget.
- Net: the hybrid can hold the **≥30 fps real-time / <100 ms latency** Stage-3
  target *because* the heavy feature lives on the NPU, not the CPU.

---

## 7. Deployment topology (maps to the staged master plan)

| Stage | Topology | What runs | This plan's role |
|---|---|---|---|
| 1 (done) | Server (PC + webcam) | CV (LBPH) | source track |
| 2 | Server–client (PC + Pi 5) | DL (YuNet+SFace) | source track |
| **3 (this doc)** | **Client-centered (Pi 5 + NPU)** | **Hybrid gate** | **the integration** |
| 4 | Client-centered (Pi 5) | Hybrid, real-world | hardening |

The hybrid is designed **client-centered from the start**: detector + DL on the
NPU, classical + gate on the CPU, gallery local. No server round-trip in the hot
path (a server remains optional for enrollment / logging).

---

## 8. Threshold calibration (one method, both gates)

Every threshold in §4 is set by the **independence test both teams already run** —
this is the project's core method, and the hybrid does not invent a new one:

1. Run LBPH independence vs LFW impostors → impostor distance distribution →
   `τ_accept` (100 ppm FAR = 73.04) and `τ_reject` (band edge ≈ 1% FAR = 76.85).
2. Run SFace independence (already done: LFW FP 0.07%) → SFace operating
   threshold at the **same FAR budget** (re-derive on the **INT8** model for the
   deployed point).
3. Calibrate the **quality-probe thresholds** (`τ_blur`, luma band, `τ_noise`,
   `τ_pose`, `px_min`) on the La Salle DB2 41-modification suite: pick the point
   on each modification where LBPH AR drops below the SFace AR — i.e. escalate
   exactly where DL starts winning. This is a measurable crossover, not a guess.
4. Report the **fused** TAR/FAR/FRR end-to-end (hybrid as one system) so Stage-3
   numbers are honest and comparable to the single-track baselines.

---

## 9. Implementation roadmap

Phased so each step is independently testable; nothing here rewrites either
recognizer's internals.

**Phase 1 — Unify detection (vendor the seam).**
Copy `face_detection_yunet_2023mar.onnx` (228 KB) into the CV repo at
`models/yunet_mobilefacenet/` (the path `detection.py` already expects), and set
`FACE_G3_DETECTOR=yunet` as the hybrid default. Confirm Haar↔YuNet parity on the
clean split. *Deliverable: one detector front-end, weights present in-repo.*

**Phase 2 — Port the SFace recognizer into a shared wrapper.**
New `src/sface/` (or `src/embedding/sface.py`) wrapping `cv.FaceRecognizerSF` from
the DL track's `dnn.py` / `feature-extract.py`: `enroll` → 512-B embedding
gallery (`.npy`/JSON), `score` → cosine, `far_of` → from the SFace impostor run.
*Deliverable: SFace usable through the same interface as LBPH.*

**Phase 3 — The `Recognizer` protocol + `HybridRecognizer`.**
Define the protocol (§3); make LBPH and SFace satisfy it. Implement
`HybridRecognizer` holding both + the gate (§4.2) + the quality probes. Modes:
`cascade` (default), `parallel`, `cv_only`, `dl_only`.
*Deliverable: `src/hybrid/` with the gate and a `predict()` returning the fused decision.*

**Phase 4 — Calibration + honest evaluation.**
Add `src/hybrid/calibrate.py` (derives all thresholds per §8 from the independence
runs + DB2 crossover) and a hybrid path in the evaluator that reports fused
TAR/FAR/FRR + escalation rate (what fraction of frames hit SFace) + per-stage
latency. Reuse `src/benchmark/` aggregation.
*Deliverable: `reports/benchmark/hybrid_comparison.md` — hybrid vs LBPH-only vs SFace-only.*

**Phase 5 — Launcher wiring.**
Add a **"Hybrid"** group to `main.py`'s `GROUPED_CHOICES` (enroll / evaluate /
live detect / calibrate), so switching modes is a menu choice — mirroring how the
classical and DL families are already exposed.
*Deliverable: `python main.py → Hybrid → live detect` runs the gated cascade.*

**Phase 6 — Pi + accelerator port.**
INT8-quantize SFace (reuse `arcface_mobilenet_int8/quantize_model.py` recipe),
compile YuNet+SFace for the target NPU (Hailo HEF or Coral EdgeTPU), wire the NPU
inference behind the SFace wrapper (CPU fallback if absent), re-run independence on
the quantized model, and measure on-device FPS/latency.
*Deliverable: hybrid running client-centered on the Pi 5 at the Stage-3 budget.*

### Files at a glance

- **New:** `models/yunet_mobilefacenet/face_detection_yunet_2023mar.onnx` (vendored),
  `src/sface/…`, `src/hybrid/{recognizer,gate,quality,calibrate}.py`,
  `src/benchmark/compare_hybrid.py`.
- **Edit:** `main.py` (Hybrid group), `src/classical_faces/pipeline.py`
  (expose LBPH behind the `Recognizer` protocol — additive, no behavior change).
- **Reuse as-is:** `src/classical_faces/detection.py` (YuNet backend),
  `face-detection-g3-dl/{dnn,feature-extract,loader}.py` (SFace reference),
  `src/arcface_mobilenet_int8/quantize_model.py` (INT8 recipe), the independence-test
  scripts (threshold calibration).

---

## 10. Risks & open questions

- **Escalation rate vs FPS.** If quality probes are too trigger-happy, too many
  frames hit SFace and FPS drops. Mitigation: calibrate probe thresholds at the
  *measured* LBPH↔SFace crossover (§8.3), and cap escalation rate as a tuned budget.
- **Two galleries or one?** LBPH needs its `.yml` gallery; SFace needs the 512-B
  embedding gallery. Same enrolled identities, two representations — enrollment
  must build both from the *same* aligned crops to stay consistent.
- **INT8 drift.** Quantized SFace ≠ float SFace; the deployed threshold must come
  from an independence run on the **quantized** model, not the float numbers in §1.
- **No-accelerator fallback.** If the NPU is absent, the system must degrade to
  `cv_only` (LBPH/CPU) rather than attempt SFace on the CPU at 30 fps. The mode
  switch (§4.3) is that fallback.
- **YuNet alignment vs LBPH preprocessing.** SFace wants YuNet's `alignCrop`
  (112×112 RGB); LBPH wants grayscale 100×100 + Tan-Triggs. The shared stage 0
  produces the *box + landmarks*; each recognizer applies its own normalization
  downstream. Keep those two normalizations explicit so neither silently changes.
- **Don't invent fused numbers.** Until Phase 4 runs, the hybrid TAR/FAR/FRR is
  *projected*, not measured. Report it as such.

---

## 11. One-paragraph summary for the team

> We already share a detector (YuNet) and an evaluation method (independence
> test). The hybrid adds a thin **decision gate** on top: LBPH handles clean
> frontal faces on the CPU at high FPS, and the gate **escalates to SFace only
> when LBPH is uncertain or the face is blurry / dark / noisy / off-pose** — the
> exact conditions we *measured* LBPH to fail. That is the professor's "DL
> compensates for CV" as a concrete runtime policy. The professor's second point —
> the **Pi accelerator** — is what makes the SFace escalation path cheap enough to
> hold 30 fps on-device: YuNet and SFace are ONNX, so they offload (INT8) to a
> Hailo/Coral NPU while LBPH and the gate stay on the CPU. Net result: the
> hybrid keeps LBPH's speed and SFace's robustness *and* its sub-1 KB feature,
> instead of compromising one for the other.
