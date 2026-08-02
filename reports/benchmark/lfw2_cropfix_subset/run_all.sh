#!/usr/bin/env bash
set -uo pipefail
cd "C:\Users\acer\Downloads\USLS 4th Year\Computer Vision\classical-cv"
ROOT="reports/benchmark/lfw2_cropfix_subset"
OVERRIDE_DIR="C:/Users/acer/.claude/jobs/0f45ede8/tmp/thr_override"
STANDALONE_THR="$OVERRIDE_DIR/thresholds_standalone.json"
SPLIT="data/splits/lfw_ident_split_seed42.json"

run_one() {
  name="$1"; shift
  echo "=== START $name $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  "$@"
  code=$?
  echo "=== END $name exit=$code $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  return $code
}

# Arm A standalone (assume_cropped=true, standalone thresholds + SFace L2 override)
run_one armA_standalone env PYTHONPATH="$OVERRIDE_DIR" SFACE_L2_OVERRIDE=1.030628 \
  py -3.11 scripts/pipeline/run_lfw2_robustness.py \
  --split-manifest "$SPLIT" --limit-identities 1500 \
  --modes cv_only,dl_only --lbph-assume-cropped true \
  --thresholds-json "$STANDALONE_THR" \
  --output-dir "$ROOT/armA_standalone" \
  > "$ROOT/logs/armA_standalone.log" 2>&1
A1=$?

# Arm A cascade (assume_cropped=true, deployed thresholds, no env overrides)
run_one armA_cascade \
  py -3.11 scripts/pipeline/run_lfw2_robustness.py \
  --split-manifest "$SPLIT" --limit-identities 1500 \
  --modes cascade --lbph-assume-cropped true \
  --output-dir "$ROOT/armA_cascade" \
  > "$ROOT/logs/armA_cascade.log" 2>&1
A2=$?

# Arm B standalone (assume_cropped=false, standalone thresholds + SFace L2 override)
run_one armB_standalone env PYTHONPATH="$OVERRIDE_DIR" SFACE_L2_OVERRIDE=1.030628 \
  py -3.11 scripts/pipeline/run_lfw2_robustness.py \
  --split-manifest "$SPLIT" --limit-identities 1500 \
  --modes cv_only,dl_only --lbph-assume-cropped false \
  --thresholds-json "$STANDALONE_THR" \
  --output-dir "$ROOT/armB_standalone" \
  > "$ROOT/logs/armB_standalone.log" 2>&1
B1=$?

# Arm B cascade (assume_cropped=false, deployed thresholds, no env overrides)
run_one armB_cascade \
  py -3.11 scripts/pipeline/run_lfw2_robustness.py \
  --split-manifest "$SPLIT" --limit-identities 1500 \
  --modes cascade --lbph-assume-cropped false \
  --output-dir "$ROOT/armB_cascade" \
  > "$ROOT/logs/armB_cascade.log" 2>&1
B2=$?

echo "=== ALL DONE armA_standalone=$A1 armA_cascade=$A2 armB_standalone=$B1 armB_cascade=$B2 ==="
