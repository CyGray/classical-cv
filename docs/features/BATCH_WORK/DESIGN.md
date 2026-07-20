# Distributed LFW2 Batch Work — Design

Status: IMPLEMENTED 2026-07-19 — §7.1 wiring, `--modification`,
`--selection-manifest`, worker, pins, merge, matrix all built; verifications
§12.1–12.5 PASSED on La Salle. Remaining before a real campaign: generate the
LFW selection manifest, pin the campaign commit, fill real member names,
canary round for assignment sizing.
Owner: Kyle (classical-CV track)
Scope: split the LFW-scale hybrid independence test and the robustness (Accuracy
Ratio) test across 4–8 group members, each running a batch on their own machine.
Also the execution substrate for the 41-variant systematic suite
(`docs/SYSTEMATIC_INDEPENDENCE_TEST.md`): its work unit is (variant, segment),
so everything below — pack, canary, pins, worker, merge — carries over with a
variant axis added to `assignments.json` and the merge.

---

## 1. Purpose

The two remaining LFW-scale open items (deferred 2026-07-10, see
`docs/audits/STATE-07-10.md`) are too slow for one machine:

1. **Hybrid independence test on LFW2** — the joint LBPH + SFace + cascade
   N×(N-1) impostor sweep (`src/hybrid/independence_test.py`) over modified LFW
   probes. At N = 5,749 identities this is 5,749 × 5,748 = **33,045,252 ordered
   pairs** per iteration (`evidence_matrix.py` defaults to `--lfw-iterations 3`).
2. **Robustness / Accuracy Ratio at LFW scale** — the 41-modification suite
   (`src/benchmark/accuracy_ratio_hybrid.py`). Scope per Kyle: **hybrid needs
   independence + robustness; DL (SFace) needs robustness only.** One
   `accuracy_ratio_hybrid` run already scores `cv_only` / `dl_only` / `cascade`
   / `parallel` in a single pass over the same probes, so a single robustness
   run per batch covers both the hybrid and the dl_only requirement (use
   `--modes dl_only,cascade,parallel` if cv_only should be skipped to save time).

Each member gets: a shareable worker script, their own LFW1 copy (augmented into
LFW2 or replaced by a probe pack — see §5), and a batch assignment. Each member
returns: the **full `comparisons.csv`** for their batch plus a mergeable
`summary.json` and an audit manifest.

---

## 2. Ground truth — what already exists (verified 2026-07-17)

| Concern | State |
|---|---|
| Hybrid independence test | `src/hybrid/independence_test.py`. `run_sweep()` (line ~208) trains a temporary LBPH model on all N selected tiles, builds an N×N `lbph_dist` matrix via `predict_collect` per probe, vectorises SFace cosine/L2 from a stacked embedding matrix, and runs the cascade gate once per query probe over the full non-self ranking. Streams per-pair CSV (`query_identity, candidate_identity, query_image_path, candidate_image_path, lbph_distance, sface_cosine, sface_l2, lbph_fp, sface_fp, both_fp, cascade_fp`). Resumable per-iteration caching in `_raw_runs/run_N/`. |
| Segment CLI flags on the hybrid test | **WIRED (2026-07-19).** `--segment-count` / `--segment-index` now slice query rows in `run_sweep()` per §7.1; candidates stay global. Verified per §12.1–12.2 (results recorded in §12). Cosine kernel changed to per-row matvec for segment invariance — see §9 BLAS row. |
| Canonical slicing helper | `segment_bounds(n, segment_count, segment_index)` in `src/independence_report.py:219` — 1-based, query-rows-[0,n) slicing. |
| Proven precedent | Classical `*_light_front.py` tests run segmented LFW sweeps: `archive/outputs-5-17/.../_segments/lfw_seg{1..6}of6/` (eigenfaces, 6-way) and `lfw_seg{1,2}of2` (LBPH). `try_merge_segment_outputs()` (`src/lbph/independence_test_light_front.py:1008`) merges segment summaries: sums FP counts per threshold label, recomputes FPR over summed totals, merges lowest-pairs top-20, and deliberately leaves `comparisons.csv` per-segment. |
| Robustness test | `src/benchmark/accuracy_ratio_hybrid.py` — iterates originals × 41 deterministic (mod, level) probes from `src/benchmark/modifications.py`. Every probe's RNG comes from `stable_rng()` seeded per (image, mod, level) → **per-image deterministic, order-independent, therefore shard-safe by identity**. Uses the deployed LBPH model + SFace gallery (`DEFAULT_LBPH_MODEL`, `DEFAULT_SFACE_GALLERY`) and the frozen `src/hybrid/thresholds.json`. **UPDATE 2026-07-19: `--segment-count`/`--segment-index` now present** (slices originals via `segment_bounds`, emits segment fields in the JSON); merged by `scripts/merge_robustness_segments.py`. |
| LFW1 acquisition | `scripts/setup_datasets.py::setup_lfw()` — downloads/extracts LFW (verifies 5,749 identity dirs), plus `run_augmentation()` count-verification pattern. |
| LFW1 → LFW2 augmentation | `scripts/augment_split_light_medium.py` — seeded (`--seed 42`) but uses **one sequential `np.random.default_rng`** consumed in directory-sorted order. Deterministic only if the whole set is processed, in the same order, with the same NumPy version (NumPy does not guarantee bit-identical distribution streams across versions). This is the single biggest reproducibility risk for "everyone augments locally" (§5, §10). |
| Pre-modified LFW probes | `data/lfw/{light,medium,heavy}/` — 5,749 identities of pre-generated modified probes (`<Person>_0001__processed__<mod>.jpg`). **No generator script exists in the repo** — external artifact. `evidence_matrix.py`'s `lfw2_41mods` leg expects `data/lfw2_41mods` which currently does not exist (leg reports SKIPPED). Past manual hybrid runs exist at `reports/independence/hybrid/lfw2_light/` and `lfw2_medium/`. Which "LFW2" definition the paper run uses is an open decision (§13). |
| Frozen inputs | `src/hybrid/thresholds.json` (SHA-256 already recorded by `evidence_matrix.py`), deployed LBPH model/labels, SFace gallery/impostors. All must be byte-identical on every member machine. |

