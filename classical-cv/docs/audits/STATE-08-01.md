# State Update — 2026-08-01: LFW2 41-modification benchmark moved to a gallery/probe-disjoint identification protocol

**Status: 🔵 ACTION TAKEN (methodology fix) + 🟠 NEW OPEN FINDING underneath
it.** The fix closes 🟠 Open Finding #2 in `AGENTS.md` ("the `dl_only` AR
column is saturated by benchmark design") — but fixing it exposed something
the leak had been hiding: LBPH's argmin lands on the correct identity only
~7.5% of the time on raw cross-photo LFW (§5a, a matcher-ranking problem, not
a threshold one), and separately the frozen `tau_accept = 67.0084` sits below
every observed genuine LBPH distance, so neither standalone `cv_only` nor the
cascade's fast path can accept a real cross-photo genuine pair. Neither is
fixed here — frozen thresholds were left untouched per instruction — and both
are now open items. §5a also records a **code fix** made here: `cv_only` was
accepting on `tau_reject`, not the frozen `tau_accept`.
Read this before citing, re-running, or extending
`src/benchmark/accuracy_ratio_hybrid.py`,
`scripts/pipeline/run_lfw2_robustness.py`,
`scripts/utils/make_lfw_identification_split.py`,
`scripts/reporting/plot_genuine_distance_distribution.py`, or any report
under `reports/benchmark/lfw2_robustness*/`.

**Companions:** `docs/audits/STATE-07-21.md` §2 (the original finding this
fixes — probes were distorted copies of the enrolled image, no impostors
scored), `docs/reports/ROBUSTNESS_TEST_OVERVIEW.md` §2/§4 (updated protocol
description), `AGENTS.md` 🟠 Open Findings (item 2 — the leak itself is fixed
here; item 1/3 are unrelated and still open) and its "Frozen thresholds"
section (§5a is a new finding about those thresholds, not a change to them).

---

## 0. TL;DR

**The prior LFW2 AR numbers (cv_only 86.66% / dl_only 98.22% / cascade 94.69%
/ parallel 98.26%, `reports/benchmark/lfw2_robustness/accuracy_ratio_hybrid.md`)
are INVALID as recognition-accuracy figures.** Do not cite them, average them
into anything, or put them in `docs/PAPER.md`. They measured whether a
degraded copy of an already-memorized photo still matches itself, not
whether the system can recognize a person from a different photo. Direct
evidence: that same report's `cv_only` **clean acceptance = 100.00%** on a
5,749-identity closed set — LBPH getting every single clean probe exactly
right is only possible because the "clean probe" and the enrolled gallery
image were pixel-identical.

**New finding, exposed by fixing the leak (§5a): `cv_only`'s failure is
mostly a ranking problem, not a threshold problem.** LBPH's argmin
identifies the correct person only **7.48%** of the time (Rank-1,
threshold-free, n=147) on raw cross-photo LFW — a hard ceiling no threshold
choice can lift. On top of that, the frozen `tau_accept = 67.0084` sits
below the *entire* observed genuine LBPH distance range (75.82–133.54,
min–max, n=147), so `cv_only`'s clean TPIR is **0.00%**: not one genuine
cross-photo pair produces a distance the standalone accept rule will take.
The same fact is why the cascade escalates 51–100% of probes (mean 95.6%)
instead of using its LBPH fast path. `dl_only` (SFace) is healthy under the
same protocol (clean TPIR 93.20%) — worth citing as the contrast case. No
threshold was changed; both the ranking gap and the threshold placement are
flagged as open items, and re-deriving thresholds alone would NOT rescue
`cv_only` past the 7.48% Rank-1 ceiling.**

The fix is a disjoint gallery/probe 1:N identification split
(`scripts/utils/make_lfw_identification_split.py` →
`data/splits/lfw_ident_split_seed42.json`), wired through
`accuracy_ratio_hybrid.py --split-manifest` and
`run_lfw2_robustness.py --split-manifest`, writing to the new
`reports/benchmark/lfw2_robustness_disjoint/` (old report directories
`lfw2_robustness/`, `lfw2_robustness_rerun/` are left untouched as run
records). The modification taxonomy also moved to a 41-name set shared with
the DL team's benchmark (`--mod-set dl41`, now the default), with the
original 12-family set kept as `--mod-set legacy` for bit-identical old-report
reproduction.

