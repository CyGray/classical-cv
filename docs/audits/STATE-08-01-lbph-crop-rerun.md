# STATE 2026-08-01 — LBPH independence re-run on YuNet: findings only, no config change

**Nothing in `src/hybrid/thresholds.json` (or any of its sync locations) was
changed by this work.** This file records what was measured and what it implies.
The adopt/revert decision is explicitly deferred to Kyle.

## What was run

Two sweeps, both on `data/lfw-dataset`, N=5,749, **0 detector skips**,
16,522,626 unique cross-identity pairs, seed 42, YuNet, LBPH radius=1 /
neighbors=8 / grid=8x8, native `predict_collect()` scale, **identical
per-identity probe picks**:

1. **Standalone LBPH** — `scripts/archive/run_lfw_lbph_native_predict_independence.py`,
   which crops to the detected face box (`assume_cropped=False`).
2. **Hybrid joint sweep** — `scripts/archive/run_hybrid_independence_no_pair_csv.py`
   (this branch; wraps `src/hybrid/independence_test.py`), which normalizes the
   **full frame** for LBPH.

## Measured

| Quantity | Standalone (cropped) | Hybrid (full-frame) |
|---|---:|---:|
| LBPH @ rank 165 (9.9863 ppm) | **67.033255** | **74.644440** |
| LBPH @ rank 165,226 (1.0000%) | **74.349590** | **89.106094** |
| SFace L2 @ rank 165 | — | 1.030628 |
| SFace L2 @ rank 165,226 | — | 1.191515 |
| SFace cosine @ 165 / 165,226 | — | 0.468903 / 0.290145 |

Boundary pairs — standalone: rank-165 `Ahmed_Qureia` vs `Ferenc_Madl`;
rank-165226 `Bob_Hartley` vs `Ravan_AG_Farhadi`. Hybrid: rank-165
`Chris_Claiborne` vs `Richard_Parsons`; rank-165226 `Andy_Hebb` vs
`Gunter_Pleuger`.

## Finding 1 — the 77.77-vs-67.01 gap is the crop, not the detector

`FROZEN_THRESHOLDS_HYBRID.md` attributes the gap to Haar vs YuNet. That is
wrong. Both sweeps above use YuNet on the same images with the same picks; the
only difference is the crop, and it accounts for **67.03 -> 74.64 (+11.4%)**.

- `src/hybrid/independence_test.py:286` runs YuNet, but uses it only for SFace
  alignment, `face_px`, and the quality probe. LBPH's tile is
  `normalize_face(gray, ...)` at `:302` — the whole frame.
- Deployment crops: `src/hybrid/detect.py:257` (live path) calls
  `detect_sample(..., assume_cropped=False)`, and `LBPHAdapter._normalize`
  (`src/hybrid/recognizer.py:190`) normalizes `sample.face_gray`.

This is **not a bug in the hybrid test as designed.** Its default dataset is
`data/lasalle_db1_processed` — 100x100 pre-cropped tiles, where the tile *is*
the face and full-tile normalization is correct (`make_sample()`,
`src/hybrid/recognizer.py:90-95`). It becomes wrong only when the test is
pointed at raw 250x250 LFW frames. `src/hybrid/calibrate.py:101,161` has the
same `assume_cropped=True` assumption baked in, which is how a full-frame number
reached a config consumed by a cropping runtime.

Separately, the frozen Haar-derived 67.0084 and this YuNet cropped 67.033255 are
**0.037% apart** — the detector swap does not move `tau_accept`, even though
YuNet keeps the 46 identities Haar dropped.

## Finding 2 — the deployed LBPH gate does not match the distribution it runs on

`thresholds.json` currently holds `tau_accept` 77.7693 / `tau_reject` 88.4927 /
`l2_genuine` 1.0313 — i.e. the full-frame candidates from
`FROZEN_THRESHOLDS_HYBRID.md`, which that document still describes as *"candidate,
not adopted."* Against the cropped (deployment-faithful) distribution:

| Threshold | Deployed | Cropped re-run | Gap |
|---|---:|---:|---:|
| `tau_accept` | 77.7693 | 67.0333 | +16.0% |
| `tau_reject` | 88.4927 | 74.3496 | +19.0% |
| `l2_genuine` | 1.0313 | 1.030628 (hybrid-derived) | +0.065% |