---

## 3. Requirements and derived constraints

**From Kyle:**
- 4–8 members, each with their own LFW1 copy, each handling one assigned batch.
- A single shareable bridge/worker script; minimal member-side expertise assumed.
- Each member returns the full `comparisons.csv` for their batch.
- Tests in scope: hybrid independence + hybrid robustness + dl_only robustness.
- Audit-grade: no silently divergent inputs, everything verifiable at merge time.

**Derived constraints (from the code):**

1. **Every member needs the FULL probe set, not just their slice.** `run_sweep()`
   trains LBPH on all N tiles, and the cascade gate ranks each query probe
   against all N-1 candidates. Sharding therefore slices *query rows* only;
   candidates stay global. (This is exactly the classical light-front
   "complete" segment mode, not "intra".)
2. **Image selection must be identical across members.**
   `select_one_image_per_person()` seeds `random.Random(seed + iteration)` and
   picks per person in sorted order — deterministic *given identical file
   listings and identical file content*. So either everyone's LFW2 is
   bit-identical, or the selection is done once centrally (§5 Approach B).
3. **Cascade FP semantics partition cleanly.** At most one cascade FP per query
   probe → per-segment cascade FP counts sum to the global count with no
   double-counting.
4. **The complementarity statistics merge from counts.** Yule Q, Fisher exact,
   FAR, and Wilson intervals all derive from the 2×2 contingency table
   (both_fp / lbph_only / sface_only / neither) plus totals — all summable per
   segment. `comparisons.csv` is needed for audit and post-hoc analysis, not
   for the headline statistics.
5. **Robustness shards trivially.** `stable_rng()` per (image, mod, level)
   means any identity subset produces bit-identical probes to the full run.

---

## 4. Batch-division strategies considered

### 4.1 Query-row segments (RECOMMENDED)
Slice the independence sweep's query rows with the existing
`segment_bounds()`; robustness slices the sorted identity list the same way.

- Even load: each ordered pair computed exactly once across the team.
- Merge is count-summation (proven pattern, `try_merge_segment_outputs()`).
- Same worker command for everyone; only `--segment-index` differs.
- Matches the historical 6-way eigenfaces run — precedent Kyle can cite.

### 4.2 By robustness-modification variant (rejected for independence, viable for AR only)
One member per subset of the 41 mods. Balances poorly (mods have very different
costs), does nothing for the independence sweep (the dominant cost), and
complicates the merge (per-mod rows come from different machines → any hardware
float drift lands *inside* a mod's number instead of across identities where a
canary catches it).

