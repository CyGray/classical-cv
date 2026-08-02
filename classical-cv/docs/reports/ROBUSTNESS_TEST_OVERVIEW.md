# Robustness Test — Simple Overview

## What this test checks

Real photos aren't perfect — too dark, blurry, tilted, noisy, zoomed weird, or partly covered. This test checks whether the face recognition system still recognizes the right person even when the photo is damaged like that.

It compares three versions of the system side by side:

| Mode | What it is |
| --- | --- |
| **CV Only** | The classical engine alone (LBPH) |
| **DL Only** | The deep learning engine alone (SFace) |
| **Hybrid Cascade** | The combined system — LBPH tries first, SFace steps in when LBPH isn't confident |

## "Enrolled photo" and "test photo" are now two DIFFERENT photos

Earlier runs (`reports/benchmark/lfw2_robustness/`, `lfw2_robustness_rerun/`)
picked ONE photo per person and used it for BOTH steps: the system learned
that exact photo, then "tested" itself by damaging a copy of the SAME photo.
Every test photo started at zero distance from what the system already knew,
so the numbers mostly showed how well each damage type survives re-detection
on a near-identical image — not whether the system can recognize someone from
a genuinely different photo. See `docs/audits/STATE-08-01.md` for the full
writeup; those old numbers (86.66% / 98.22% / 94.69% / 98.26%) are not valid
recognition-accuracy figures.

The fixed protocol (`reports/benchmark/lfw2_robustness_disjoint/`) uses TWO
different photos per person whenever a second one exists: one **gallery**
photo the system enrolls, and one **probe** photo — genuinely different from
the gallery photo — that gets damaged and tested. People with only one photo
stay in the gallery as "known faces the system could mistakenly pick" but
never contribute a test photo. Which photo plays which role is picked once,
randomly, with a fixed seed, so it's reproducible but never "the easiest
pair" — see `scripts/utils/make_lfw_identification_split.py`.

## What "damage" gets tested

The default damage set is a **41-modification taxonomy shared with the deep-learning
team's benchmark** (brightness/JPEG/colour-reduction/noise/blur/rotation/scaling/
translation/flip/aspect-ratio/crop/skew/perspective — see §4 below for the full
list), so the two teams' tables are directly comparable. The original 12-family
set (rotation ±10°, zoom 0.90–1.10×, occlusion ≤17.5%, etc.) is still available
via `--mod-set legacy` for reproducing old reports bit-for-bit, but is no longer
the default.

Four of the 41 (`rot_90`, `rot_180`, `rot_270`, `flip_lr`) are reported
**separately** and are not blended into the headline average: a system failing
on an upside-down face is expected, and a horizontal mirror is close to free
for most face embeddings, so folding them into the main number would distort
it in both directions.

Each damage type has a **light / medium / heavy** version, so the report can show where a mode starts to break, not just whether it breaks.

## How "pass" is measured — two different questions, both reported

The report answers two separate questions per photo, because they can give
very different answers (see `docs/audits/STATE-08-01.md` §5a for a concrete
case where they diverge sharply):

1. **Rank-1 (threshold-free)**: out of everyone in the gallery, did the
   engine's single best guess land on the right person at all — regardless
   of how confident it was?
2. **AR / TPIR (threshold-gated)**: did it pick the right person **and**
   was it confident enough to clear that engine's accept threshold?

A mode can rank the right person first and still get scored as a miss on AR,
because it wasn't confident enough to accept them. That is a genuinely
different failure than not ranking them first at all — one says "the
threshold is miscalibrated for this engine/dataset", the other says "the
engine can't tell this photo is the same person". The percentage of damaged
photos passing rule 2 is the **Accuracy Ratio (AR)**; rule 1 is reported
alongside it as **Rank-1 identification**.

