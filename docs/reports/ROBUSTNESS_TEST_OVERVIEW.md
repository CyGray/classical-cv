# Robustness Test — Simple Overview

## What this test checks

Real photos aren't perfect — too dark, blurry, tilted, noisy, zoomed weird, or partly covered. This test checks whether the face recognition system still recognizes the right person even when the photo is damaged like that.

It compares three versions of the system side by side:

| Mode | What it is |
| --- | --- |
| **CV Only** | The classical engine alone (LBPH) |
| **DL Only** | The deep learning engine alone (SFace) |
| **Hybrid Cascade** | The combined system — LBPH tries first, SFace steps in when LBPH isn't confident |

## What "damage" gets tested

Every clean test photo gets put through 12 kinds of damage, at several strength levels each, for **41 total damaged versions per photo**:

- Brightness up / down
- Contrast up / down
- Gamma up / down
- Gaussian noise (graininess)
- Gaussian blur
- Motion blur
- Rotation (tilt)
- Zoom in / out
- Occlusion (part of the face blocked)

Each damage type has a **light / medium / heavy** version, so the report can show where a mode starts to break, not just whether it breaks.

## How "pass" is measured

For each damaged photo, a mode "passes" if it:
1. Picks the correct person, **and**
2. Its confidence score clears that engine's accept threshold.

The percentage of damaged photos that pass this is called the **Accuracy Ratio (AR)**. Higher AR = holds up better under that damage.

## The complete flow, step by step

1. **Pick the test photos** — one clean, held-out photo per person, chosen the same way every time (same random seed) so results are reproducible and comparable across runs.
2. **Register everyone** — each engine "learns" the clean photos first (LBPH trains a model file, SFace stores a face-embedding gallery). This step is cached, so it only happens once per dataset.
3. **Damage every photo** — apply all 41 damage variants to each clean photo.
4. **Run all three modes on every damaged photo** — detect the face, then score it with CV Only, DL Only, and the Hybrid Cascade.
5. **Tally the results** — for every (damage type, strength level), record each mode's Accuracy Ratio, plus how often the Hybrid Cascade had to escalate from LBPH to SFace.
6. **Split the work up (for big datasets)** — a large dataset like LFW2 is split into segments and run in parallel across multiple worker processes, then all segment results get merged back into one unified report.
7. **Summarize into Light / Medium / Heavy tiers** — the 41 results get grouped by damage severity into a simple table (and matching PNG images) so it's easy to see, per mode, how accuracy holds up as damage gets worse.

## Where the results live

- Raw numbers: `reports/benchmark/accuracy_ratio_hybrid.json` / `.md`
- Severity-tier tables: `reports/benchmark/robustness_tables.md`
- Picture versions of the tables: `reports/figures/robustness_table_*.png` and `hybrid_robustness_tables.png`
- Large-dataset (LFW2) run: `reports/benchmark/lfw2_robustness/`

## Why it matters

This is the test that answers: *"If the camera catches someone in bad lighting, at an angle, or slightly out of focus, does the system still get it right — and does combining both engines actually help, or just add complexity?"*

---

# Comprehensive Version

This section covers the same test with the actual formulas, thresholds, and code paths, for anyone implementing, auditing, or citing the numbers. Terms like enrollment, feature DB, augmentation, and independence test are used as-is (no simplification).

## 1. Scope, and how this differs from the Independence Test

This is the **41-modification Accuracy Ratio (AR) battery**
(`src/benchmark/accuracy_ratio_hybrid.py`) — an **identification-axis** test:
for the same enrolled identity, does a degraded probe still get matched to
that identity and clear the accept threshold?

This is a **different 2×2 table** from the [Systematic Independence
Test](../features/SYSTEMATIC_INDEPENDENCE_TEST.md), which is an
**impostor-pair / false-accept-axis** test: across all $N(N-1)/2$ identity
pairs, does the system wrongly accept two different people as the same one?
Both share the same augmentation code (`src/benchmark/modifications.py`,
`stable_rng`) and the same frozen thresholds, but they answer different
questions and are not interchangeable.

## 2. Probe set and enrollment (feature DB construction)