### 4.3 By evidence-matrix leg (rejected)
One member runs lfw1, another lfw2_light, etc. Only ~2–4 units of work — cannot
occupy 4–8 members, and each leg is still a full 33M-pair sweep, so the slowest
machine bottlenecks everything. Could be *combined* with 4.1 later (tier ×
segment grid) if both light and medium tiers are required.

**Decision: 4.1, with micro-batching for hardware imbalance (§9).**

---

## 5. Distribution approaches (how members get their inputs)

### Approach A — Self-generate: member downloads LFW1 and augments locally
The worker script runs `setup_lfw()` → `augment_split_light_medium.py` (full
set, seed 42) → verifies image count → runs the tests.

- Pros: no large uploads from Kyle; members only need the repo + internet.
- Cons: **augmentation determinism is fragile** — a different NumPy version, a
  partially-failed prior run, or a stray extra file changes the RNG consumption
  order and silently produces different LFW2 pixels → different distances →
  unusable batch. Mitigations: pinned `requirements-batch.txt`, mandatory
  post-augment content hashing (§10.2), `--clean-output` enforced. Cost:
  ~173 MB LFW download + full-set augmentation time + disk for 23,940 images.

### Approach B — Probe pack: Kyle generates LFW2 once, ships exactly the needed files (RECOMMENDED)
The independence sweep only ever touches **one selected image per identity per
iteration**. Kyle runs selection locally (same seeded logic), exports the
selected files as `lfw2_probe_pack_<tier>.zip` (≤ iterations × 5,749 images
plus a `selection_manifest.json` mapping identity → relative path → SHA-256),
and shares it via Drive. The worker consumes the pack directly via
`--probe-pack`, skipping download and augmentation entirely.

- Pros: **bit-identical inputs by construction** — eliminates the entire
  augmentation-determinism risk class; smallest member setup (one zip + repo);
  works offline once downloaded; the pack's manifest doubles as the audit
  record of exactly which pixels were tested.