A **clean baseline row** reports both Rank-1 and AR/TPIR on the UNDEGRADED
probe photo (no damage applied) — this is what makes AR interpretable at
all: an AR of 70% means something different if the clean baseline is 100%
(damage caused the drop) versus 75% (damage barely mattered; the engine just
isn't great at this dataset), and a low AR with a HIGH clean Rank-1 points at
the threshold rather than the engine's ranking ability. Each modification
also reports **retention** = `AR_mod / AR_clean` (threshold-gated), the
fraction of the clean baseline that survives that damage.

## The complete flow, step by step

1. **Pick the gallery and probe photos** — one gallery (enrolled) photo per person, and — for anyone with a second photo — one probe photo, genuinely different from their gallery photo. Chosen once, randomly, with a fixed seed, and pinned into a manifest so every run reuses the exact same split (`scripts/utils/make_lfw_identification_split.py`).
2. **Register everyone** — each engine "learns" the gallery photos (LBPH trains a model file, SFace stores a face-embedding gallery). This step is cached, so it only happens once per dataset/split combination.
3. **Damage every probe photo** — apply all 41 damage variants to each probe photo (never to the gallery photo).
4. **Run all three modes on every damaged photo** — detect the face, then score it with CV Only, DL Only, and the Hybrid Cascade, against the enrolled gallery.
5. **Tally the results** — for every (damage type, strength level), record each mode's Accuracy Ratio and retention, plus how often the Hybrid Cascade had to escalate from LBPH to SFace.
6. **Split the work up (for big datasets)** — a large dataset like LFW is split into segments and run in parallel across multiple worker processes, then all segment results get merged back into one unified report.
7. **Summarize into Light / Medium / Heavy tiers** — the results get grouped by damage severity into a simple table so it's easy to see, per mode, how accuracy holds up as damage gets worse. Rotation/flip results are kept in their own section, never averaged into the headline number (see above).

## Where the results live

- Raw numbers (fixed protocol): `reports/benchmark/lfw2_robustness_disjoint/accuracy_ratio_hybrid.{json,md}`
- Raw numbers (older, same-image runs — kept as run records, not valid recognition accuracy): `reports/benchmark/lfw2_robustness/`, `reports/benchmark/lfw2_robustness_rerun/`
- Genuine (same-identity) distance distributions — LBPH distance vs `tau_accept`/`tau_reject`, SFace L2 vs `l2_genuine` — for checking whether the frozen thresholds sit inside the range real cross-photo genuine pairs actually produce: `reports/benchmark/lfw2_robustness_disjoint/genuine_distance/` (`scripts/reporting/plot_genuine_distance_distribution.py`; see `docs/audits/STATE-08-01.md` §5a)
- Severity-tier tables: `reports/benchmark/robustness_tables.md`
- Picture versions of the tables: `reports/figures/robustness_table_*.png` and `hybrid_robustness_tables.png`

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

## 2. Gallery/probe split and enrollment (feature DB construction)

**This section describes the FIXED protocol** (`--split-manifest`, default for
new runs). The previous same-image path is documented at the end of this
section for backward compatibility only — see `docs/audits/STATE-08-01.md`
for why it is not a valid recognition-accuracy measurement.

- **The bug this replaces**: `accuracy_ratio_hybrid.py` and its LFW2 enrollment
  step both called `select_originals(lfw_root, select_one_per_person=True,
  seed=42)` — the SAME function, SAME seed. Enrollment and probing therefore
  picked the identical image for every identity: every "clean" probe had
  `lbph_distance == 0.0` before any damage was applied, and every damaged
  probe was a degraded copy of the exact photo the system had just memorized.
  That measures **transform sensitivity** (does re-detecting a near-identical
  image survive brightness/blur/rotation/etc.), not recognition (can the
  system identify someone from a genuinely different photo of them).
- **The fix — a gallery/probe-disjoint 1:N identification split**, in the
  spirit of the standard LFW verification/identification protocols (e.g.
  Best-Rowden et al. 2014): built once by
  `scripts/utils/make_lfw_identification_split.py` into
  `data/splits/lfw_ident_split_seed42.json` (schema
  `lsface-lfw-ident-split-v1`):
  - **Gallery**: one image per identity, for every identity including
    singletons (people with only one LFW photo). Singletons are enrolled but
    never probed — they exist purely as impostor pressure for the 1:N search
    and to keep gallery size comparable to the old (leaky) run.
  - **Probes**: for every identity with ≥2 images, one further image —
    disjoint from that identity's gallery pick (configurable up to
    `--max-probes-per-identity`, default 1 = 1,680 probes on full LFW1).
  - **Selection is uniform-random with a fixed seed, never quality/similarity
    ranked** — picking the "best" or most-similar pair would silently
    reintroduce the same leak. A single `random.Random(42)` walks identities
    in sorted order, `rng.sample`/`rng.choice` over each identity's
    `sorted()` files. The one allowed exception: both chosen images must pass
    YuNet detection, with deterministic same-RNG resampling on failure; an
    identity that still can't form a valid pair is demoted to gallery-only
    and counted, never silently dropped.
  - The manifest pins the dataset root, seed, every identity's gallery/probe
    path, realized counts, and a SHA256 over the sorted `(person, gallery,
    probe)` triples so a run can be verified against the exact split it used.