- **Selection**: `select_originals(base_dir, select_one_per_person=True, seed=42)` — one image per identity folder, chosen deterministically by seeding `random.Random(42)` and walking sorted person folders. Default `--originals-dir` is the held-out `data/split_lasalle/test`; the LFW2 harness (`scripts/pipeline/run_lfw2_robustness.py`) points this at `data/lfw-dataset` instead.
- **Enrollment (feature DB build)**: each identity's clean image is run through YuNet detection, then:
  - **LBPH**: the gray face crop is normalized (`normalize_face`, fixed `IMG_SIZE`, equalization per `SPECS["lbph"]`) and trained into an OpenCV `cv2.face.LBPHFaceRecognizer` (`radius=1, neighbors=8, grid_x=8, grid_y=8`), saved as a `.yml` model + a `labels.json` person↔label map.
  - **SFace**: an embedding is extracted per identity (`feature_from_row` via YuNet landmarks, or `feature_from_crop` if YuNet missed) and stored as a gallery `.npy` + `labels.json` — this is the "feature DB" SFace matches against.
  - For LFW2 this enrollment is cached under `models/lfw2/` keyed by `(lfw_root, seed)` in a `manifest_*.json`; a matching manifest skips re-enrollment.
- **Probe generation**: each clean image is passed through all 41 `(modification, level)` transforms from `MODIFICATIONS`, each seeded via `stable_rng(seed, person, filename, mod_name, level)` — deterministic and shard-safe, so any segment slice reproduces bit-identical probes to a full run.

## 3. The three modes and their accept rules

| Mode | Engine(s) | Accept rule |
| --- | --- | --- |
| `cv_only` | LBPH alone | correct identity **and** `lbph_distance <= tau_accept` |
| `dl_only` | SFace alone | correct identity **and** `cosine >= cosine_genuine` **and** `l2 <= l2_genuine` |
| `cascade` | LBPH fast path + SFace escalation | see gate logic, §5 |

**Frozen thresholds** (`src/hybrid/thresholds.json`, current as of 2026-07-28 — see the repo's `cv-repo-map` skill before quoting these anywhere else, since this repo has two non-comparable LBPH distance scales and it's easy to grab the wrong one):

| Threshold | Value | Meaning |
| --- | ---: | --- |
| `gate.tau_accept` | **67.0084** | LBPH distance ≤ this ⇒ confident accept (native `predict_collect()` scale) |
| `gate.tau_reject` | 76.85 | LBPH distance ≥ this ⇒ confident reject |
| `gate.margin_min` | 0.05 | minimum relative top1/top2 margin (below this ⇒ escalate) |
| `sface.cosine_genuine` | 0.363 | SFace cosine ≥ this required to accept |
| `sface.l2_genuine` | **1.018** | SFace L2 ≤ this required to accept |

LBPH's raw score is a **distance** (lower = better match), so `tau_accept < tau_reject` by construction.

## 4. The 41 modifications

12 families, 41 parameter levels total (`MODIFICATIONS` in `src/benchmark/modifications.py`):

| Family | Levels | Count |
| --- | --- | ---: |
| `brightness_up` / `brightness_down` | ±15, ±30, ±45, ±60 | 4 + 4 |
| `contrast_up` / `contrast_down` | 1.15/1.30/1.45, 0.85/0.70/0.55 | 3 + 3 |
| `gamma_up` / `gamma_down` | 1.2/1.4/1.6, 0.8/0.65/0.5 | 3 + 3 |
| `gaussian_noise` | σ = 5, 10, 15, 20 | 4 |
| `gaussian_blur` | k = 3, 5, 7 | 3 |
| `motion_blur` | k = 3, 5, 7 px | 3 |
| `rotation` | −10°, −5°, +5°, +10° | 4 |
| `zoom` | 0.90×, 0.95×, 1.05×, 1.10× | 4 |
| `occlusion` | 7.5%, 12.5%, 17.5% of area | 3 |
| **Total** | | **41** |

**Severity-tier bucketing** (Light/Medium/Heavy, `generate_robustness_report.py::tier_ar`): a per-family severity function maps each level to a magnitude —

- brightness / noise / blur / rotation / occlusion: `severity = abs(level)`
- contrast / zoom: `severity = abs(level - 1.0)`
- gamma: `severity = abs(log(level))`

The distinct severities within a family are rank-ordered; each level's rank fraction `f = rank / (m - 1)` (0 for mildest, 1 for harshest) is rounded into 3 buckets via `round(f * 2)` → 0 = Light, 1 = Medium, 2 = Heavy. Symmetric families (e.g. rotation ±5°/±10°) put both signs of the same magnitude in the same tier.