Measured directly — the realized FAR of each candidate value on the cropped
(deployment) LBPH distribution, same sweep conditions, 16,522,626 unique pairs:

| Value | Role | Realized FAR (cropped) | vs ~10 ppm target |
|---:|---|---:|---|
| **67.0084** | committed `tau_accept` | **9.62 ppm** (159 pairs) | **on target** |
| 67.033255 | this re-run, rank 165 | 9.99 ppm (165 pairs) | on target |
| **77.7693** | proposed `tau_accept` | **5.3635%** (886,192 pairs) | **~5,370x looser** |
| 76.85 | committed `tau_reject` | 3.6443% (602,141 pairs) | — |
| **88.4927** | proposed `tau_reject` | **56.80%** (9,385,438 pairs) | — |
| 74.3496 | this re-run, rank 165,226 | 1.0000% (165,227 pairs) | — |

FAR target -> cropped threshold: 0.001% -> 67.0333 | 0.01% -> 68.8808 |
0.1% -> 71.1718 | 1% -> 74.3496 | 5% -> 77.5943 | 10% -> 79.5150 |
50% -> 87.3465.

So the **committed 67.0084 is correct** — it realizes 9.62 ppm against its
10 ppm design target. The proposed 77.7693 would accept **5.36% of impostor
pairs on LBPH alone, without escalating to SFace**. `tau_accept` is the edge
below which LBPH accepts unverified, which is what makes this the
safety-critical one. The SFace value is independently reproduced and needs no
action.

Note also that the committed `tau_reject` = 76.85 realizes 3.64%, not the ~1%
its provenance claims; the true 1% point on cropped YuNet data is 74.3496.
Both sweeps cross-check: 67.0333 -> 9.99 ppm and 74.3496 -> 1.0000% reproduce
the rank-165 and rank-165,226 results exactly.

Corroborating: the hybrid run applies the *old* frozen 67.0084 to its inflated
full-frame distances and logs only **44 LBPH false accepts in 33,045,252 ordered
pairs (1.33 ppm)** against a ~10 ppm target, with **99.4% escalation**. Its
reported `Yule Q = 1.000` / observed-vs-expected joint FP of 19,938 rest on 6
joint FPs at that distorted operating point and should not be cited as evidence
of error dependence.

## Finding 3 — the pinned selection manifest is unusable, and LFW copies differ

`docs/features/BATCH_WORK/selection_manifest_lfw1_hybrid.json` is pinned to
`face-detection-g3/data/lfw-dataset`, which **no longer exists on this machine**.
Every one of its SHA-256 entries mismatches `data/lfw-dataset`, so
`load_selection_manifest()` aborts. Regenerated as
`selection_manifest_lfw1_classical.json` via
`scripts/archive/make_lfw_selection_manifest.py`.

The two manifests select the **identical 5,749 files** — same identities, same
relpaths, zero differences — yet all hashes differ. Same filenames, different
pixels. The engines respond asymmetrically, which is a useful diagnostic:

- SFace L2: 1.031255 -> 1.030628 (**0.06%**) — aligns via landmarks.
- LBPH: 77.769348 -> 74.644440 (**4.0%**) — full-frame, no alignment step.

Note also that the 1%-FAR point reproduces across copies far better (88.4927 vs
89.1061, 0.7%) than the 10 ppm point (77.7693 vs 74.6444, 4.2%). Deep-tail
thresholds — 165 pairs out of 16.5M — should not be carried between dataset
copies.

## Open decision

Whether to move `tau_accept` / `tau_reject` back onto the cropped scale is
**not decided here**. If it is taken, `FROZEN_THRESHOLDS.md`'s "Where these
values live (keep in sync)" list applies (`thresholds.json`, `gate.py`
`_FALLBACK_GATE_DEFAULTS`, `calibrate.py` `LBPH_TAU_ACCEPT`,
`sface/recognizer.py` `L2_GENUINE_THRESHOLD`), and the following also need
reconciling, since they currently disagree with each other and with the config:
`FROZEN_THRESHOLDS.md`, `FROZEN_THRESHOLDS_HYBRID.md` (whose "not adopted"
status line is now false), the workspace-root `AGENTS.md`, the root
`reports/independence/independence_report.md`, and the `cv-repo-map` skill's
hardcoded threshold table.