- **Enrollment (feature DB build)**: identical mechanics to before (YuNet
  detection, LBPH `normalize_face`/train, SFace embedding), but now reads
  each identity's manifest **gallery** image
  (`load_gallery_from_manifest` in `accuracy_ratio_hybrid.py`) instead of
  `select_originals`. Cached under `models/lfw2/` keyed by
  `(lfw_root, seed, split_manifest_sha256, limit_identities)` — the cache key
  including the manifest's own SHA256 means a stale
  `models/lfw2/manifest_seed{seed}*.json` can never be silently reused
  against a *different* split manifest that happens to share the same seed.
- **Probe generation**: each identity's manifest **probe** image (never the
  gallery image) is passed through all 41 `(modification, level)` transforms,
  each seeded via `stable_rng(seed, person, filename, mod_name, level)` —
  deterministic and shard-safe, so any segment slice reproduces bit-identical
  probes to a full run. The undamaged probe image is also scored directly, as
  the **clean held-out baseline** (§7).
- **Backward-compatible same-image path** (`--split-manifest` omitted):
  `select_originals(base_dir, select_one_per_person=True, seed=42)` picks one
  image per identity folder and reuses it for both enrollment and probing, as
  before. Its report label is `transform_sensitivity` everywhere in the
  output (JSON `protocol`/`protocol_label` fields, markdown headings) — it
  can no longer be printed or read as "Accuracy Ratio". Default
  `--originals-dir` is the held-out `data/split_lasalle/test`; the LFW
  harness (`scripts/pipeline/run_lfw2_robustness.py`) points this at
  `data/lfw-dataset` when no `--split-manifest` is given.

## 3. The three modes and their accept rules

| Mode | Engine(s) | Accept rule |
| --- | --- | --- |
| `cv_only` | LBPH alone | correct identity **and** `lbph_distance <= tau_accept` |
| `dl_only` | SFace alone | correct identity **and** `cosine >= cosine_genuine` **and** `l2 <= l2_genuine` |
| `cascade` | LBPH fast path + SFace escalation | see gate logic, §5 |

`cv_only`'s threshold is `tau_accept` (67.03325520645528 as of 2026-08-02, was 67.0084), not `tau_reject`.
`tau_accept` *is* LBPH's own standalone independence-test threshold — LFW1
rank-165 unidirectional unique pair, ~10 ppm FAR (see the `provenance` block
in `src/hybrid/thresholds.json`), and `src/hybrid/independence_test.py`:488
scores LBPH-alone false accepts as `d <= tau_accept` on the same basis. It
lives under the `gate.*` key for storage reasons; that does not make it a
cascade-only parameter. `tau_reject` is the cascade gate's confident-*reject*
bound and has no role in standalone `cv_only`.

Each standalone leg uses its own engine's frozen independence threshold, so
the two are compared at the same ~10 ppm FAR operating point: LBPH at
`tau_accept`, SFace at `cosine_genuine`/`l2_genuine`. `recognizer.py`'s
`cv_only` branch used `tau_reject` until 2026-08-01, which silently ran
`cv_only` at ~1% FAR against `dl_only`'s ~10 ppm — a ~1000x mismatch in
LBPH's favour. Fixed; see `docs/audits/STATE-08-01.md` §5a.

**Frozen thresholds** (`src/hybrid/thresholds.json`; `tau_accept` current as of 2026-08-02, other rows not re-verified this pass — see the repo's `cv-repo-map` skill before quoting these anywhere else, since this repo has two non-comparable LBPH distance scales and it's easy to grab the wrong one):

| Threshold | Value | Meaning |
| --- | ---: | --- |
| `gate.tau_accept` | **67.03325520645528** | LBPH distance ≤ this ⇒ accept (native `predict_collect()` scale) — both the cascade's confident-accept bound **and** standalone `cv_only`'s accept rule (unified 2026-08-02, see `docs/independence/MASTER_FILE.md`) |
| `gate.tau_reject` | 76.85 | LBPH distance ≥ this ⇒ confident reject — **cascade gate only**, not used by standalone `cv_only` |
| `gate.margin_min` | 0.05 | minimum relative top1/top2 margin (below this ⇒ escalate) |
| `sface.cosine_genuine` | 0.363 | SFace cosine ≥ this required to accept |
| `sface.l2_genuine` | **1.018** | SFace L2 ≤ this required to accept |

LBPH's raw score is a **distance** (lower = better match), so `tau_accept < tau_reject` by construction.

## 4. The 41 modifications

Two selectable sets, `--mod-set {dl41,legacy}` on `accuracy_ratio_hybrid.py`
(`src/benchmark/modifications.py`):