## 5. The escalation gate (`src/hybrid/gate.py::decide_escalation`)

Given the LBPH distance $d$, the relative top1/top2 margin $m = (d_2 - d_1)/d_1$, and a `QualityReport`, escalate to SFace if **any** of, checked in this precedence order:

1. **Quality override** — `quality.any_flag` is true (see §6). This clause can override even a confident LBPH score.
2. **Ambiguous band** — `tau_accept < d < tau_reject`.
3. **Thin margin** — `m < margin_min` (0.05), i.e. the runner-up identity is within 5% of the best distance.

If none fire: `d <= tau_accept` ⇒ accept on LBPH (`confident_accept`); otherwise ⇒ reject as Unknown (`confident_reject`). No SFace call happens on these two non-escalated paths.

## 6. Quality probes (`src/hybrid/quality.py::compute_quality`)

Five cheap signals computed on the LBPH crop + YuNet landmarks, each thresholded against the calibrated values in `thresholds.json["quality"]`:

| Flag | Measurement | Formula | Current threshold |
| --- | --- | --- | ---: |
| `blur` | variance of Laplacian | $\mathrm{Var}(\nabla^2 I)$ | `< 587.83` |
| `low_light` | mean luma | $\mathrm{mean}(I)$ | `< 52.88` or `> 137.71` |
| `noise` | Immerkaer (1996) noise σ | $\sigma = \dfrac{\sqrt{\pi/2}}{6(w-2)(h-2)}\sum \lvert I * K\rvert$, $K=\begin{bmatrix}1&-2&1\\-2&4&-2\\1&-2&1\end{bmatrix}$ | `> 8.206` |
| `off_pose` | roll/yaw angle from 5 YuNet landmarks | $\max(\lvert\text{eye-roll}\rvert,\ \text{nose-yaw proxy})$, degrees | `> 63.74` |
| `small_face` | YuNet box side | $\min(h, w)$ px | `< 61` |

## 7. Metrics computed per (modification, level)

- **Accuracy Ratio**: $\mathrm{AR} = 100 \times K / M$, where $K$ = probes with correct identity **and** within the mode's accept threshold, $M$ = total probes for that (modification, level).
- **Per-modification AR**: mean AR across its levels, plus a pooled-binomial view (`matched` summed over all level probes for that modification) reported with a **Wilson 95% CI**:
$$\hat p \pm \; \text{via } \;\text{center} = \frac{p + z^2/2n}{1+z^2/n}, \quad \text{half-width} = \frac{z}{1+z^2/n}\sqrt{\frac{p(1-p)}{n} + \frac{z^2}{4n^2}}, \quad z = 1.95996\ (95\%)$$
- **`dl_minus_cv_points`**: `dl_only AR − cv_only AR`, tagged `cv_stronger` / `dl_stronger` / `tie` (tie if `|Δ| ≤ 2.0` percentage points, `AR_TIE_TOLERANCE`).
- **`cascade_vs_best_points`**: `cascade AR − max(cv_only AR, dl_only AR)` — is the fused system beating the better of its two parts?
- **`cascade_escalation_percent`**: share of probes the gate routed to SFace.
- **No-face count**: per (mod, level), how many probes YuNet failed to detect a face on (see `--no-face-policy` below).

## 8. Complementarity battery (identification-axis 2×2)

For every probe, `cv_correct` / `dl_correct` booleans build a 2×2 table (per modification, and pooled over all modified probes):

|            | DL correct | DL wrong |
|------------|:---:|:---:|
| **CV correct** | w (both right) | x (CV-only right) |
| **CV wrong**   | y (DL-only right) | z (both wrong) |

- **Recovery rate** = $y / (y+z)$ with Wilson CI: *given LBPH is wrong, how often does SFace still get it right.*
- **Both-fail rate** = $z / n$ with Wilson CI: the accuracy floor no fusion of these two engines can beat.
- **McNemar's test** (`mcnemar_test(x, y)`) on the discordant cells $x, y$: is the CV-only-right vs DL-only-right split lopsided enough to be real?
  - Exact form: $p_{exact} = \min(1,\ 2\sum_{k=0}^{\min(x,y)} \binom{x+y}{k} 0.5^{x+y})$
  - Continuity-corrected chi-square: $\chi^2 = \dfrac{(|x-y|-1)^2}{x+y}$, $p_{\chi^2} = \mathrm{erfc}(\sqrt{\chi^2/2})$

