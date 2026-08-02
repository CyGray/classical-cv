"""Shared orchestration for the classical independence tests.

Ties together the three shared pieces so each model's ``independence_test.py`` stays
thin and identical apart from its feature extractor + distance metric:

* :func:`write_default_plots` - the two default paper figures (histogram + FAR
  curve) from a distance sample and an ``error_pair_report`` result. Used by the
  in-memory (small-N) path.
* :func:`stream_and_report` - the full large-N path: memmap the feature matrix,
  run the parallel streaming sweep, build the rank-based report from the streamed
  top-K, write the plots + lowest-pairs CSV, and hand the pieces back so the caller
  still owns its ``summary.json`` shape.

Plots use each model's RAW feature-distance scale (chi-square for LBPH, euclidean
for Eigen/Fisher) with the spec k-th-error-pair threshold marked, so the figure's
threshold line is literally the number the report recommends.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile

import numpy as np

from src.independence_common import error_pair_report_from_topk, format_error_pair_report
from src.independence_plots import (
    compute_kde_curve, save_distance_curve_plot, save_distance_histogram,
    save_far_curve, tight_xlim,
)
from src.independence_streaming import pairwise_topk_stream, expected_unique_pairs

HISTOGRAM_NAME = "distance_histogram.png"
CURVE_NAME = "distance_curve_plot.png"
HISTOGRAM_TIGHT_NAME = "distance_histogram_tight.png"
CURVE_TIGHT_NAME = "distance_curve_plot_tight.png"
FAR_NAME = "far_curve.png"
LOWEST_NAME = "lowest_distance_pairs.csv"


def add_scaling_args(parser: argparse.ArgumentParser, *, include_max_identities: bool = True) -> None:
    """Speed / memory / plotting flags shared by the independence mains.

    *include_max_identities* is False for callers (e.g. the hybrid test) that
    already define ``--max-identities`` themselves.
    """
    if include_max_identities:
        parser.add_argument("--max-identities", type=int, default=0,
                            help="If > 0, use a seeded random subset of this many identities "
                                 "(makes LFW-scale sweeps tractable; 0 = all).")
    parser.add_argument("--streaming-threshold", type=int, default=3_000_000,
                        help="Switch to the memory-safe streaming path when the unique "
                             "comparison count exceeds this (default 3,000,000).")
    parser.add_argument("--workers", type=int, default=6,
                        help="Worker processes for the streaming pairwise sweep.")
    parser.add_argument("--chunk-rows", type=int, default=64,
                        help="Query rows per streaming work chunk.")
    parser.add_argument("--keep-top", type=int, default=4096,
                        help="Smallest unique-pair distances kept for the rank report.")
    parser.add_argument("--block-rows", type=int, default=384,
                        help="Inner candidate block size for the distance kernel.")
    parser.add_argument("--sample-cap", type=int, default=2_000_000,
                        help="Max distances sampled for the histogram/percentiles (streaming). "
                             "Fixed default so the same dataset yields the same statistical "
                             "sample regardless of machine; override explicitly if needed - "
                             "do not derive this from hardware-tier detection (it would make "
                             "published percentiles/plots machine-dependent).")
    parser.add_argument("--segment-count", type=int, default=1,
                        help="Split the sweep into this many query-row segments (sharding).")
    parser.add_argument("--segment-index", type=int, default=1,
                        help="1-based segment to run when --segment-count > 1.")
    parser.add_argument("--device", choices=["cpu", "gpu"], default="cpu",
                        help="Distance-kernel backend (gpu requires CuPy).")
    parser.add_argument("--histogram-bins", type=int, default=40)
    parser.add_argument("--curve-points", type=int, default=500)
    parser.add_argument("--curve-bandwidth", type=float, default=None)
    parser.add_argument("--plots", action=argparse.BooleanOptionalAction, default=True,
                        help="Write distance_histogram.png + far_curve.png (default: on).")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress bars.")


def figure_prefix(output_dir: str) -> str:
    """Filename prefix so exported figures stay unique when copied into a flat
    folder (e.g. the Android gallery via ``export-cv-figs``). The report
    output-dir name already encodes ``<model>_<dataset>`` by convention
    (``lbph_lasalle``, ``lbph_lsdb2``, ``eigenfaces_lfw``, ...), so reusing it
    means every figure filename carries both the model and the dataset."""
    return os.path.basename(os.path.normpath(output_dir))


def default_output_paths(output_dir: str) -> dict[str, str]:
    prefix = figure_prefix(output_dir)
    return {
        "distance_histogram": os.path.join(output_dir, f"{prefix}_{HISTOGRAM_NAME}"),
        "distance_curve_plot": os.path.join(output_dir, f"{prefix}_{CURVE_NAME}"),
        "distance_histogram_tight": os.path.join(output_dir, f"{prefix}_{HISTOGRAM_TIGHT_NAME}"),
        "distance_curve_plot_tight": os.path.join(output_dir, f"{prefix}_{CURVE_TIGHT_NAME}"),
        "far_curve": os.path.join(output_dir, f"{prefix}_{FAR_NAME}"),
        "lowest_distance_pairs": os.path.join(output_dir, f"{prefix}_{LOWEST_NAME}"),
    }


def write_default_plots(
    sample_distances_normalized,
    report: dict,
    output_dir: str,
    *,
    model_label: str,
    distance_label: str,
    bins: int = 40,
    curve_points: int = 500,
    curve_bandwidth: float | None = None,
    plots: bool = True,
) -> dict:
    """Write the paper's default figures on the normalized 0-100 scale:
    ``distance_histogram.png`` / ``distance_curve_plot.png`` (fixed 0-100 x-axis,
    comparable across every model/dataset figure) plus ``_tight`` companions
    (x-axis cropped to the data's own range +/-10% padding, for readability -
    same figures otherwise, same KDE curve). ``far_curve.png`` rounds it out.
    *sample_distances_normalized* must already be normalized; the spec threshold
    line uses ``normalized_threshold``.

    The KDE curve is computed once and reused across the fixed/tight histogram
    and curve-plot renders (4 images total) instead of the 4x recompute a naive
    per-figure call would do - matters at the sample sizes ``stream_and_report``
    can hand this (up to ``sample_cap`` distances).
    """
    paths = default_output_paths(output_dir)
    result = {
        "distance_histogram": None, "distance_curve_plot": None,
        "distance_histogram_tight": None, "distance_curve_plot_tight": None,
        "far_curve": None, "kde_bandwidth_used": None,
    }
    if not plots:
        return result
    os.makedirs(output_dir, exist_ok=True)

    spec = report.get("spec") or {}
    threshold = spec.get("normalized_threshold")
    far_percent = spec.get("realized_far_percent")

    values = np.asarray(sample_distances_normalized, dtype=np.float64)
    values = values[np.isfinite(values)]
    precomputed_kde = None
    bw = 0.0
    if values.size > 1:
        x, y, bw = compute_kde_curve(values, points=curve_points, bandwidth=curve_bandwidth)
        precomputed_kde = (x, y, bw)
    tight_range = tight_xlim(values)

    for suffix, xlim, hist_key, curve_key in (
        ("", (0.0, 100.0), "distance_histogram", "distance_curve_plot"),
        (" (tight)", tight_range, "distance_histogram_tight", "distance_curve_plot_tight"),
    ):
        save_distance_histogram(
            sample_distances_normalized, paths[hist_key],
            threshold=threshold,
            title=f"{model_label} Independence Test: Inter-Identity Distance Histogram{suffix}",
            xlabel="Normalized inter-identity distance (0-100)",
            bins=bins, curve_points=curve_points, curve_bandwidth=curve_bandwidth,
            xlim=xlim, far_percent=far_percent, precomputed_kde=precomputed_kde,
        )
        save_distance_curve_plot(
            sample_distances_normalized, paths[curve_key],
            threshold=threshold,
            title=f"{model_label} Independence Test: Inter-Identity Distance Curve{suffix}",
            xlabel="Normalized inter-identity distance (0-100)",
            curve_points=curve_points, curve_bandwidth=curve_bandwidth,
            xlim=xlim, precomputed_kde=precomputed_kde,
        )
        result[hist_key] = paths[hist_key]
        result[curve_key] = paths[curve_key]

    wrote_far = save_far_curve(
        report, paths["far_curve"], model_label=model_label, engine_label=distance_label,
        threshold_field="normalized_threshold",
        xlabel="Match threshold (normalized 0-100)",
    )
    result["far_curve"] = paths["far_curve"] if wrote_far else None
    result["kde_bandwidth_used"] = bw
    return result


def write_lowest_pairs_csv(pairs: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["query_identity", "candidate_identity",
                           "raw_distance", "normalized_distance"],
        )
        writer.writeheader()
        for p in pairs:
            writer.writerow({
                "query_identity": p["query_identity"],
                "candidate_identity": p["candidate_identity"],
                "raw_distance": f"{p['raw_distance']:.6f}",
                "normalized_distance": f"{p['normalized_distance']:.6f}",
            })


def _normalize_stats(stats: dict, scale: float) -> dict:
    """Scale raw distance moments/percentiles onto the 0-100 normalized axis."""
    if stats.get("count", 0) == 0:
        return stats
    out = dict(stats)
    for key in ("min_distance", "max_distance", "mean_distance",
                "median_distance", "std_dev"):
        if key in out and out[key] is not None:
            out[key] = float(out[key]) * scale
    if "percentiles" in out:
        out["percentiles"] = {p: float(v) * scale for p, v in out["percentiles"].items()}
    out["scale"] = "normalized_0_100"
    return out


def segment_bounds(n: int, segment_count: int, segment_index: int) -> tuple[int, int]:
    """1-based *segment_index* of *segment_count* over query rows [0, n)."""
    segment_count = max(1, int(segment_count))
    segment_index = max(1, int(segment_index))
    seg_size = (n + segment_count - 1) // segment_count
    start = (segment_index - 1) * seg_size
    end = min(n, start + seg_size)
    return start, end


def stream_and_report(
    feature_matrix: np.ndarray,
    names: list[str],
    metric: str,
    *,
    output_dir: str,
    model_label: str,
    distance_label: str,
    target_far_ppm: float,
    error_pair_rank: int | None,
    workers: int = 6,
    chunk_rows: int = 64,
    keep_top: int = 4096,
    block_rows: int = 384,
    device: str = "cpu",
    sample_cap: int = 1_000_000,
    segment_count: int = 1,
    segment_index: int = 1,
    bins: int = 40,
    curve_points: int = 500,
    curve_bandwidth: float | None = None,
    plots: bool = True,
    quiet: bool = False,
) -> dict:
    """Large-N streaming path. Returns report / stats / lowest_pairs / plot paths.

    The caller keeps ownership of ``summary.json`` (each model's shape differs);
    this only produces the shared artifacts and the numbers to embed.
    """
    n = int(feature_matrix.shape[0])
    os.makedirs(output_dir, exist_ok=True)

    # Persist features as .npy so the worker processes can mmap them read-only.
    feat_tmp = tempfile.NamedTemporaryFile(prefix="indep_feat_", suffix=".npy", delete=False)
    feat_tmp.close()
    np.save(feat_tmp.name, np.ascontiguousarray(feature_matrix, dtype=np.float32))

    seg_start, seg_end = segment_bounds(n, segment_count, segment_index)
    result = None
    try:
        result = pairwise_topk_stream(
            feat_tmp.name, n, metric,
            seg_start=seg_start, seg_end=seg_end,
            workers=workers, chunk_rows=chunk_rows, keep_top=keep_top,
            block_rows=block_rows, device=device, sample_cap=sample_cap,
            progress=not quiet,
        )
    finally:
        try:
            os.unlink(feat_tmp.name)
        except OSError:
            pass

    dmax = result["max_distance"]
    top_i, top_j = result["top_i"], result["top_j"]
    top_pairs = [(names[int(i)], names[int(j)]) for i, j in zip(top_i, top_j)]
    report = error_pair_report_from_topk(
        top_unique_distances=result["top_distances"],
        top_unique_pairs=top_pairs,
        total_ordered_comparisons=result["ordered_comparisons"],
        max_distance=dmax,
        target_far_ppm=target_far_ppm,
        explicit_rank=error_pair_rank,
    )

    lowest_pairs = []
    for d, i, j in zip(result["top_distances"], top_i, top_j):
        lowest_pairs.append({
            "query_identity": names[int(i)],
            "candidate_identity": names[int(j)],
            "raw_distance": float(d),
            "normalized_distance": (100.0 * float(d) / dmax) if dmax > 0 else 0.0,
        })
    lowest_pairs = lowest_pairs[:20]

    scale = (100.0 / dmax) if dmax > 0 else 0.0
    sample_norm = np.asarray(result["sample"], dtype=np.float64) * scale
    stats_norm = _normalize_stats(result["stats"], scale)

    plot_paths = write_default_plots(
        sample_norm, report, output_dir,
        model_label=model_label, distance_label=distance_label,
        bins=bins, curve_points=curve_points, curve_bandwidth=curve_bandwidth, plots=plots,
    )
    write_lowest_pairs_csv(lowest_pairs, default_output_paths(output_dir)["lowest_distance_pairs"])

    # Release the raw-distance memmap file (stats/sample already extracted).
    try:
        os.unlink(result["raw_memmap_path"])
    except OSError:
        pass

    return {
        "report": report,
        "stats": stats_norm,
        "lowest_pairs": lowest_pairs,
        "plots": plot_paths,
        "max_distance": dmax,
        "unique_pairs": result["unique_pairs"],
        "ordered_comparisons": result["ordered_comparisons"],
        "segment": {"start": seg_start, "end": seg_end,
                    "count": segment_count, "index": segment_index},
    }


def run_streaming_and_save(
    args,
    *,
    names: list[str],
    feature_matrix: np.ndarray,
    metric: str,
    model_label: str,
    distance_label: str,
    person_dirs,
    pre_stats: dict,
    model_key: str,
) -> int:
    """Streaming sweep + summary.json + console report, shared by all classical mains.

    *args* must carry the flags added by :func:`add_scaling_args` plus
    ``dataset_dir``, ``output_dir``, ``target_far_ppm`` and ``error_pair_rank``.

    Note: this path always writes ``"iterations": 1`` - unlike the exact (small-N)
    path, which averages 10 seeded repeats per pair (see
    ``per_run_error_pair_thresholds`` in ``src/independence_common.py``), the
    streaming path used for large-N runs (e.g. full LFW) does not currently
    support multi-iteration averaging, so its thresholds/statistics carry no
    run-to-run stability estimate. This is a known protocol gap between the two
    paths (see docs/IMPROVEMENT_SPEC.md, item B4), not a claim that the two are
    equivalent.
    """
    res = stream_and_report(
        feature_matrix, names, metric,
        output_dir=args.output_dir, model_label=model_label, distance_label=distance_label,
        target_far_ppm=args.target_far_ppm, error_pair_rank=args.error_pair_rank,
        workers=args.workers, chunk_rows=args.chunk_rows, keep_top=args.keep_top,
        block_rows=args.block_rows, device=args.device, sample_cap=args.sample_cap,
        segment_count=args.segment_count, segment_index=args.segment_index,
        bins=args.histogram_bins, curve_points=args.curve_points,
        curve_bandwidth=args.curve_bandwidth, plots=args.plots, quiet=args.quiet,
    )
    summary = {
        "dataset": {"path": args.dataset_dir, "total_identities": len(person_dirs),
                    "selected_identities": len(names)},
        "mode": "streaming",
        "model": model_key,
        "preprocessing": pre_stats,
        "comparison": {"ordered_comparisons": res["ordered_comparisons"],
                       "unique_pairs": res["unique_pairs"], "segment": res["segment"]},
        "distance_statistics": res["stats"],
        "error_pair_thresholds": res["report"],
        "lowest_distance_pairs": res["lowest_pairs"],
        "plots": res["plots"],
        "iterations": 1,
    }
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[SAVE] JSON summary: {json_path}")
    print("\n" + format_error_pair_report(res["report"]))
    if res["plots"].get("distance_histogram"):
        print(f"[PLOT] Histogram: {res['plots']['distance_histogram']}")
    if res["plots"].get("distance_curve_plot"):
        print(f"[PLOT] Distance curve: {res['plots']['distance_curve_plot']}")
    if res["plots"].get("far_curve"):
        print(f"[PLOT] FAR curve: {res['plots']['far_curve']}")
    return 0


def expected_ordered_comparisons(n: int) -> int:
    return n * (n - 1)


__all__ = [
    "add_scaling_args", "write_default_plots", "write_lowest_pairs_csv",
    "stream_and_report", "default_output_paths", "segment_bounds",
    "expected_ordered_comparisons", "expected_unique_pairs",
]