---

## 1. Why the old numbers are invalid

### 1.1 The bug

`accuracy_ratio_hybrid.py`'s `select_originals(base_dir,
select_one_per_person=True, seed=42)` was called TWICE with the SAME
arguments: once by `run_lfw2_robustness.py::ensure_lfw2_enrollment` to pick
the one image per identity that gets enrolled, and once by
`accuracy_ratio_hybrid.py::main` to pick the "clean" originals that get
damaged into probes. Same function, same seed, same dataset root → the exact
same image both times, for every identity.

Concretely: identity `X`'s enrolled LBPH template and SFace gallery embedding
came from `X_0001.jpg`. Every probe scored for `X` — "clean" and all 41
damaged variants — was ALSO derived from `X_0001.jpg` (grayscale copy,
optionally with brightness/blur/rotation/etc. applied on top). Intra-class
distance before any damage was applied was exactly 0 for every identity, on
every run, unconditionally.

### 1.2 What that actually measured

Not recognition. **Transform sensitivity of re-detecting/re-scoring a
near-duplicate of an image the system just memorized.** Concrete tell-tales,
all present in `reports/benchmark/lfw2_robustness/accuracy_ratio_hybrid.md`:

- **`cv_only` clean acceptance = 100.00%** on a 5,749-identity closed set.
  LBPH is not a strong recognizer on unaligned LFW crops across genuinely
  different photos (this session's own disjoint smoke run, §3 below, got
  0.00% clean acceptance for `cv_only` on a 13-probe sample) — the only way
  to get a clean 100.00% is for every "probe" to literally be the enrolled
  image.
- **`dl_only` pinned at a flat ~99.4–99.7%** across nearly every modification
  regardless of severity (per-modification table in the same report). YuNet
  re-detects the damaged tile and `alignCrop` undoes most geometric
  distortion before SFace embeds it; combined with the genuine rule having
  large headroom for a same-image pair, almost nothing failed except
  `gaussian_noise` (83.19% in the STATE-07-21 audit's citation of the same
  run family).
- **No impostors were scored at all.** The benchmark only ever asked "does
  probe X still match gallery X", never "does probe X get incorrectly
  matched to gallery Y". A same-image identification benchmark cannot
  produce a false-accept number by construction.

This was already flagged as 🟠 Open Finding #2 in `AGENTS.md` on 2026-07-21
(`docs/audits/STATE-07-21.md` §2); this update is the fix, not a new
discovery.

## 2. The fix: gallery/probe-disjoint 1:N identification

### 2.1 Dataset restore (prerequisite)

`data/lfw-dataset` had degraded to a 3.8 MB stub (1,756 folders, 289 images —
not enough to build any split at all). Moved aside to
`data/_broken_lfw-dataset_stub/` (not deleted). Restored from the **original,
unfunneled** LFW — the UMass host (`vis-www.cs.umass.edu`) is unreachable
from this machine; used the verified figshare mirror instead:

- Source: `https://ndownloader.figshare.com/files/5976018`
- Archive size: 180,566,744 bytes (matches exactly)
- Archive SHA256: `055f7d9c632d7370e6fb4afc7468d40f970c34a80d4c6f50ffec63f5a8d536c0`
- Extracted layout: `data/lfw-dataset/<Person_Name>/<Person_Name>_NNNN.jpg`

Realized counts, verified against the standard LFW figures: **5,749
identities, 13,233 images, 250×250×3 RGB, 1,680 identities with ≥2 images** —
all match exactly, no substitution of a funneled/deep-funneled/aligned
variant occurred.

### 2.2 Split manifest (`scripts/utils/make_lfw_identification_split.py`)

Output: `data/splits/lfw_ident_split_seed42.json`, schema
`lsface-lfw-ident-split-v1`.