## 9. Gate competence (does the LBPH signal predict its own failure?)

Only for `cascade` runs, over probes that reached the gate (excludes strict-policy no-face rows):

- **AUC** of `lbph_distance` (and of `-lbph_margin`) for predicting "LBPH wrong", via the Mann-Whitney rank formula with midrank ties: $\mathrm{AUC} = \dfrac{U}{n_{pos}\, n_{neg}}$, $U = R_{pos} - \dfrac{n_{pos}(n_{pos}+1)}{2}$ ($R_{pos}$ = sum of midranks of the positive class = "LBPH wrong").
- **Deployed-rule confusion matrix**: escalate vs. LBPH-actually-wrong — TPR (recall of wrong), FPR (false-escalate rate on already-right probes), precision, plus a breakdown of escalation reasons (`quality:*`, `ambiguous_band`, `low_margin`) among the true-positive escalations.

## 10. Execution mechanics

- **No-face policy** (`--no-face-policy`): `fallback` (default) scores the whole undetected tile without landmarks (SFace resizes the raw crop); `strict` counts the probe as failed for every mode — this is the "deployed system, detection included" view. No-face counts are reported either way.
- **`--reuse-engine-scores`**: memoizes each engine's score per sample object (`_ScoreMemo`) so `cv_only` and `cascade` don't redundantly re-run identical LBPH/SFace work on the same probe (~3× less work for AR/battery runs; disables per-mode latency numbers, so it's off for latency-bearing runs).
- **Parallel segmentation** (LFW2 scale): `scripts/pipeline/run_lfw2_robustness.py` splits the query identities into `--num-segments` (auto: `max(16, num_workers)`), runs each as a subprocess of `accuracy_ratio_hybrid.py --segment-count --segment-index`, capped to a hardware-profile-derived `num_workers` so BLAS/OpenMP threads per process can't oversubscribe the machine. A finished segment (`seg{i}of{n}.json` + matching CSV) is skipped on re-launch — delete its files to force a redo.
- **Merge** (`scripts/utils/merge_robustness_segments.py`): combines all segment JSON/CSV outputs into one `accuracy_ratio_hybrid.{json,md}` + `accuracy_ratio_hybrid_probes.csv`.
- **Report generation** (`scripts/reporting/generate_robustness_report.py`): reads the merged JSON, applies the severity-tier bucketing (§4), writes `robustness_tables.md` and renders per-mode + composite 2×2 PNG tables to `reports/figures/`.

## 11. Output artifacts

| Artifact | Contents |
| --- | --- |
| `reports/benchmark/accuracy_ratio_hybrid.json` / `.md` | Full per-(modification, level) AR, CIs, escalation %, battery stats, gate competence |
| `reports/benchmark/accuracy_ratio_hybrid_probes.csv` | Per-probe rows: modification, level, person, file, no_face, cv_correct, dl_correct, escalated, gate_reason, lbph_distance, lbph_margin |
| `reports/benchmark/robustness_tables.md` | Light/Medium/Heavy tier tables per mode |
| `reports/figures/robustness_table_{mode}.png`, `hybrid_robustness_tables.png` | Rendered tier tables |
| `reports/benchmark/lfw2_robustness/` | LFW2-scale segment outputs + merged report |
| `models/lfw2/*` | Cached LFW2 enrollment (LBPH `.yml`, SFace gallery `.npy`, label maps, manifest) |

## 12. Example CLI

```bash
# Held-out La Salle test set, all three modes, single machine
python -m src.benchmark.accuracy_ratio_hybrid \
    --originals-dir data/split_lasalle/test \
    --modes cv_only,dl_only,cascade \
    --select-one-per-person --seed 42 \
    --reuse-engine-scores

# LFW2 scale, parallel workers, auto-enrollment + auto-merge
python scripts/pipeline/run_lfw2_robustness.py \
    --lfw-root data/lfw-dataset \
    --num-workers 4 \
    --output-dir reports/benchmark/lfw2_robustness

# Severity-tier tables + PNGs from a merged run
python scripts/reporting/generate_robustness_report.py \
    --input-json reports/benchmark/accuracy_ratio_hybrid.json
```