- Cons: Kyle uploads once (estimated tens–low-hundreds of MB for 5,749 LFW
  jpgs per iteration — measure, don't assume); a new pack is needed if the
  tier/seed/iteration count changes.
- Robustness note: `accuracy_ratio_hybrid.py` generates its own 41 mods
  in-memory from originals, so its pack is just the originals subset (or the
  same probe pack, decision §13.3).

### Approach C — Orchestrated gateway (a real "bridge" service)
A coordination layer instead of manual zips: a shared Drive folder as a job
queue (workers claim `batch_03.CLAIMED`, upload `batch_03.done.zip`), or the
existing FastAPI console (`ui/console/`) extended with `/batches/claim` +
`/batches/submit` endpoints, or GitHub Actions runners.

- Pros: automatic assignment, progress visibility, no lost zips, reassignment
  of abandoned batches is automatic.
- Cons: real engineering + hosting for what is likely a one-shot campaign;
  members must authenticate; failure modes move from "zip missing" to "service
  down". **Not recommended for the first campaign.** If batch campaigns become
  recurring, revisit — the manifest/zip format below is designed so a gateway
  can be layered on later without changing the worker.

**Decision (revised 2026-07-19 per Kyle's campaign flow):** members download
LFW1 themselves (`setup_datasets.py::setup_lfw()`); modifications are applied
**in memory** by `--modification` (systematic doc §3.1), so no augmented
dataset or probe-pack zip is ever distributed. Approach B survives as its
cleanest part: a **committed selection manifest**
(`scripts/make_selection_manifest.py` output, SHA-256 per probe file) that the
independence test verifies via `--selection-manifest` before sweeping —
bit-identical inputs by construction without any upload. Approach C deferred.

---

## 6. Component design

```
                    Kyle (coordinator)                     Member i (of N)
  ┌──────────────────────────────────┐        ┌─────────────────────────────────┐
  │ scripts/make_probe_pack.py       │  zip   │ scripts/lfw2_worker.py          │
  │  - seeded selection over LFW2    │──────▶ │  1 preflight (env+SHA checks)   │
  │  - selection_manifest.json+SHAs  │        │  2 fetch inputs (pack or A-path)│
  │ assignments.json (batch table)   │        │  3 canary micro-sweep           │
  └──────────────────────────────────┘        │  4 independence seg i of N      │
                 ▲                            │  5 robustness  seg i of N       │
                 │  lfw2_seg{i}of{N}.zip      │  6 package results + manifest   │
  ┌──────────────┴───────────────────┐        └─────────────────────────────────┘
  │ scripts/merge_lfw2_segments.py   │
  │  - manifest cross-verification   │
  │  - count-sum merge + global stats│
  │  - canary comparison             │
  │  - feeds evidence_matrix row     │
  └──────────────────────────────────┘
```

### 6.1 `scripts/lfw2_worker.py` — the shareable bridge script

One command per member:

```
python scripts/lfw2_worker.py --segment-index 3 --segment-count 8 \
    --probe-pack path/to/lfw2_probe_pack_light.zip
# Approach-A fallback (no pack):
python scripts/lfw2_worker.py --segment-index 3 --segment-count 8 --self-augment
```

Phases, each idempotent with a `[SKIP] already done` fast path and a stamp file
so a crashed run resumes where it stopped:

1. **Preflight** — hard-fail on any mismatch (audit rule: no divergent inputs):
   - Python ≥ 3.10; import-check pinned deps; record `numpy.__version__`,
     `cv2.__version__`, platform, CPU, RAM in the manifest.
   - SHA-256 verify against `batch_pins.json` (committed, written by Kyle):
     `src/hybrid/thresholds.json`, deployed LBPH model + labels, SFace gallery
     (+ impostors if present), SFace/YuNet ONNX files.
   - `git rev-parse HEAD` must equal the pinned commit (warn-and-abort if the
     working tree is dirty).
2. **Inputs** — unpack probe pack and verify every file's SHA against
   `selection_manifest.json`; or (Approach A) `setup_lfw()` → full augmentation
   with `--clean-output` → count check → hash-verify the ~20-file sample listed
   in `batch_pins.json` (cheap detector for RNG divergence, §10.2).
3. **Canary** — run a fixed tiny sweep (e.g. the first 64 identities,
   `--segment-count 1`) and write `canary_summary.json` + `canary.csv`. Every
   member runs the *same* canary; the merge compares them across machines to
   detect hardware float drift before trusting the real batches.
4. **Independence** — invoke `python -m src.hybrid.independence_test
   --dataset-dir <resolved> --segment-count N --segment-index i --iterations K
   --output-dir reports/independence/hybrid/lfw2_<tier>_seg{i}of{N}`.
5. **Robustness** — invoke `python -m src.benchmark.accuracy_ratio_hybrid
   --originals-dir <resolved> --segment-count N --segment-index i
   --modes dl_only,cascade,parallel` (mode list per decision §13.2) with
   per-segment output paths.
6. **Package** — `lfw2_seg{i}of{N}_results.zip`:
   - `independence/comparisons.csv.gz` (gzipped — see size note §11)
   - `independence/summary.json`, `_raw_runs/` summaries (not the npz unless
     requested)
   - `robustness/accuracy_ratio_hybrid_seg.json` + per-probe battery CSV
   - `canary_summary.json`, `canary.csv`
   - `manifest.json`: pinned-SHA echo, git commit, dataset root used, segment
     bounds actually swept (`seg_start`,`seg_end`,`n_total`), seeds, iteration
     count, lib versions, hostname, wall-clock per phase, row/FP totals.

### 6.2 `scripts/make_probe_pack.py` (Kyle-side, Approach B)
Runs `get_person_dirs()` + `select_one_image_per_person(seed + it)` for each
iteration over the chosen LFW2 tier directory, copies selected files into a
pack layout `pack/<iteration>/<identity>/<file>`, writes
`selection_manifest.json` (identity → relpath → SHA-256, plus tier, seed,
iteration count, source-dir fingerprint), zips it. The worker feeds
`--dataset-dir` shims per iteration or (simpler) the independence test learns a
`--selection-manifest` flag that bypasses `select_one_image_per_person` and
loads exactly the manifest paths (§7.1, change 3 — this is the cleaner seam and
also removes the "identical file listing" requirement entirely).

### 6.3 `scripts/merge_lfw2_segments.py` (Kyle-side)
Input: a folder of the N result zips (+ `assignments.json`).

1. **Verify** — all manifests agree on commit, SHAs, seed, tier, iteration
   count, `n_total`; segment set is disjoint and covers [0, n_total) exactly;
   canaries agree across members (exact match expected; any mismatch →
   tolerance report per column and a hard decision from Kyle, §10.3).
2. **Merge independence** — per iteration: sum FP counts (lbph, sface, both,
   cascade) and comparison totals; recompute FAR/ppm, Wilson intervals, Yule Q,
   Fisher exact from the summed 2×2 tables (helpers already in
   `src/stats_utils.py`); merge lowest-pairs top-K; then aggregate across
   iterations the same way the unsegmented test does. Output
   `reports/independence/hybrid/lfw2_<tier>_merged/summary.json` shaped
   identically to a single-machine run so `evidence_matrix.py` and the paper
   pipeline consume it unchanged.
3. **Merge robustness** — sum per-(mode, modification) correct/total/no-face
   counts, recompute AR percentages and cv_stronger/dl_stronger/tie tags,
   concatenate the per-probe battery CSVs; rerun
   `scripts/generate_robustness_report.py` on the merged JSON.
4. **comparisons.csv** — keep per-segment `comparisons.csv.gz` side by side
   (the merged summary records their SHAs); optionally emit one concatenated
   file. **Path normalization:** the CSV stores each machine's absolute image
   paths — the merge rewrites them to paths relative to the dataset root
   recorded in that member's manifest, so rows are machine-independent and
   dedupe/audit by (identity, relpath) works.

---

## 7. Code changes required

### 7.1 `src/hybrid/independence_test.py` — wire in the (already-accepted) segment flags

**STATUS: IMPLEMENTED 2026-07-19** (all changes 1–5 below; change 3
`--selection-manifest` landed in the second pass with 0-based iteration keys
matching the seed offset `random_seed + it` and
`make_selection_manifest.py`; verified byte-identical to a plain run and
abort-on-tamper, §12.3). Also added in the second pass:
`--modification <name>:<level>` (systematic doc §3.1) — in-memory
`stable_rng(seed, person, basename, mod, level)` corruption of all N tiles,
token-scheme and gray-first order copied exactly from
`accuracy_ratio_hybrid.py`, verified deterministic across runs and
byte-identical under 2-way segmentation (FP sums exact: lbph 2, sface 8,
cascade 8, both 0 on La Salle motion_blur:5). Two deviations from the plan,
both deliberate:

* **Segment block only when segmented.** `summary.json` gains the `segment`
  block (and the fingerprint gains segment keys) only when
  `--segment-count > 1`, so unsegmented runs stay byte-compatible with
  existing caches and baselines (verification 12.1).
* **SFace cosine is now one matvec per query row, not one matmul.** The
  planned `cos = norm[seg] @ norm.T` slice failed verification 12.2: BLAS
  picks different blocked kernels for different operand shapes, so sliced
  results disagreed with the full run at the last float32 ulp
  (155/756 rows on La Salle, ≤ 3.8e-6 relative, sface_cosine column only,
  zero FP-flag flips). Per-row matvec makes cosines bit-identical no matter
  how rows are segmented — the invariant the merge audits. One-time cost:
  vs. the pre-change kernel, cosine values shift by ≤ 3.8e-6 relative
  (no decision flips on La Salle); new runs are self-consistent.
1. In the sweep setup: `seg_start, seg_end = segment_bounds(n, args.segment_count,
   args.segment_index)` (import exists already via `src.independence_report`).
2. `run_sweep()` gains `seg_start`/`seg_end`:
   - LBPH: still `train()` on all N tiles (constraint §3.1), but run
     `predict_collect` only for probes in `[seg_start, seg_end)` →
     `lbph_dist` shrinks to `(seg_len, n)`.
   - SFace: embed all N (needed as candidates), compute `cos = norm[seg] @
     norm.T`; L2 from the slice. Memory drops from O(N²) to O(seg_len × N).
   - Cascade gate loop and the per-pair record loop iterate `i` over the slice
     only; record arrays sized `seg_len × (n-1)`.
   - CSV path unchanged in shape; rows are just the slice's rows.
3. New `--selection-manifest` flag (optional): when given, skip
   `select_one_image_per_person` and load the manifest's per-iteration
   identity→path map (Approach B seam, §6.2).
4. `summary.json` gains a `segment` block: `{count, index, seg_start, seg_end,
   n_total, query_rows, comparisons}`; output dir defaults to
   `..._seg{i}of{N}` when `segment_count > 1` (mirrors the light-front naming).
5. Per-iteration `_raw_runs` caching keeps working — the fingerprint must
   include the segment bounds so a cache from a different segment is never
   reused.

Estimated diff: small and local — the sweep is already structured as
"per-query-probe" loops; this mirrors what `lbph/independence_test_light_front.py`
already does. No behavior change when `--segment-count 1` (verification §12.1).

### 7.2 `src/benchmark/accuracy_ratio_hybrid.py`
1. Add `--segment-count/--segment-index`; apply `segment_bounds` to the sorted
   identity list from `load_originals()` (slice identities, keep all their
   images). Safe because probes are per-image deterministic (§3.5).
2. Emit raw counts (correct/total/no-face per mode per mod) alongside the
   percentages in the JSON so the merge sums counts, never averages
   percentages. Add the same `segment` block to the JSON.

### 7.3 New scripts — ALL BUILT 2026-07-19
- `scripts/lfw2_worker.py` (§6.1) — 5 idempotent stamped phases
  (PREFLIGHT / DATASET / CANARY / UNITS / PACKAGE); every heavy step is a
  subprocess of existing modules. `--member <name>` reads (variant, segment)
  units from `assignments.json`; `--pins` overridable for testing.
- `scripts/make_selection_manifest.py` (replaces the planned
  `make_probe_pack.py` — no pack zip needed under the in-memory-mods flow,
  §5 decision) + `scripts/make_batch_pins.py`.
- `scripts/merge_lfw2_segments.py` (§6.3) — coverage proof (segment set
  exact, bounds tile [0, n_total), per-segment row counts), count-sum merge
  via `src/stats_utils.py`, merged summary shaped like an unsegmented run,
  `comparisons.csv.gz` concat. `scripts/build_systematic_matrix.py` — 41-row
  tier-grouped matrix (md + json + FAR figure), PENDING for missing variants.
- `docs/BATCH_WORK/batch_pins.json` (7 artifact SHA-256s, versions; commit
  placeholder until campaign start), `assignments.json` (41-variant template),
  `assignments_lasalle_dryrun.json`, `requirements-batch.txt`,
  `selection_manifest_lasalle_test.json` (verification fixture).
- `docs/BATCH_WORK/MEMBER_GUIDE.md` — one page: clone at pinned commit,
  install `requirements-batch.txt`, run one worker command, upload the zips.

---

## 8. Batch assignment

`assignments.json` (committed):

```json
{
  "campaign": "lfw2_light_2026-07",
  "commit": "<pinned>",
  "tier": "light",
  "segment_count": 16,
  "iterations": 3,
  "assignments": {
    "member_a": [1, 2, 9],
    "member_b": [3, 4],
    "kyle":     [5, 6, 10, 11]
  }
}
```

Note `segment_count` (16) > member count (4–8): **micro-batching**. Each
segment is an independent unit; fast machines take more segments, a dropped
member's segments are reassigned without recomputation elsewhere, and each
completed segment is a natural checkpoint. The worker accepts
`--segment-index` repeatedly or a `--member <name>` flag that reads its list
from `assignments.json` and loops.

---

## 9. Hardware heterogeneity

**Cost profile (what actually dominates):** LBPH `predict_collect` against an
N-identity model per query probe (CPU, single-threaded inside OpenCV per call,
scales with query count → linear speedup from row slicing); SFace embedding of
the N probe images (one-time per member, CPU DNN, minutes-scale); cosine matrix
and gate are negligible. Robustness cost is per-(image × 41 mods) engine
scoring — embarrassingly parallel across identities.

| Axis | Handling |
|---|---|
| CPU speed spread | Micro-batches (§8) sized so the *slowest* expected machine finishes one segment in an acceptable sitting (target: ≤ 2–3 h/segment; calibrate below). Assign counts proportional to measured speed. |
| Calibration | The canary (§6.1 phase 3) doubles as a benchmark: its wall-clock is reported in the manifest; Kyle scales assignments after the first canary round. Anchor for absolute totals: the Jul-8 full-LFW 33M LBPH run's wall time on the D: machine is a known real number — use it, don't estimate from scratch. |
| RAM | Sliced sweep needs O(seg_len × N) doubles: e.g. N=5,749, 16 segments → ~360 rows × 5,749 × 8 B ≈ 17 MB for `lbph_dist`, similar for cos/L2, plus 23 MB probe tiles + model. Comfortably under 4 GB total including OpenCV/ONNX overhead — every member laptop qualifies. (Numbers are arithmetic from array shapes, not measurements — the canary confirms real peak RSS via the manifest.) |
| Disk | Approach B: pack size + results (<~1 GB). Approach A additionally: LFW tar 173 MB + extracted + 23,940 augmented images — require ~5 GB free, checked in preflight. |
| GPU | Ignored. LBPH is CPU-only; SFace via OpenCV DNN on CPU is a minutes-scale one-time cost per member. Do NOT let some members use a CUDA DNN backend while others use CPU — different backends are a float-drift source; preflight pins the backend to CPU. Same reasoning as the existing `--sample-cap` doc-string: never derive behavior from hardware tier. |
| OS differences | Repo already runs on Windows (junction handling in `setup_datasets.py::fix_junctions()` has POSIX fallbacks). Worker uses `pathlib` throughout; results record relative paths (§6.3.4). Members on macOS/Linux fine; the pinned wheel set in `requirements-batch.txt` must resolve on all three. |
| BLAS/thread nondeterminism | **Measured, not assumed (2026-07-19):** cosine matmul reductions are deterministic per NumPy build *only for a fixed operand shape* — slicing query rows changed BLAS kernel blocking and shifted sface_cosine by up to 3.8e-6 relative vs. the full matmul (no FP flips). Fixed in code: the hybrid test computes cosine as one matvec per query row, which is bit-identical across any segmentation on the same build (verified 12.2). LBPH distances were unaffected (per-probe `predict_collect` is naturally row-independent, and LBPH chi-square distance verified exactly symmetric). Cross-machine drift remains the canary's job. |

---

## 10. Determinism and audit safeguards

1. **Pinned everything**: `batch_pins.json` carries SHA-256 of thresholds.json,
   LBPH model/labels, SFace gallery/impostors, ONNX models, and the pinned
   commit; `requirements-batch.txt` pins exact `numpy`/`opencv-python` versions.
   Preflight refuses to run on mismatch; merge refuses to accept manifests that
   disagree.
2. **Input content hashing**: Approach B verifies every probe file's SHA from
   `selection_manifest.json`. Approach A hashes a fixed ~20-file sample of the
   augmented output listed in `batch_pins.json` — if a member's NumPy produced
   a different RNG stream, the sample hashes diverge and the run aborts before
   wasting hours.
3. **Cross-machine canary**: identical 64-identity sweep on every machine.
   Expectation: bit-identical CSVs. If a machine differs, Kyle sees exactly
   which columns and by how much *before* merging, and decides: exclude the
   machine, or (if drift is ~1e-6 on SFace floats only and flips no FP
   decision) document it in the merged summary. No silent tolerance.
4. **Coverage proof at merge**: segment bounds from manifests must tile
   [0, n_total) exactly; per-segment row counts must equal
   `seg_len × (n_total − 1) × iterations`; totals cross-checked against
   `comparisons.csv.gz` line counts.
5. **No invented numbers**: the merged summary records, per statistic, which
   segments contributed and links each member's manifest — the paper cites the
   merged summary; the audit trail goes zip → manifest → machine.

---

## 11. Output size note (`comparisons.csv`)

Full-LFW: ~33M rows/iteration × 11 columns including two path strings — plain
CSV plausibly runs to several GB per iteration across the team (estimate;
measure on the canary and extrapolate exactly). Hence:
- per-segment CSVs are **gzipped** in the result zip (`comparisons.csv.gz`);
- the classical light-front test defaults `--write-comparisons-csv` to False
  for exactly this reason — for the hybrid campaign Kyle explicitly wants the
  full CSV, so keep it on, but surface the projected size in the member guide
  so nobody is surprised;
- if size becomes prohibitive, fallback: ship `records.npz`-style compact
  arrays (the fields already exist in `run_sweep`'s record arrays) and
  regenerate CSV centrally — decision §13.4.

---

## 12. Verification plan (before any member touches it)

1. **Segment-1-of-1 equivalence**: `--segment-count 1` run vs. current
   unmodified code on La Salle (N=28) — summaries and CSVs byte-identical.
   **PASSED 2026-07-19** for the segment wiring itself (byte-identical CSVs +
   summary modulo output-dir path strings). The subsequent cosine-kernel fix
   (§7.1 deviation 2) intentionally shifts sface_cosine ≤ 3.8e-6 relative vs.
   pre-change code, zero FP-flag changes on all 756 pairs — segment
   invariance (12.2) was chosen over bit-compat with the old shape-dependent
   kernel, since the former is what every merge audits.
2. **Split-merge equivalence**: 2-way and 3-way segmented runs on La Salle,
   merged, vs. the unsegmented run — all FP counts, FAR, Yule Q, Fisher,
   cascade stats identical; robustness AR counts identical.
   **PASSED 2026-07-19** for the independence test: concatenated 2-way and
   3-way per-segment `comparisons.csv` byte-identical to the unsegmented run
   (756/756 rows); FP counts sum exactly (sface 17+3 = 10+8+2 = 20, cascade
   7+2 = 5+3+1 = 9). Robustness (§7.2) not yet implemented, still to verify.
3. **Selection-manifest equivalence**: manifest generated by
   `make_selection_manifest.py` over La Salle (seed 42, 28 identities), run via
   `--selection-manifest`, vs. direct `--dataset-dir` run.
   **PASSED 2026-07-19** — comparisons.csv byte-identical; corrupting one hex
   digit of one probe's sha256 aborts naming the exact identity and relpath.
4. **Sabotage tests**: **PASSED 2026-07-19** (all hard-fail with the offender
   named): tampered artifact hash in pins → preflight aborts printing
   expected/got; missing segment → merge refuses (`missing segment index(es)
   [2]`); duplicate segment index → merge refuses; deleted CSV row → merge
   refuses (row-count vs query_rows*(n_total-1) mismatch); mismatched
   iterations across segments → merge refuses; corrupted probe sha → test
   aborts (see 12.3); unknown `--member` → worker refuses listing known
   members.
5. **Dry campaign**: **PASSED 2026-07-19** — worker ran member
   `dryrun_member` on La Salle (motion_blur:5, 2 segments): preflight
   verified 7 pinned artifacts + versions, canary ran, 2 upload zips
   produced; rerun fully `[SKIP]`-stamped with no recompute; zips unpacked
   and merged → lbph 2 / sface 8 / cascade 8 / both 0 / 756 comparisons,
   exactly the known-good unsegmented totals.

---

## 13. Open decisions (Kyle)

1. **Which LFW2?** `data/lfw/{light,medium,heavy}` pre-modified probes vs.
   regenerating via `augment_split_light_medium.py` vs. producing the
   `data/lfw2_41mods` layout `evidence_matrix.py` expects. Affects the probe
   pack source and how the merged row plugs into the evidence matrix. (Past
   manual runs used augmented-split light/medium.)
2. **Robustness mode list**: `dl_only,cascade,parallel` (per "dl only" scoping)
   or all four modes since cv_only rides along at modest extra cost and
   completes the table?
3. **Robustness originals at LFW scale**: which originals dir — the LFW test
   split, or the same one-image-per-identity probe set? (The 41 mods are
   self-generated either way.)
4. **CSV vs. npz** for the per-pair records if the gzipped CSV is still too
   large for members' upload bandwidth (§11).
5. **Iterations**: keep `--lfw-iterations 3` (evidence-matrix default) or 1 for
   the first campaign? Multiplies every cost estimate by K.
6. **Tier count**: light only, or light + medium (doubles the campaign; the
   segment grid handles it as two campaigns).

---

## 14. Build order — ALL STEPS DONE 2026-07-19

1. §7.1 segment wiring + verification 12.1–12.2. ✅
2. §7.2 robustness sharding + count emission (plus
   `scripts/merge_robustness_segments.py`, `scripts/run_lfw2_robustness.py`). ✅
3. `make_selection_manifest.py` + `--selection-manifest` seam +
   `--modification` seam + verification 12.3. ✅
4. `merge_lfw2_segments.py` + `build_systematic_matrix.py` + sabotage
   tests 12.4. ✅
5. `lfw2_worker.py` + `batch_pins.json` + `requirements-batch.txt`. ✅
6. `MEMBER_GUIDE.md` + `assignments.json`; dry campaign 12.5. ✅

Remaining operational steps before distributing (Kyle):
1. Download LFW1 locally; run `make_selection_manifest.py` over it →
   `docs/BATCH_WORK/selection_manifest_lfw.json`; register it in
   `batch_pins.json`.
2. Commit everything; write the real commit into `batch_pins.json` and
   `assignments.json`.
3. Fill real member names / unit assignments (canary round sizes them, §9).
4. Decide remaining §13 items: iterations (template: 1), segment_count
   (template: 8), full 41 vs subset first wave (systematic doc §4.4).