- **Gallery**: one image per identity, for all 5,749 identities including
  singletons (4,069 of them — people with only one LFW photo). Singletons
  are enrolled but never probed; they supply impostor pressure to the 1:N
  search and keep gallery size comparable to the old run's ~5,749-identity
  enrollment.
- **Probes**: for each of the 1,680 identities with ≥2 images, one further
  image, disjoint from that identity's gallery pick (configurable up to
  `--max-probes-per-identity`, default 1 = the headline 1,680-probe
  configuration; LFW's per-identity image count is heavily skewed — e.g.
  George_W_Bush alone has 530 — so pulling every non-gallery image as a probe
  is opt-in, not default).
- **Selection**: uniform-random with `random.Random(42)`, walking identities
  in sorted order, `rng.sample`/`rng.choice` over each identity's `sorted()`
  files — deliberately NOT ranked by similarity, embedding distance,
  detector score, or sharpness (that would silently reintroduce the same
  leak this fix closes). The one allowed exception is a YuNet-detection
  quality gate on the chosen images, with deterministic same-RNG resampling
  on failure; an identity that still can't form a valid disjoint pair is
  demoted to gallery-only and counted, never silently dropped.
- **Realized run** (full LFW1, seed 42, K=1): 5,749 identities, 5,749
  gallery entries, 1,680 probes, **0 demotions, 0 YuNet resamples** (every
  chosen image passed YuNet detection on the first draw — LFW's faces are
  well-detected at this crop size), 7,429 total YuNet checks. Triples
  SHA256: `ce922042297ef99571ac235ab43e274166a02fe8213e1f8b3028667f5b8fb98a`.
- Verified: gallery path ≠ probe path for every one of the 1,680 probes (0
  collisions checked directly against the manifest).

### 2.3 Wiring

- `run_lfw2_robustness.py --split-manifest <path>`: enrolls LBPH + SFace from
  the manifest's **gallery** images (`load_gallery_from_manifest`) instead of
  `select_originals`. The enrollment cache key
  (`models/lfw2/{lbph,sface,manifest}_seed{seed}_manifest{sha[:12]}.*`)
  includes the split manifest's own SHA256, so a stale
  `models/lfw2/manifest_seed{seed}.json` can never be silently reused against
  a different split manifest sharing the same seed.
- `accuracy_ratio_hybrid.py --split-manifest <path>`: probes are the
  manifest's **probe** images (`load_probes_from_manifest`), scored against
  the pre-enrolled gallery. The undamaged probe is also scored directly as
  the new **clean held-out baseline** row — genuinely different image from
  the gallery, not the same image — reported as BOTH threshold-free Rank-1
  identification and threshold-gated TPIR (§5a covers why both are needed).
- The old same-image path (`select_originals` reused for both roles) is
  still reachable when `--split-manifest` is omitted, for reproducing old
  reports. Its output is now labelled `transform_sensitivity` everywhere —
  JSON `protocol`/`protocol_label` fields, markdown headings — so it can
  never again be printed or read as "Accuracy Ratio".
- New reports write to `reports/benchmark/lfw2_robustness_disjoint/`.
  `reports/benchmark/lfw2_robustness/` and `lfw2_robustness_rerun/` are left
  untouched (repo convention: old report artifacts are run records).

## 3. New modification taxonomy (`--mod-set {legacy,dl41}`)

`src/benchmark/modifications.py`'s original set (rotation ±10° max, zoom
0.90–1.10×, occlusion ≤17.5%) is comparatively gentle. Replaced the default
with a 41-name taxonomy mirrored (names + light/medium/heavy tiers, verbatim)
from the DL team's `MODIFICATION_MAPS` in `..\deep-learning\ar-table.py`
lines 15-57, so the two teams' AR tables are directly comparable — see
`DL41_MODIFICATIONS`/`DL41_CATEGORY_TIER` in `modifications.py` and
`docs/reports/ROBUSTNESS_TEST_OVERVIEW.md` §4a for the full list. `ar-table.py`
only records category+tier per name, not pixel-level operations (its scored
images came from a separate DL-side pipeline not present in this repo), so
the actual transform math is this repo's own reasonable implementation of
each named operation — only the names/tiers are pinned to the DL spec.

