# Systematic Single-Modification LFW2 Independence Testing Specification

**Author / Project:** USLS Computer Vision Group 3 (LS-Face / Smart Gate)  
**Version:** 0.81.0 (revised 2026-07-19)  
**Target Leg:** LFW2 (5,749 identities, 41 single-modification suites)  
**Document Status:** IMPLEMENTED 2026-07-19 (all seams built and verified on La Salle N=28: `--modification`, `--selection-manifest`, tier tagging, worker, merge, matrix — see §6 and `docs/BATCH_WORK/DESIGN.md` §12). Runtime and campaign scale remain **pending canary calibration** (§4.2); the v0.81 draft's throughput figures were estimates, not measurements, and are withdrawn. Executes as a distributed campaign per `docs/BATCH_WORK/DESIGN.md` (§4.5, §6.3).  

---

## 1. Executive Summary & Core Objective

The current independence testing methodology relies on broad, multi-factor synthetic corruption tiers (`light`, `medium`, `heavy`). While these tiers provide a fast high-level overview of transfer degradation, they aggregate heterogeneous image defects into a single empirical distance distribution—potentially obscuring individual failure modes.

This document specifies the **Systematic Single-Modification Independence Sweep Protocol** for LFW2. Instead of mixing multiple image corruptions into coarse tiers, this protocol systematically evaluates **each of the 41 modification variants individually** across the complete $N \times (N-1)/2$ unique impostor pair space of 5,749 identities ($16,522,626$ unique comparisons per variant).

### Primary Benefits
1. **Variable Isolation**: Isolate exact physical failure thresholds for each corruption type (e.g., distinguishing Gaussian Blur $7\times7$ breakdown from Contrast $0.55$ breakdown).
2. **Unidirectional Record Emission**: For the symmetric per-pair statistics (LBPH FAR, SFace FAR, joint-FP table), each unordered pair $\{i,j\}$ is recorded once instead of twice, halving the record/CSV volume. **This does not halve engine compute** — see §2.1 for what is and is not saved.
3. **Rigorous Diversity Tracking**: Evaluates pairwise error overlap (Yule's $Q$, Fisher's exact $p$-value) independently for every single corruption parameter, surfacing fine-grained engine complementarity.

---

## 2. Theoretical & Mathematical Framework

### 2.1 Unidirectional vs. Directional Impostor Sweeps

For a dataset of $N$ identities with 1 image per identity:
* **Full Directional Sweep ($N \times (N-1)$)**: Records ordered pairs $(i, j)$ and $(j, i)$ for $i \neq j$, totaling $5,749 \times 5,748 = 33,045,252$ records.
* **Unidirectional Unique Pair Sweep ($\frac{N(N-1)}{2}$)**: Records unordered pairs $\{i, j\}$ for $i < j$, totaling $\frac{5,749 \times 5,748}{2} = 16,522,626$ records.

**Symmetry status (verified 2026-07-19):** LBPH predict distance was checked empirically with the deployed parameters (radius 1, neighbors 8, grid $8\times8$, OpenCV 4.13) — $d(A,B) = d(B,A)$ exactly (max asymmetry 0.0 across all pairs of an 8-tile model). SFace cosine/L2 are symmetric by construction. The upper triangle therefore yields an identical empirical distance distribution for the marginal statistics.

**What halving does and does not save** (from the actual `run_sweep` implementation, `src/hybrid/independence_test.py`):

| Cost component | Halved by unidirectional? | Why |
|---|---|---|
| LBPH distances | **No** | One `predict_collect` call per *query row* returns the full row of $N$ distances; rows cannot be half-computed. Cost scales with query rows, not with recorded pairs. |
| SFace cosine/L2 | **No** (already negligible) | One 128-dim matvec per query row. |
| Cascade gate | **No — must stay directional** | The gate is one decision per *query probe* over its full non-self ranking (top-1, margin, quality). A pure $i<j$ pair loop would silently drop cascade false accepts whose accepted impostor has $j < i$. Cascade FP accounting stays per-query over all $N$ query rows. |
| Per-pair record loop + CSV/npz volume | **Yes** | This is the only stage where $(j,i)$ duplicates exist to skip. |

