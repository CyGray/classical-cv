# LS-Face Raspberry Pi `r3` integration

Candidate port for the compact LBPH descriptor plus quality-first cascade:

```text
YuNet detect -> cheap quality probes -> SFace direct on trigger
                              -> LBPH only when quality is clear
                              -> accept / confident reject / SFace ambiguity gate
```

This directory is intentionally separate from `porting-sets/cascade-porting/`.
That directory remains the deployed `r1_n8_g8x8` rollback bundle. This
integration uses `r3_n8_g6x6` (radius 3, neighbors 8, grid 6x6) and is marked
candidate-only until Raspberry Pi calibration completes.

## Source and artifacts

- Upstream repo: `../../upstream/lsface-raspberry-pi/` (submodule, latest
  `master`, Git LFS hydrated).
- Default source DB: upstream `db/lasalledb.npy`.
- Paired baseline release: `enrollment/baseline-r1/current.json` ->
  `r1_n8_g8x8` YAML.
- Generated candidate release: `enrollment/current.json` ->
  `r3_n8_g6x6` YAML.
- Thresholds: `config/thresholds.json`; do not promote this file to production
  without Pi validation.

Both releases use same 36-identity x 10-row cohort as upstream. Selection is
`numpy.default_rng(42).choice(..., replace=False)` per identity, ordered by
upstream `record['id']`.

## Build candidate release

From this directory:

```powershell
python rebuild_release.py --descriptor deployed --output-root enrollment\baseline-r1
python rebuild_release.py --descriptor selected --output-root enrollment
```

Explicit source/output paths:

```powershell
python rebuild_release.py `
  --database ..\..\upstream\lsface-raspberry-pi\db\lasalledb.npy `
  --output-root enrollment
```

For the reviewed push artifacts, use stable release names:

```powershell
python rebuild_release.py --descriptor deployed `
  --output-root enrollment\baseline-r1 --release-name release-r1_n8_g8x8
python rebuild_release.py --descriptor selected `
  --output-root enrollment --release-name release-r3_n8_g6x6
```

Omitting `--release-name` is still supported for local timestamped experiments;
those extra release directories stay ignored.

The builder retrains LBPH with explicit descriptor constructor arguments,
rebuilds the SFace gallery from the same selected source rows, writes
descriptor and selection metadata into each release manifest, and atomically
updates each `current.json` pointer.

## Run runtime

Use upstream model files, or pass another directory containing the two ONNX
files:

```powershell
python hybrid_rpi.py `
  --models-dir ..\..\upstream\lsface-raspberry-pi `
  --image path\to\frame.jpg
```

Runtime refuses descriptor mismatches between thresholds, manifest, and the
serialized LBPH model. Quality-triggered frames never call LBPH; result fields
include `route`, `quality`, and `descriptor_id` for instrumentation.

## Hardware-team API compatibility

`HybridCascade` keeps upstream call shape:

```python
cascade = HybridCascade(base_dir=".")
results = cascade.infer(frame_bgr)  # list[dict], BGR ndarray
```

`hybrid.py` re-exports same class for callers that use upstream module name;
maintained implementation remains in `hybrid_rpi.py`.

`infer()` returns `[]` when no face is detected. Each face record keeps the
usual `status`, `engine`, `name`, `bbox=(x, y, w, h)`, `distance`/`l2`, and
`lbph_distance` fields; new diagnostics are additive (`route`, `quality`,
`descriptor_id`, `cosine`). The PC test normalizes old bundle's single-dict
return into this list shape, so setup 1 and setup 2 share display/logging code.
Setup 1 uses paired upstream r1 YAML plus paired selected gallery; it does not
use old local rollback release under `porting-sets/cascade-porting/`.

### Compatibility boundary

The public hardware-facing contract is intentionally close to upstream:

| Contract | Upstream/old expectation | r3 implementation |
|---|---|---|
| Class/import | `HybridCascade` from `hybrid` | Same; `hybrid.py` is a shim |
| Constructor | `HybridCascade(base_dir=".")` | Same positional call; extra paths are keyword-only |
| Input | BGR `numpy.ndarray`, shape `(H, W, 3)` | Same |
| Output | `list[dict]`; `[]` for no face | Same for the upstream contract |
| Box | `(x, y, w, h)` integer tuple | Same, clamped to the frame |
| Legacy fields | `status`, `engine`, `name`, `bbox`, `distance`/`l2`, `lbph_distance`, `gate_reason` | Retained; `route`, `quality`, `descriptor_id`, and `cosine` are additive |
| Core methods | `__init__`, `_normalize_lbph`, `infer` | Retained; helpers are additive |

Known, deliberate differences are explicit: r3 probes quality before LBPH,
so a triggered frame has `lbph_distance=None`; it uses direct YuNet rows rather
than exposing the upstream `FaceAligner` helper; and its compact SFace gallery
stores one mean feature per identity (same feature shape `(1, 128)`) instead
of upstream's per-enrollment-image gallery. The old local rollback can return a
single `{"status": "no_face"}` dict and only processes its largest face; the
PC test's `normalize_results()` adapter converts that legacy shape to the
shared list shape.

## Verification

```powershell
python -m unittest discover -s test -p "test_*.py"
```

Before hardware promotion, run the release on Pi and record: clean/self-match
retention, 41-transform retention, SFace escalation rate, LBPH-call rate,
end-to-end latency, RSS, CPU, and thermal behavior. Keep `r1` available for
atomic rollback.

## Push boundary

Keep the push limited to source, configs, tests, provenance manifests, the two
active release pointers, and their reviewed release artifacts. The active
`lbph.yml` and `sface_gallery.npy` files are Git-LFS assets. The upstream repo
is a submodule and remains the source of the original LFS database/models.

Logs, `__pycache__`, timestamped rebuilds, and inactive release directories are
local-only and ignored. The PC logs remain available locally at
`logs/config1-old-r1.log` and `logs/config2-new-r3.log`, but are not push
artifacts.