`--mod-set legacy` reproduces the original 12-family/41-variant set
bit-identically (verified: same `VARIANT_COUNT`, same `MODIFICATIONS` list,
untouched). `dl41` is now the default for new LFW runs.

**Detector-canonical group**: `rot_90`, `rot_180`, `rot_270`, `flip_lr` are
always reported in their own section (`detector_canonical_ar_percent`,
`detector_canonical_modifications` in the JSON), because a system failing on
an upside-down face is expected behaviour and flip is near-free for a
roughly-symmetric face embedding — those four read differently from the
damage-style modifications and are worth being able to read separately.

Whether they are **also** counted in the headline mean is `--headline-scope`,
added later in this session:

- `all41` (**default**) — headline covers all 41 variants. Chosen so the
  number is directly comparable to the DL team's `ar-table.py`, which
  averages every modification in `MODIFICATION_MAPS` with no exclusions.
- `exclude-canonical` — the 37-variant headline (earlier behaviour in this
  session), kept for reproducing reports generated before the flag existed.

The flag is threaded through `run_lfw2_robustness.py` and
`merge_robustness_segments.py`; a merged report inherits the scope from its
segments via a `headline_scope` payload key, and segment JSONs written before
the flag existed default to `exclude-canonical` so old merges stay
reproducible.

**`flip_twice` investigated and dropped.** `data/lfw/medium/` (a prior
partial/incomplete generation, 214 files, no light/heavy counterpart)
contains a `flip_twice` variant that is not in `MODIFICATION_MAPS` at all —
no source file in either repo defines or references it. Its name and a
pixel-correlation check against the raw original (same-orientation
correlation consistently ≥ mirrored-orientation correlation on the one
identity checked with a matching raw file, though the crop-alignment
mismatch between the two pipelines makes this check noisy, not conclusive on
its own) are consistent with it being `flip_lr` applied twice — which is a
mathematical identity no-op (`cv2.flip(img, 1)` twice returns the exact
original pixels) by construction, regardless of what preceded it in the
pipeline. It is dropped, not reintroduced as a control, since it was never
part of the canonical 41-mod set to begin with.

## 4. Report format changes