**Consequence:** unidirectional emission is an output-size optimization, not a compute optimization. Whether it is worth implementing at all is decided *after* the canary calibration (§4.2) shows how wall-clock splits between the LBPH phase and the record phase. Until then, sweeps run the same ordered-pair protocol as every other leg in the evidence matrix, keeping results directly comparable.

---

### 2.2 Invariant Protocol: Frozen Threshold Anchor

In compliance with the project's core experimental standards (`AGENTS.md` and `docs/PAPER.md`):

> **Thresholds are derived ONCE on La Salle DB1 clean originals and frozen.**

The operational thresholds stored in `src/hybrid/thresholds.json` (provenance per that file's own `provenance` block — the gate cutoffs are **carried from the LBPH vs 13,149 LFW impostors benchmark**, `reports/benchmark/tar_at_far.md`, not re-fit per dataset):
* **LBPH Accept Threshold ($\tau_{\text{accept}}$)**: $73.04$ — carried at $100\text{ ppm}$ FAR
* **LBPH Reject Threshold ($\tau_{\text{reject}}$)**: $76.85$ — carried at $\approx 1\%$ FAR
* **SFace Cosine Genuine Threshold ($\theta_{\text{cosine}}$)**: $0.363$
* **SFace $L_2$ Genuine Threshold ($\theta_{L2}$)**: $1.128$

(The $10,582\text{ ppm}$ figure quoted in the v0.81 draft is the La Salle DB1 *rank-based spec operating point* — the 8th error pair of 756 comparisons — reported by the independence test for context. It is not the derivation point of the deployed gate cutoffs and the two must not be conflated.)

Under no circumstances are decision cutoffs re-tuned or re-derived per modification. Every systematic single-modification sweep applies these exact frozen cutoffs to measure true out-of-domain transfer degradation.

---

## 3. Specification of the 41 Systematic Single-Modification Variants

The suite covers 12 modification families across 41 parameter levels (defined in `src/benchmark/modifications.py`):

| # | Modification Family | Parameter Level / Severity | Code Parameter | Total Variants |
|---|---|---|---|:---:|
| 1–4 | **Brightness Up** | `+15`, `+30`, `+45`, `+60` | `_brightness(img, offset)` | 4 |
| 5–8 | **Brightness Down** | `-15`, `-30`, `-45`, `-60` | `_brightness(img, offset)` | 4 |
| 9–11 | **Contrast Up** | `1.15`, `1.30`, `1.45` | `_contrast(img, factor)` | 3 |
| 12–14 | **Contrast Down** | `0.85`, `0.70`, `0.55` | `_contrast(img, factor)` | 3 |
| 15–17 | **Gamma Up** | `1.20`, `1.40`, `1.60` | `_gamma(img, gamma)` | 3 |
| 18–20 | **Gamma Down** | `0.80`, `0.65`, `0.50` | `_gamma(img, gamma)` | 3 |
| 21–24 | **Gaussian Noise** | $\sigma = 5$, $10$, $15$, $20$ | `_gaussian_noise(img, sigma)` | 4 |
| 25–27 | **Gaussian Blur** | $k = 3\times3$, $5\times5$, $7\times7$ | `_gaussian_blur(img, ksize)` | 3 |
| 28–30 | **Motion Blur** | $k = 3$, $5$, $7\text{ px}$ | `_motion_blur(img, ksize)` | 3 |
| 31–34 | **Rotation** | $-10^\circ$, $-5^\circ$, $+5^\circ$, $+10^\circ$ | `_rotation(img, angle)` | 4 |
| 35–38 | **Zoom** | $0.90\times$, $0.95\times$, $1.05\times$, $1.10\times$ | `_zoom(img, zoom)` | 4 |
| 39–41 | **Occlusion** | $7.5\%$, $12.5\%$, $17.5\%\text{ area}$ | `_occlusion(img, fraction)` | 3 |
| **Sum** | **12 Families** | **41 Individual Parameter Sets** | | **41** |

(Verified 2026-07-19 against `MODIFICATIONS` in `src/benchmark/modifications.py` — names, levels, and order match exactly; `VARIANT_COUNT = 41`.)

### 3.0 Tier Tagging (light / medium / heavy)

Each of the 41 variants carries a severity tier tag for grouped reporting
(`TIER_MAP` in `src/benchmark/modifications.py`, implemented 2026-07-19):
per family, the mildest level is `light`, the harshest `heavy`, interior
levels `medium`; the symmetric families rotation and zoom have only
`light` (±mild) and `heavy` (±harsh). Counts: light 14, medium 13,
heavy 14 (module-level assert enforces full 41-variant coverage). The tier
is a reporting group only — it does not change which sweeps run.
`systematic_matrix.md` sections and the FAR figure group by tier.
The mapping is an explicit dict Kyle can adjust in one edit.

### 3.1 Variant Realization: In-Memory, Not On-Disk

The v0.81 draft pointed the CLI at `data/lfw2_41mods/single_mods/<variant>/` directories. **Those directories do not exist and no generator script for them exists in the repo** (see the ground-truth table in `docs/BATCH_WORK/DESIGN.md` §2). Instead of generating, hashing, and distributing 41 on-disk probe sets, each variant is applied **in memory** at probe-load time:

* The independence test gains a `--modification <name>:<level>` flag (e.g. `--modification motion_blur:5`). After the clean tile is loaded and before LBPH normalization / SFace embedding, the transform from `src/benchmark/modifications.py` is applied, seeded via `stable_rng(seed, image_relpath, mod, level)`.
* `stable_rng` is per-(image, modification, level) deterministic and order-independent — the same guarantee `accuracy_ratio_hybrid.py` already relies on — so **any identity subset or query-row segment produces bit-identical probes to a full run**, on any member machine.
* The distribution unit is therefore a **single clean probe pack** (`docs/BATCH_WORK/DESIGN.md` §5 Approach B); all 41 variants derive from it locally. This removes the 41-dataset generation/hashing/upload problem entirely and makes the variant dimension shard-safe by construction.
* All N tiles receive the modification (queries and candidates alike, and the temporary LBPH model trains on the modified tiles) — consistent with how the existing tiered `lfw2_light`/`lfw2_medium` legs were run from fully-modified directories.

---

## 4. Execution Cost & Scale — Calibrate, Don't Estimate

### 4.1 Pair Arithmetic (exact)

* **Identities ($N$)**: 5,749
* **Ordered pairs per sweep** ($N(N-1)$): $33,045,252$; unique pairs ($N(N-1)/2$): $16,522,626$
* **Total across 41 sweeps**: $1.355\text{B}$ ordered / $677.4\text{M}$ unique pair records

### 4.2 Runtime: No Number Until the Canary Says So

The v0.81 draft claimed 60,000–80,000 pairs/sec and a ~3-hour single-machine total. **That figure was not a measurement and is withdrawn.** No wall time for any full hybrid LFW sweep is recorded anywhere in the repo (checked 2026-07-19: `reports/independence/lbph_lfw1/summary.json` has no timing field, and that Jul-8 run used the classical *streaming* LBPH path, not the hybrid `run_sweep`, which is a different and slower code path: sequential `predict_collect` per query row plus a pure-Python per-pair record loop).

The project's own premise (`docs/BATCH_WORK/DESIGN.md` §1) is that **one** 33M-pair hybrid sweep is too slow for a single machine — 41 sweeps is ~20× that work and is planned as a **distributed campaign**, not a single-machine run. The real cost model comes from the batch campaign's canary (`DESIGN.md` §6.1 phase 3): every member runs an identical fixed 64-identity sweep whose wall-clock is recorded in the manifest. Assignment sizing, per-variant runtime, and the go/no-go on the full 41-variant scope are all decided from canary numbers plus one timed full single-variant sweep — never from hardware-spec extrapolation.

Per-sweep cost anatomy (query rows dominate, from the code): $N$ `predict_collect` calls, each scoring the probe against all $N$ model histograms; one 128-dim matvec per query row for SFace; one gate decision per query row; then the per-pair record loop. Row-slicing (segments) divides all four linearly.

### 4.3 RAM Footprint (arithmetic from array shapes, confirmed small)

* SFace embeddings: $5,749 \times 128 \times 4\text{ B} \approx 2.9\text{ MB}$
* LBPH model histograms: $5,749 \times 16,384 \times 4\text{ B} \approx 377\text{ MB}$ (grid $8\times8$ × 256 bins = 16,384 dims — the v0.81 draft's "2,048 dims / 47 MB" was wrong by 8×)
* Sliced distance matrices: $\text{seg\_len} \times 5,749 \times 8\text{ B}$ (LBPH float64) + $2 \times \text{seg\_len} \times 5,749 \times 4\text{ B}$ (cos/L2 float32) — e.g. ~92 MB total at seg_len = 720 (8 segments)
* Comfortably inside member laptops' RAM; the canary manifest records real peak RSS rather than trusting this arithmetic.

### 4.4 Trade-off Comparison: Tiered Pooled vs. Systematic Per-Variant Suite

| Evaluation Mode | Number of Sweeps | Unique Pairs ($N(N-1)/2$) | Directional Pairs ($N(N-1)$) | Runtime | Primary Analytical Purpose |
|---|---:|---:|---:|---:|---|
| **Tiered Pooled (3 Tiers)** | 3 sweeps (`light`, `medium`, `heavy`) | **49,567,878** | **99,135,756** | measure via canary | High-level transfer degradation overview |
| **Systematic Per-Variant Suite** | **41 sweeps** (all parameter levels) | **677,427,666** | **1,354,855,332** | measure via canary; ~13.7× the tiered load | ⭐ Pinpoint single-variable corruption breakdown & 41-point Yule's $Q$ spectrum |

**Scale-reduction options if calibration says the full suite is too heavy** (decision for Kyle after the canary round):
1. **Seeded identity subset per variant** (existing `--max-identities`): e.g. $N=2{,}000$ → 3.998M ordered pairs per variant, an 8.3× reduction. Caveat for the paper: impostor pairs share identities, so nominal pair counts overstate effective statistical precision at *any* $N$ — Wilson CIs on pair counts are optimistic in both designs.
2. **Family-endpoint first wave**: run the mildest and harshest level of each family (~24 variants), filling in interior levels only where the endpoints disagree.

---

## 5. Statistical Output & Deliverables

For each of the 41 modification sweeps, the execution engine writes structured artifacts to `reports/independence/systematic_lfw2/<mod_name>/`:

1. **`summary.json`**:
   * **Marginal False Acceptance Rates**: LBPH-only, SFace-only, and Fused Cascade FAR with 95% Wilson Confidence Intervals.
   * **Diversity & Error Overlap**: 
     * Observed vs. Expected Joint False Positive Ratio ($\frac{P(A \cap B)}{P(A)P(B)}$)
     * Yule’s $Q$ Statistic ($\frac{ad - bc}{ad + bc}$)
     * Disagreement Measure ($D$) & Double Fault Rate ($DF$)
     * Fisher's Exact Test $p$-value for error co-occurrence.
   * **Cascade Efficiency**: Escalation percentage and breakdown of gate reasons (Quality, Margin, Ambiguous Band).

2. **Distance & Distribution Plots**:
   * Distance histogram vs. clean LFW1 baseline.
   * FAR operating curve vs. frozen threshold $\tau_{\text{accept}}$.

3. **`systematic_matrix.md` & `systematic_matrix.json`**:
   * Consolidated 41-row master table summarizing degradation-distance compression across all 12 families.

4. **Per-pair record policy (new — the v0.81 draft was silent on this):** a full
   `comparisons.csv` across 41 sweeps is $677\text{M}$–$1.36\text{B}$ rows
   including two path strings per row — plausibly $>100\text{ GB}$ plain, still
   tens of GB gzipped. That is not shippable by members. Policy:
   * Default per variant: `records.npz` (compact fixed-width arrays — the fields
     `run_sweep` already produces) + `summary.json`. No per-pair CSV.
   * One **designated audit variant** (Kyle picks, e.g. `motion_blur:5`) runs
     with the full `comparisons.csv.gz` for row-level auditability of the
     pipeline, per the campaign's audit rule.
   * CSV for any other variant is regenerable centrally from its `records.npz`.

---

## 6. CLI Command & Orchestration Workflow

Implementation status (2026-07-19, second pass): everything below is
**implemented and verified** (`docs/BATCH_WORK/DESIGN.md` §12):
`--segment-count`/`--segment-index`, `--modification <name>:<level>`
(in-memory via `stable_rng`, byte-identical under any segmentation and
bit-matched to `accuracy_ratio_hybrid.py` probes for the same
(image, mod, level)), and `--selection-manifest` (SHA-256-verified probe
selection, 0-based iteration keys, generated by
`scripts/utils/make_selection_manifest.py`). Campaign orchestration runs through
`scripts/pipeline/lfw2_worker.py`; merging through `scripts/utils/merge_lfw2_segments.py`;
the 41-row table and figure through `scripts/archive/build_systematic_matrix.py`.
The v0.81 draft's `--unidirectional` flag is dropped pending the
§2.1 / §4.2 decision.

### 6.1 Running One (Variant × Segment) Work Unit
```bash
python -m src.hybrid.independence_test \
    --dataset-dir data/lfw-dataset \
    --selection-manifest docs/BATCH_WORK/selection_manifest_lfw.json \
    --modification motion_blur:5              # in-memory via stable_rng (§3.1) \
    --segment-count 8 --segment-index 3       # output dir auto-suffixed _seg3of8 \
    --output-dir reports/independence/systematic_lfw2/motion_blur_5 \
    --iterations 1
```

Members do not run this directly — `scripts/pipeline/lfw2_worker.py --member <name>`
reads their (variant, segment) units from `docs/BATCH_WORK/assignments.json`,
runs preflight (pins/version checks), the canary, each unit, and packages one
upload zip per unit (`comparisons.csv.gz` + `summary.json` + `manifest.json`).
See `docs/BATCH_WORK/MEMBER_GUIDE.md`.

### 6.2 Campaign Orchestration
The 41-variant suite runs through the batch-work worker
(`scripts/pipeline/lfw2_worker.py`, `DESIGN.md` §6.1, BUILT + dry-run verified): one
work unit = **(variant, segment)**, assigned per member in
`docs/BATCH_WORK/assignments.json`. Kyle merges each variant's returned zips
with `scripts/utils/merge_lfw2_segments.py` (coverage proof + count-sum merge,
verified byte-identical reassembly), then builds the 41-row tier-grouped
`systematic_matrix.md`/`.json` + FAR figure with
`scripts/archive/build_systematic_matrix.py` (missing variants render as PENDING,
never invented). A dedicated single-machine harness is only worth writing if
the canary calibration (§4.2) shows a single machine can realistically carry
whole variants.

---

## 7. Integration with Deliverables (`docs/PAPER.md`)

The output from this systematic suite directly provides:
1. **Section 4.3 (Robustness & Degradation Transfer)**: Quantifies exact distance distribution compression for each of the 12 corruption families.
2. **Section 4.5 (Joint Error Independence & Diversity)**: Replaces coarse tier averages with a comprehensive 41-point Yule's $Q$ spectrum, proving where CV and DL errors remain independent vs. where they co-occur.

Statistical honesty note for both sections: impostor pairs share identities
(each identity appears in $N-1$ pairs), so pair-count Wilson intervals
overstate effective precision. State this caveat wherever per-variant CIs are
quoted, exactly as the existing pooled-iterations caveat is stated in
`summary.json`.

### 7.1 Execution Dependency

This suite is a consumer of the batch-work infrastructure
(`docs/BATCH_WORK/DESIGN.md`), all of which is now implemented and verified
(§12 there, including the §12.5 dry campaign on La Salle): segment wiring,
the `--modification` seam (§3.1), selection manifest, canary, pins, worker
with variant axis, and merge. What remains before the real campaign is
operational, not code: generate `selection_manifest_lfw.json` from a
downloaded LFW1, pin the campaign commit in `batch_pins.json` and
`assignments.json`, fill real member names, and run the canary round to size
assignments (§4.2).
