"""One-shot plot generator for a raw independence-test comparison file.

Takes the per-pair "raw comparison" output of an independence test -
``comparisons.csv`` (query_identity, query_image_path, candidate_identity,
candidate_image_path, distance_normalized) or an equivalent JSON list of the
same records - and (re)generates the two standard figures used everywhere
else in this repo (src/independence_plots.py):

  * <prefix>distance_histogram.png  - binned histogram + Gaussian KDE overlay
  * <prefix>distance_curve_plot.png - pure KDE density curve

Meant for post-hoc plotting: e.g. a teammate ran an older version of an
independence test that only wrote comparisons.csv/summary.json (the plain
independence_test.py mains only ever plot the KDE curve, never a true
histogram - only the *_light_front.py variants do), and you want the missing
figure(s) without re-running the (possibly slow) N x (N-1) sweep.

Column/key detection is deliberately loose since an older run's CSV/JSON
schema may differ slightly from today's src/*/independence_test.py output;
override with --column if auto-detection guesses wrong.

Usage:
    python scripts/reporting/plot_independence_comparisons.py outputs/lbph/independence_test/comparisons.csv
    python scripts/reporting/plot_independence_comparisons.py results.json --column raw_distance --label "LBPH - LFW1"
    python scripts/reporting/plot_independence_comparisons.py comparisons.csv --threshold 12.5 --output-dir reports/adhoc
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from src.independence_plots import save_distance_curve_plot, save_distance_histogram  # noqa: E402

# Column/key names tried in priority order when --column isn't given.
DISTANCE_KEY_CANDIDATES = [
    "distance_normalized",
    "normalized_distance",
    "distance",
    "raw_distance",
    "l2",
    "l2_score",
    "score",
    "cosine_sim",
    "cosine",
]

# Keys under which a JSON object might nest the list of per-pair records.
JSON_LIST_KEYS = ["comparisons", "records", "rows", "pairs", "data", "all_records"]

# Presence of any of these (with no raw list found) means "aggregate-only report".
SUMMARY_ONLY_MARKERS = ("distance_statistics", "error_pair_thresholds", "suggested_thresholds")


def _pick_key(available: list[str], forced: str | None) -> str:
    if forced:
        for c in available:
            if c.lower() == forced.lower():
                return c
        raise SystemExit(f"[ERROR] --column '{forced}' not found. Available: {available}")
    lower_map = {c.lower(): c for c in available}
    for cand in DISTANCE_KEY_CANDIDATES:
        if cand in lower_map:
            return lower_map[cand]
    # Fallback: any column that looks distance-ish and isn't a path/identity field.
    for c in available:
        cl = c.lower()
        if "dist" in cl and "path" not in cl and "identity" not in cl:
            return c
    raise SystemExit(
        "[ERROR] Could not auto-detect the distance column/key. "
        f"Available: {available}. Pass --column explicitly."
    )


def _records_to_values(records: list, forced_column: str | None) -> tuple[np.ndarray, str]:
    if records and isinstance(records[0], (int, float)):
        return np.asarray(records, dtype=np.float64), "(flat list)"
    if not records or not isinstance(records[0], dict):
        raise SystemExit("[ERROR] JSON list entries are neither numbers nor objects.")
    key = _pick_key(list(records[0].keys()), forced_column)
    values: list[float] = []
    skipped = 0
    for row in records:
        try:
            values.append(float(row[key]))
        except (TypeError, ValueError, KeyError):
            skipped += 1
    if skipped:
        print(f"[WARN] Skipped {skipped} record(s) with a missing/non-numeric '{key}' value.")
    return np.asarray(values, dtype=np.float64), key


def _load_csv(path: Path, forced_column: str | None) -> tuple[np.ndarray, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(f"[ERROR] {path} has no header row.")
        key = _pick_key(list(reader.fieldnames), forced_column)
        values: list[float] = []
        skipped = 0
        for row in reader:
            raw = (row.get(key) or "").strip()
            try:
                values.append(float(raw))
            except ValueError:
                skipped += 1
        if skipped:
            print(f"[WARN] Skipped {skipped} row(s) with a non-numeric '{key}' value.")
        return np.asarray(values, dtype=np.float64), key


def _load_json(path: Path, forced_column: str | None) -> tuple[np.ndarray, str]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))

    if isinstance(payload, list):
        return _records_to_values(payload, forced_column)

    if isinstance(payload, dict):
        for list_key in JSON_LIST_KEYS:
            if isinstance(payload.get(list_key), list) and payload[list_key]:
                return _records_to_values(payload[list_key], forced_column)

        if isinstance(payload.get("lowest_distance_pairs"), list) and payload["lowest_distance_pairs"]:
            print(
                "[WARN] Only 'lowest_distance_pairs' found (a truncated top-K sample, "
                "NOT the full distribution) - the histogram/KDE below will misrepresent "
                "the true distance distribution. Point this at comparisons.csv if you have it."
            )
            return _records_to_values(payload["lowest_distance_pairs"], forced_column)

        if any(marker in payload for marker in SUMMARY_ONLY_MARKERS):
            raise SystemExit(
                "[ERROR] This looks like a summary.json (aggregate statistics only - "
                "min/max/mean/percentiles), not a raw per-comparison list. "
                "Point this script at the sibling comparisons.csv instead."
            )

        raise SystemExit(
            f"[ERROR] No recognizable list of records in {path}. Top-level keys: {list(payload.keys())}"
        )

    raise SystemExit(f"[ERROR] Unsupported JSON shape in {path} (expected a list or object).")


def load_distances(path: Path, forced_column: str | None) -> tuple[np.ndarray, str]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path, forced_column)
    if suffix == ".csv":
        return _load_csv(path, forced_column)
    # Unknown extension: sniff the first non-whitespace character.
    sniff = path.read_text(encoding="utf-8-sig", errors="ignore")[:256].lstrip()
    if sniff.startswith("{") or sniff.startswith("["):
        return _load_json(path, forced_column)
    return _load_csv(path, forced_column)


def _print_stats(values: np.ndarray, key: str) -> None:
    print(f"[INFO] Distance column/key: '{key}'")
    print(f"[INFO] Comparisons loaded: {values.size:,}")
    if values.size == 0:
        return
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    pct = np.percentile(values, percentiles)
    print(
        f"[STATS] min={values.min():.4f} max={values.max():.4f} "
        f"mean={values.mean():.4f} median={np.median(values):.4f} std={values.std():.4f}"
    )
    print("[STATS] percentiles: " + ", ".join(f"p{p}={v:.4f}" for p, v in zip(percentiles, pct)))


def _try_autoload_threshold(input_path: Path) -> float | None:
    """Best-effort: pick up the spec threshold from a sibling summary.json."""
    candidate = input_path.parent / "summary.json"
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
        spec = (payload.get("error_pair_thresholds") or {}).get("spec")
        if spec and "normalized_threshold" in spec:
            value = float(spec["normalized_threshold"])
            print(f"[INFO] Auto-picked up spec threshold {value:.4f} from {candidate.name}")
            return value
    except Exception:
        pass
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot a distance histogram + KDE curve from a raw independence-test comparison file."
    )
    parser.add_argument("input_path", type=Path, help="Path to comparisons.csv or a raw-records JSON file.")
    parser.add_argument("--column", default=None, help="Explicit distance column/key name (skips auto-detection).")
    parser.add_argument("--output-dir", default=None, help="Where to write the PNGs (default: alongside input).")
    parser.add_argument("--prefix", default="", help="Filename prefix, e.g. 'lbph_lfw1_' to avoid collisions.")
    parser.add_argument("--label", default=None, help="Title label, e.g. 'LBPH - La Salle DB1' (default: filename stem).")
    parser.add_argument("--bins", type=int, default=40, help="Histogram bin count (default: 40, matches the pipeline).")
    parser.add_argument("--curve-points", type=int, default=500)
    parser.add_argument("--curve-bandwidth", type=float, default=None, help="KDE bandwidth override (default: Silverman's rule).")
    parser.add_argument("--threshold", type=float, default=None, help="Optional vertical threshold marker.")
    parser.add_argument(
        "--no-threshold-autoload", action="store_true",
        help="Don't look for a sibling summary.json to auto-fill --threshold.",
    )
    parser.add_argument(
        "--assume-normalized", action="store_true",
        help="Force the 0-100 normalized x-axis window (default: auto-detected from the column name).",
    )
    parser.add_argument("--xlim", type=float, nargs=2, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--no-histogram", action="store_true", help="Skip distance_histogram.png.")
    parser.add_argument("--no-curve", action="store_true", help="Skip distance_curve_plot.png.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_path.resolve()
    if not input_path.is_file():
        print(f"[ERROR] Not a file: {input_path}")
        return 1

    values, key = load_distances(input_path, args.column)
    if values.size == 0:
        print("[ERROR] No usable numeric distance values were loaded.")
        return 1
    _print_stats(values, key)

    threshold = args.threshold
    if threshold is None and not args.no_threshold_autoload:
        threshold = _try_autoload_threshold(input_path)

    if args.xlim is not None:
        xlim = (float(args.xlim[0]), float(args.xlim[1]))
    elif args.assume_normalized or "normalized" in key.lower():
        xlim = (0.0, 100.0)
    else:
        pad = max((float(values.max()) - float(values.min())) * 0.05, 1e-6)
        xlim = (float(values.min() - pad), float(values.max() + pad))

    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    label = args.label or input_path.stem

    if not args.no_histogram:
        hist_path = output_dir / f"{args.prefix}distance_histogram.png"
        bw = save_distance_histogram(
            values, str(hist_path),
            threshold=threshold, bins=args.bins,
            title=f"{label}: Inter-Identity Distance Histogram",
            xlabel=f"Distance ({key})",
            curve_points=args.curve_points, curve_bandwidth=args.curve_bandwidth,
            xlim=xlim,
        )
        print(f"[PLOT] Histogram (+KDE overlay): {hist_path}  [KDE bandwidth={bw:.4f}]")

    if not args.no_curve:
        curve_path = output_dir / f"{args.prefix}distance_curve_plot.png"
        bw = save_distance_curve_plot(
            values, str(curve_path),
            threshold=threshold,
            title=f"{label}: Inter-Identity Distance Curve",
            xlabel=f"Distance ({key})",
            curve_points=args.curve_points, curve_bandwidth=args.curve_bandwidth,
            xlim=xlim,
        )
        print(f"[PLOT] KDE curve: {curve_path}  [KDE bandwidth={bw:.4f}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