- **Clean held-out baseline row, split into Rank-1 and TPIR (§5a explains
  why both are needed)**: `clean_rank1_percent` (threshold-free: did the
  deciding engine's nearest gallery pick land on the right identity at all —
  `HybridDecision.name_raw`) and `clean_acceptance_percent` (TPIR:
  correct identity AND clears the mode's accept rule), per mode, on the
  undegraded probe image. Both are reported per modification too
  (`rank1_percent` alongside `ar_percent` on every modification row), plus
  pooled Wilson CIs and their own markdown table/section.
- **Retention column**: `AR_mod / AR_clean`, defined against the
  **threshold-gated** number, per modification/mode (`retention` field per
  modification row) — separates "this engine is weak on this dataset in
  general" from "this modification did damage".
- **`--no-face-policy strict`** is the recommended flag for headline dl41
  runs (detection failure is a genuine system failure under the new mod
  set); no-face counts remain in the JSON either way. Threaded through
  `run_lfw2_robustness.py --no-face-policy` as of this change (previously
  only `accuracy_ratio_hybrid.py` had the flag). Default CLI behaviour is
  unchanged (`fallback`) for backward compatibility.

## 5. Thresholds — untouched, but a load-bearing gap found underneath them

`tau_accept=67.0084`, `tau_reject=76.85`, `cosine_genuine=0.363`,
`l2_genuine=1.018` (native `predict_collect()` scale, per
`docs/READ THIS/FROZEN_THRESHOLDS.md` and `STATE-07-28.md`) were **not
modified**, and none of the four sync locations were touched. The `1.128`
value in `..\deep-learning\ar-table.py`'s `MODEL_THRESHOLDS["sface"]` is
stale per the user and was ignored — not read, not copied anywhere in this
change. Everything in this section is a finding, not an action.

### 5a. LBPH fails at ranking first, thresholds second

**Code fix made here: `cv_only` now accepts on `tau_accept` (67.0084), the
frozen LBPH-only independence threshold.** `HybridRecognizer.predict()`'s
`cv_only` branch (`src/hybrid/recognizer.py`) read `accept =
lbph_match.distance <= self.gate_thresholds.tau_reject` until this revision.
That was the only site in the repo treating `tau_reject` as a standalone
accept rule: `src/hybrid/independence_test.py`:488 already scores LBPH-alone
false accepts as `d <= tau_accept`, and `thresholds.json`'s `provenance`
block derives `tau_accept` from an **LBPH-only** sweep (LFW1 rank-165
unidirectional unique pair, ~10 ppm FAR). `tau_accept` living under the
`gate.*` key is a storage detail, not evidence that it is cascade-only.

Why this mattered beyond naming: `tau_reject = 76.85` is a ~1% FAR point
carried from `tar_at_far.md`, while `dl_only`'s SFace rule
(`cosine >= 0.363 AND l2 <= 1.018`) is a ~10 ppm point. Running `cv_only` on
`tau_reject` therefore compared the two standalone engines **~1000x apart in
FAR, in LBPH's favour** — and LBPH still lost. Both legs now sit at their own
engine's frozen ~10 ppm independence threshold, which is the comparison the
separate per-engine independence tests were built to support.

Effect on the numbers: `cv_only` clean TPIR moves 1.36% → **0.00%** and its
overall AR 0.53% → **0.00%**. Rank-1 is threshold-free and unchanged (7.48%
clean), as are `dl_only` and `cascade`.

The same-image leak (§1) meant genuine (same-identity) LBPH distance was
always ≈0 in every prior run, so **no run before this one ever measured what
LBPH's genuine distance actually looks like across two different photos of
the same person.** This session built a dedicated measurement for it:
`scripts/reporting/plot_genuine_distance_distribution.py`, which — for every
probe — reads `LBPHAdapter.score(sample).all_distances[person]` (the
distance to that identity's OWN enrolled template, not the best-across-
gallery distance an argmin might report for a different identity) and the
equivalent SFace L2/cosine computed directly against
`gallery.embeddings[person]`. Reuses `src/independence_plots.py`'s
`save_distance_histogram` — no new plotting code.

**Run: 500 identities (`--limit-identities 500`, 147 of which had a probe),
`--mod-set dl41`, clean (undamaged) probes only:**

**Primary cause: LBPH's argmin rarely picks the right identity at all —
a matcher failure, not a threshold failure.** Rank-1 (threshold-free, §6)
for `cv_only` was **7.48%** on these clean probes: out of every gallery
identity, LBPH's nearest-distance pick landed on the correct person only
about 1 time in 13 on raw, unaligned cross-photo LFW. No threshold placement
can rescue this — 7.48% is a hard ceiling on `cv_only`'s achievable TPIR
regardless of where the accept threshold sits, since TPIR requires both the
correct argmin AND clearing the threshold.

**Secondary cause: `tau_accept` sits below the entire genuine
distribution, so even the already-rare correct-argmin cases are all
rejected.**

| LBPH genuine distance (n=147) | min | p01 | p05 | median | p95 | max |
|---|---:|---:|---:|---:|---:|---:|
| Raw distance | 75.82 | 76.82 | 87.13 | 99.39 | 115.00 | 133.54 |

- **Zero** genuine pairs (distance to the identity's OWN gallery template,
  regardless of whether that identity was also the argmin) fall at or below
  `tau_accept = 67.0084`: the observed genuine MINIMUM is 75.82, a full 8.8
  distance units above the threshold. This matches the merged run's
  `clean_acceptance_percent["cv_only"]` (**0.00%**, §6) exactly — a direct
  cross-check that the genuine-distance measurement and the benchmark's own
  TPIR agree. `cv_only`'s AR is therefore 0.00% by construction on this
  protocol, and its 7.48% Rank-1 is the only informative number it produces.
- For reference, the retired `tau_reject = 76.85` rule would have passed
  **1.36%** of genuine pairs (min 75.82, p01 76.82 — it sat almost exactly
  at the floor of the distribution). That is the origin of the 1.36% figure
  in earlier drafts of this document.
- The same sub-floor placement is why the **cascade** escalates on
  51.0%–100.0% of probes (see below): its "confident accept" fast path is
  gated on the same `tau_accept` and is, on this evidence, never reachable
  by a real cross-photo genuine pair.

| SFace genuine (n=147) | min | p01 | p05 | median | p95 | max |
|---|---:|---:|---:|---:|---:|---:|
| L2 distance | 0.455 | 0.534 | 0.570 | 0.809 | 1.043 | 1.379 |
| Cosine | 0.049 | 0.220 | 0.456 | 0.673 | 0.837 | 0.897 |

- The dual rule (`cosine >= 0.363 AND l2 <= 1.018`) passes **93.20%** of
  genuine pairs — matching `clean_acceptance_percent["dl_only"]` (93.20%)
  exactly. SFace's genuine distribution sits mostly inside its accept
  thresholds; `l2_genuine = 1.018` is close to the genuine p95 (1.043), a
  reasonable operating point, not an obviously-wrong one. Worth citing as
  the contrast case: SFace does not have LBPH's ranking problem on this
  protocol.

**Escalation is close to saturated.** Across the 41 dl41
modifications the cascade's escalation rate
ranges 51.0%–100.0% (mean 95.6%) — with `tau_accept` below the genuine
floor, LBPH is essentially never "confident" enough on a genuine pair to
skip escalation, so the cascade collapses to
approximately-`dl_only`-with-LBPH-latency-overhead. **The cascade's design
(fast LBPH path, selective SFace escalation) is not meaningfully under test
at the current thresholds** — nearly everything escalates regardless of
whether LBPH's fast path would have been safe.

**Recommendation, NOT acted on — and re-deriving thresholds alone will NOT
rescue `cv_only`.** `tau_accept`/`tau_reject` were derived from an
**impostor-only** target (LFW1 rank-165 unique pair, ~10 ppm FAR,
`STATE-07-28.md`) and never checked against a genuine cross-photo
distribution, because no prior run had one to check against. Re-deriving
them from a genuine-vs-impostor tradeoff (ROC/DET curve across both
distributions, e.g. an EER or a chosen FAR/FRR operating point), rather than
impostor-only rank targeting, would raise `tau_accept` enough to recover
some of the 7.48% Rank-1 ceiling for `cv_only`'s TPIR and to make the
cascade's fast path reachable again — but 7.48% is a hard cap regardless: no
threshold choice makes `cv_only`
competitive with `dl_only` (93.20% clean TPIR) on this protocol, because
most of the failure is LBPH not ranking the right person first, which no
threshold can fix. This is flagged as an **open item** for whoever next
revisits threshold derivation — this session did not re-derive or edit
either value, per the explicit instruction to leave them frozen.

## 6. Smoke-test validation (this session)

Two runs: an initial 40-identity/13-probe wiring check, then a larger
500-identity/147-probe run (requested during review, since a 13-probe sample
can't distinguish "genuinely near-zero" from "small-sample noise").

```
python scripts/pipeline/run_lfw2_robustness.py \
    --split-manifest data/splits/_bigsmoke_split.json \
    --mod-set dl41 --no-face-policy strict --num-workers 4 --num-segments 4 \
    --output-dir outputs/benchmark/_bigsmoke_disjoint \
    --modes cv_only,dl_only,cascade
```

**500 identities, 147 probes, `--reuse-engine-scores` on:**

Re-run after two changes made later in the session: `cv_only` moved to
`tau_accept` (§5a) and the headline mean moved to **all 41** modifications
(`--headline-scope all41`, §3). Only the `cv_only` TPIR row is affected by
the threshold fix; the headline-scope change shifts every "overall" row,
since the 4 detector-canonical variants are now inside the mean.

| Metric | cv_only | dl_only | cascade |
|---|---:|---:|---:|
| Clean Rank-1 (threshold-free) | 7.48% | 97.96% | 96.60% |
| Clean TPIR @ threshold | **0.00%** | 93.20% | 91.84% |
| Overall AR (all 41 mods, TPIR) | **0.00%** | 81.28% | 79.74% |
| Overall Rank-1 (all 41 mods) | 3.75% | 88.55% | 87.01% |
| Detector-canonical AR (4 mods, TPIR) | 0.00% | 23.47% | 22.96% |
| Detector-canonical Rank-1 (4 mods) | 0.85% | 24.66% | 24.15% |

For reference, the same run with the pre-fix `tau_reject` rule and the
37-variant headline gave `cv_only` 1.36% clean TPIR / 0.59% overall AR, and
`dl_only` 87.53% / `cascade` 85.88% overall AR. `dl_only` and `cascade` are
lower under `all41` purely because the 4 detector-canonical variants (~23%
AR) are now averaged in — no engine got worse.

- Confirmed gallery path ≠ probe path for every probe (0 collisions,
  verified directly against both the 13- and 147-probe manifests).
- **`cv_only` is genuinely weak here, not a wiring artifact** — the
  genuine-distance measurement in §5a explains exactly why (LBPH's argmin is
  correct only ~7–8% of the time on raw cross-photo LFW, and even when
  correct the resulting distance is always above `tau_accept`).
  This is the direct opposite of the old same-image benchmark's `cv_only`
  100.00% clean acceptance (§1.2) — confirming that number was an artifact
  of the leak, not real recognition performance.
- **`dl_only` looks healthy under the new protocol**: 97.96% clean Rank-1,
  93.20% clean TPIR, 81.28% overall AR across all 41 mods — worth keeping as the
  contrast case: SFace's genuine distribution (§5a) sits mostly inside its
  accept thresholds, unlike LBPH's.
- `cascade` tracks `dl_only` closely (91.84% vs 93.20% clean TPIR) because it
  escalates on almost every probe (§5a) — it is not currently exercising its
  fast-path/escalation design meaningfully.
- `--mod-set legacy` (no `--split-manifest`, `data/lfw-dataset` substituted
  for the unpopulated La Salle test split on this machine) reproduces the
  old same-image behaviour pattern (clean acceptance 93–100%, overall AR
  80–98%) and correctly labels its report `Transform Sensitivity`, not
  `Accuracy Ratio` — confirms the backward-compatible path still works.
- Three pre-existing bugs were hit and fixed while validating this (all
  predate this session's protocol change; none previously exercised because
  no prior run had gone through this exact code path at small/edge-case
  scale): a `ModuleNotFoundError` (missing `scripts/utils` on `sys.path` in
  `run_lfw2_robustness.py`), a `TypeError` (unguarded `:.3f` formatting of
  `None` gate-competence metrics in `accuracy_ratio_hybrid.py`'s
  `battery_markdown`), and a JSON round-trip key mismatch in
  `merge_robustness_segments.py` (tuple-valued dl41 levels, e.g.
  `color_8bit`'s `(3, 3, 2)`, serialize as lists and no longer `str()`-match
  their Python-tuple form across a JSON write/read).

## 7. Full run — not executed, left for the user

The full run (5,749 identities × 41 dl41 variants × 3 modes) takes hours (the
old same-taxonomy run took ~1h53m per `AGENTS.md`'s benchmark note; dl41 has
a different, not-yet-measured per-probe cost). Launch command:

```
python scripts/utils/make_lfw_identification_split.py   # already run, produced
                                                          # data/splits/lfw_ident_split_seed42.json

python scripts/pipeline/run_lfw2_robustness.py \
    --split-manifest data/splits/lfw_ident_split_seed42.json \
    --mod-set dl41 \
    --headline-scope all41 \
    --modes cv_only,dl_only,cascade \
    --output-dir reports/benchmark/lfw2_robustness_disjoint \
    --no-face-policy strict
```

(`--headline-scope all41` is the default and is shown only for explicitness.
`--no-face-policy` is threaded through `run_lfw2_robustness.py`'s
passthrough flags as of this change, alongside `--mod-set`,
`--headline-scope` and `--split-manifest`.)

Optionally, after the full run, regenerate the genuine-distance artifact
(§5a) at full scale against the full-run enrollment cache:

```
python scripts/reporting/plot_genuine_distance_distribution.py \
    --split-manifest data/splits/lfw_ident_split_seed42.json \
    --lbph-model models/lfw2/lbph_seed42_manifest<sha12>.yml \
    --lbph-labels models/lfw2/lbph_labels_seed42_manifest<sha12>.json \
    --sface-gallery models/lfw2/sface_gallery_seed42_manifest<sha12>.npy \
    --output-dir reports/benchmark/lfw2_robustness_disjoint/genuine_distance
```

(`<sha12>` = the first 12 hex chars of the split manifest's `triples_sha256`,
printed by `run_lfw2_robustness.py`'s enrollment step and visible in the
`models/lfw2/manifest_seed42_manifest*.json` filename it writes.)

## 8. Files changed / created

- **Dataset**: `data/lfw-dataset/` restored (5,749 identities); old stub
  moved to `data/_broken_lfw-dataset_stub/` (not deleted).
- **New**: `scripts/utils/make_lfw_identification_split.py`,
  `data/splits/lfw_ident_split_seed42.json`,
  `scripts/reporting/plot_genuine_distance_distribution.py` (§5a - reuses
  `src/independence_plots.py::save_distance_histogram`, no new plotting code).
- **`src/benchmark/modifications.py`**: added `DL41_MODIFICATIONS`,
  `DL41_CATEGORY_TIER`, `DL41_TIER_MAP`, `DL41_CATEGORY_MAP`,
  `DL41_DETECTOR_CANONICAL`, `get_modification_set`, `variant_tier_dl41`, and
  ~20 new transform functions. Legacy `MODIFICATIONS`/`TIER_MAP`/`tier_ar`
  path untouched.
- **`src/benchmark/accuracy_ratio_hybrid.py`**: `--mod-set`,
  `--split-manifest`, `--limit-identities` flags; `load_split_manifest`,
  `load_probes_from_manifest`, `load_gallery_from_manifest`, `to_bgr_gray`;
  `score_probe` now also records `rank1_matched` (threshold-free, via
  `HybridDecision.name_raw`) alongside the existing threshold-gated
  `matched`; Rank-1 tracked at every aggregation level (clean baseline,
  per-level, per-modification, overall, detector-canonical) parallel to AR;
  retention (threshold-gated) + detector-canonical-exclusion in the
  payload/markdown; protocol labelling (`transform_sensitivity` vs
  `identification_disjoint`); a None-safe `_fmt_opt` formatting fix in the
  gate-competence markdown/console output (pre-existing bug, unrelated to the
  protocol change, hit during smoke-test validation).
- **`scripts/pipeline/run_lfw2_robustness.py`**: `--split-manifest`,
  `--mod-set`, `--limit-identities`, `--no-face-policy` flags;
  `ensure_lfw2_enrollment` now manifest-aware with a manifest-SHA256-keyed
  cache; fixed a pre-existing `sys.path` bug (`setup_datasets` import) hit
  during smoke-test validation.
- **`scripts/utils/merge_robustness_segments.py`**: mod-set-aware merge
  (`get_modification_set` instead of a hardcoded legacy import), Rank-1
  aggregation parallel to AR (gracefully degrades to omitted if any merged
  segment predates Rank-1 tracking), retention + detector-canonical section
  in the merged output, protocol labelling; fixed a pre-existing JSON
  round-trip bug where tuple-valued levels (e.g. `color_8bit`'s `(3, 3, 2)`)
  serialize as lists and no longer string-match their Python-tuple `str()`
  form (`json.dumps` used for level keys instead of `str()` on both sides).
- **`docs/reports/ROBUSTNESS_TEST_OVERVIEW.md`**: §2 (gallery/probe split
  protocol) and §4 (dl41 taxonomy + legacy) rewritten in both the simple and
  comprehensive sections; artifact paths updated.
- **Not touched**: `src/hybrid/thresholds.json` and its four sync locations
  (§5); `reports/benchmark/lfw2_robustness/`,
  `reports/benchmark/lfw2_robustness_rerun/` (old run records);
  `scripts/reporting/generate_robustness_report.py` (`tier_ar` legacy-only
  severity heuristic, still correct for `--mod-set legacy` reports).