### 4a. `dl41` (default for new runs)

41 individually-named modifications mirrored verbatim (names + tiers) from
the DL team's `MODIFICATION_MAPS` in `..\deep-learning\ar-table.py`, so the
CV and DL AR tables are directly comparable — only the names/tiers are
pinned to the DL spec; the actual pixel transform for each name is this
repo's own implementation (`DL41_MODIFICATIONS`/`DL41_CATEGORY_TIER` in
`src/benchmark/modifications.py`), since `ar-table.py` only records
category+tier, not pixel-level operations.

| Category | Suffixes (light → heavy) |
| --- | --- |
| Brightness change | `brightness_p10`, `brightness_p20`, `brightness_p25` |
| Colour to monochrome | `monochrome` |
| JPEG compression | `jpeg_q80`, `jpeg_q60`, `jpeg_q30` |
| Colour reduction | `rgb565`, `color_8bit` |
| Gaussian noise | `gaussnoise_4`, `gaussnoise_8`, `gaussnoise_12` |
| Histogram equalization | `histeq` |
| Auto-levels | `autolevel` |
| Blur | `blur_3`, `blur_5`, `blur_7` |
| Rotation (canonical) | `rot_90`, `rot_180`, `rot_270` |
| Simple rotation | `rot_10`, `rot_25`, `rot_45` |
| Scaling | `scale_90`, `scale_70`, `scale_50` |
| Translation | `trans_10`, `trans_20`, `trans_30` |
| Flip | `flip_lr` |
| Aspect ratio change | `aspect_16_9`, `aspect_6_3` |
| Crop | `crop_90`, `crop_70`, `crop_60` |
| Skew | `skew_4`, `skew_6`, `skew_10` |
| Perspective | `persp_4`, `persp_6`, `persp_10` |
| **Total** | **41** |

`rot_90`, `rot_180`, `rot_270`, `flip_lr` are the **detector-canonical**
group — reported in their own section, excluded from the headline overall-AR
mean (see the simple section above).

Tiers come directly from `DL41_CATEGORY_TIER` (the DL team's explicit
mapping), not from a severity heuristic.

**`flip_twice`** — a partial/incomplete prior generation under
`data/lfw/{light,medium,heavy}` (214 files, medium tier only) contains a
`flip_twice` variant that is **not** part of `MODIFICATION_MAPS` at all. Its
name and a pixel-correlation check against the raw original are consistent
with it being `flip_lr` applied twice — a mathematical identity no-op
(`cv2.flip(img, 1)` twice returns the exact original pixels) — which is
presumably why the DL team's own map never included it. It is dropped, not
reintroduced as a control; see `docs/audits/STATE-08-01.md`.

### 4b. `legacy` (bit-identical to old reports)

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

**Severity-tier bucketing** (Light/Medium/Heavy, `generate_robustness_report.py::tier_ar`) applies ONLY to the `legacy` set: a per-family severity function maps each level to a magnitude —

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

- **Accuracy Ratio (AR, threshold-gated)**: $\mathrm{AR} = 100 \times K / M$, where $K$ = probes with correct identity **and** within the mode's accept threshold, $M$ = total probes for that (modification, level). JSON field `ar_percent` / `matched`.
- **Rank-1 identification (threshold-free)**: same $M$, but $K$ = probes where the deciding engine's nearest gallery pick (`HybridDecision.name_raw` - LBPH's argmin or SFace's argmax, before any accept/reject rule) is the correct identity, regardless of confidence. JSON field `rank1_percent` / `rank1_matched`. See `docs/audits/STATE-08-01.md` §5a for why this and AR can diverge sharply (a threshold sitting below the achievable confidence range collapses AR toward 0 even when Rank-1 is high).
- **Per-modification AR / Rank-1**: mean across its levels, plus a pooled-binomial view (`matched` / `rank1_matched` summed over all level probes for that modification) reported with a **Wilson 95% CI**:
$$\hat p \pm \; \text{via } \;\text{center} = \frac{p + z^2/2n}{1+z^2/n}, \quad \text{half-width} = \frac{z}{1+z^2/n}\sqrt{\frac{p(1-p)}{n} + \frac{z^2}{4n^2}}, \quad z = 1.95996\ (95\%)$$
- **`dl_minus_cv_points`**: `dl_only AR − cv_only AR`, tagged `cv_stronger` / `dl_stronger` / `tie` (tie if `|Δ| ≤ 2.0` percentage points, `AR_TIE_TOLERANCE`). AR-based, not Rank-1-based.
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
