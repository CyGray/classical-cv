"""Hybrid independence test, per-pair CSVs suppressed.

Same sweep, same CLI, same numbers as ``python -m src.hybrid.independence_test``
- this only stops the two per-pair CSV writes:

* ``_raw_runs/run_N/comparisons.csv`` (streamed by ``run_sweep``), and
* ``<output-dir>/comparisons.csv`` (written by ``save_aggregated_csv``).

At full LFW1 scale each is ~11.5 GB over 33M ordered rows (see
``docs/READ THIS/FROZEN_THRESHOLDS_HYBRID.md``), so a single run needs ~23 GB of
free disk for files that are pure row-level audit output. ``records.npz`` and
``summary.json`` are still written, which is what the rank/threshold report and
``scripts/archive/extract_hybrid_unidirectional_ranks.py`` actually read, and is
the per-variant default the systematic-sweep spec already calls for
(``docs/features/SYSTEMATIC_INDEPENDENCE_TEST.md`` §5.4). The CSV stays
regenerable from ``records.npz`` if a row-level audit is ever needed.

Iteration resume/caching is unaffected: the cache check keys on
``records.npz`` + ``summary.json``, never on the CSV.

Usage (identical flags to the module it wraps)::

    python scripts/archive/run_hybrid_independence_no_pair_csv.py \
        --dataset-dir data/lfw-dataset \
        --output-dir reports/independence/hybrid/lfw1_yunet \
        --selection-manifest docs/features/BATCH_WORK/selection_manifest_lfw1_hybrid.json \
        --iterations 1 --random-seed 42 --no-plots
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.hybrid import independence_test as hybrid_test  # noqa: E402

_run_sweep = hybrid_test.run_sweep


def _run_sweep_no_csv(*args, **kwargs):
    """``run_sweep`` already treats ``csv_path=None`` as 'skip the CSV'."""
    kwargs["csv_path"] = None
    return _run_sweep(*args, **kwargs)


def _skip_aggregated_csv(aggregated, path) -> None:
    print(f"[SKIP] aggregated per-pair CSV not written: {path}")


# main() resolves both through module globals at call time, so patching here is
# enough - no fork of the sweep itself.
hybrid_test.run_sweep = _run_sweep_no_csv
hybrid_test.save_aggregated_csv = _skip_aggregated_csv


if __name__ == "__main__":
    raise SystemExit(hybrid_test.main())
