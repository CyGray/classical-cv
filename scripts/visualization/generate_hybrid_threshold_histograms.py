"""Generate separate hybrid-cascade LBPH and SFace threshold distributions.

The input is the recorded joint-cascade comparison CSV.  The score samples
are kept on their native scales: OpenCV LBPH ``predict_collect`` distance and
SFace L2 distance.  The threshold markers are read from the live runtime
configuration (SFace's L2 constant is read from ``src/sface/recognizer.py``
because the JSON ``sface.l2_genuine`` key is not runtime-authoritative).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
CLASSICAL_CV = ROOT / "classical-cv"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CLASSICAL_CV) not in sys.path:
    sys.path.insert(0, str(CLASSICAL_CV))

from scripts.visualization.manuscript_svg import (  # noqa: E402
    configure_matplotlib,
    export_matplotlib_svg,
)

configure_matplotlib()
import matplotlib.pyplot as plt  # noqa: E402

from src.independence_plots import compute_kde_curve  # noqa: E402


DEFAULT_INPUT = (
    ROOT
    / "docs"
    / "results"
    / "independence_test"
    / "reruns"
    / "finalized_2026-08-10"
    / "hybrid_lasalle_processed"
    / "comparisons.csv"
)
DEFAULT_THRESHOLDS = CLASSICAL_CV / "src" / "hybrid" / "thresholds.json"
DEFAULT_SFACE_SOURCE = CLASSICAL_CV / "src" / "sface" / "recognizer.py"
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "experiments"
    / "independence_test"
    / "hybrid_thresholds_live_2026-08-14"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--thresholds-json", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--sface-source", type=Path, default=DEFAULT_SFACE_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_scores(path: Path) -> tuple[np.ndarray, np.ndarray]:
    lbph: list[float] = []
    sface_l2: list[float] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lbph.append(float(row["mean_lbph_distance"]))
            sface_l2.append(float(row["mean_sface_l2"]))

    lbph_arr = np.asarray(lbph, dtype=np.float64)
    sface_arr = np.asarray(sface_l2, dtype=np.float64)
    for name, values in (("LBPH", lbph_arr), ("SFace L2", sface_arr)):
        if values.size == 0 or not np.isfinite(values).all():
            raise ValueError(f"{name} score sample is empty or non-finite")
    return lbph_arr, sface_arr


def load_thresholds(thresholds_path: Path, sface_source: Path) -> dict[str, float]:
    config = json.loads(thresholds_path.read_text(encoding="utf-8"))
    gate = config["gate"]
    source_text = sface_source.read_text(encoding="utf-8")
    match = re.search(
        r"^L2_GENUINE_THRESHOLD\s*=\s*([0-9]+(?:\.[0-9]+)?)",
        source_text,
        re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"Could not find L2_GENUINE_THRESHOLD in {sface_source}")
    return {
        "lbph_descriptor_id": str(config.get("lbph_descriptor", {}).get("id", "unknown")),
        "candidate_only": bool(config.get("candidate_only", False)),
        "threshold_status": str(config.get("status", "live")),
        "lbph_tau_accept": float(gate["tau_accept"]),
        "lbph_tau_reject": float(gate["tau_reject"]),
        "sface_l2_genuine": float(match.group(1)),
    }


def _plot_distribution(
    values: np.ndarray,
    output_stem: Path,
    *,
    title: str,
    xlabel: str,
    threshold_lines: list[tuple[str, float, str, str]],
) -> None:
    bins = 40
    x_kde, y_kde, bandwidth = compute_kde_curve(values, points=500)
    counts, edges = np.histogram(values, bins=bins)
    bin_width = float(edges[1] - edges[0])

    figure, axis = plt.subplots(figsize=(10, 6))
    axis.hist(
        values,
        bins=bins,
        edgecolor="black",
        alpha=0.75,
        color="#4c72b0",
        label="Inter-identity scores",
    )
    axis.plot(
        x_kde,
        y_kde * values.size * bin_width,
        color="#dd8452",
        linewidth=2,
        label=f"KDE (bandwidth = {bandwidth:.4g})",
    )

    for label, threshold, color, linestyle in threshold_lines:
        axis.axvline(
            threshold,
            color=color,
            linestyle=linestyle,
            linewidth=2,
            label=f"{label} = {threshold:.6g}",
        )

    data_min = float(np.min(values))
    data_max = float(np.max(values))
    threshold_values = [threshold for _, threshold, _, _ in threshold_lines]
    x_min = min(data_min, *threshold_values, float(x_kde.min()))
    x_max = max(data_max, *threshold_values, float(x_kde.max()))
    pad = max((x_max - x_min) * 0.04, 1e-3)
    axis.set_xlim(x_min - pad, x_max + pad)
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel("Count")
    axis.grid(True, alpha=0.3)
    axis.legend(loc="upper right")
    figure.tight_layout()

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    export_matplotlib_svg(
        figure,
        output_stem.with_suffix(".svg"),
        metadata={
            "Title": title,
            "Description": "Recorded hybrid-cascade inter-identity comparisons",
        },
    )
    plt.close(figure)


def main() -> int:
    args = parse_args()
    input_csv = resolve(args.input_csv)
    thresholds_json = resolve(args.thresholds_json)
    sface_source = resolve(args.sface_source)
    output_dir = resolve(args.output_dir)

    for required in (input_csv, thresholds_json, sface_source):
        if not required.is_file():
            raise FileNotFoundError(required)

    lbph, sface_l2 = load_scores(input_csv)
    thresholds = load_thresholds(thresholds_json, sface_source)
    descriptor_id = thresholds["lbph_descriptor_id"]
    candidate_note = " candidate-only" if thresholds["candidate_only"] else ""

    _plot_distribution(
        lbph,
        output_dir / "hybrid_cascade_lbph_threshold_hist_kde",
        title=f"Hybrid Cascade (LBPH, {descriptor_id}{candidate_note}): Inter-Identity Distance Distribution",
        xlabel="LBPH native predict_collect distance (lower is better)",
        threshold_lines=[
            ("tau_accept", thresholds["lbph_tau_accept"], "#c44e52", "--"),
            ("tau_reject", thresholds["lbph_tau_reject"], "#8172b3", ":"),
        ],
    )
    _plot_distribution(
        sface_l2,
        output_dir / "hybrid_cascade_sface_threshold_hist_kde",
        title=f"Hybrid Cascade (SFace; LBPH {descriptor_id}{candidate_note}): Inter-Identity Distance Distribution",
        xlabel="SFace L2 distance (lower is better)",
        threshold_lines=[
            ("l2_genuine", thresholds["sface_l2_genuine"], "#c44e52", "--"),
        ],
    )

    metadata = {
        "schema": "hybrid-threshold-hist-kde-v1",
        "input_csv": str(input_csv),
        "input_csv_sha256": sha256_file(input_csv),
        "thresholds_json": str(thresholds_json),
        "thresholds_json_sha256": sha256_file(thresholds_json),
        "sface_source": str(sface_source),
        "sface_source_sha256": sha256_file(sface_source),
        "lbph_descriptor_id": descriptor_id,
        "candidate_only": thresholds["candidate_only"],
        "threshold_status": thresholds["threshold_status"],
        "sample_counts": {"lbph": int(lbph.size), "sface_l2": int(sface_l2.size)},
        "thresholds": {
            "lbph_tau_accept": thresholds["lbph_tau_accept"],
            "lbph_tau_reject": thresholds["lbph_tau_reject"],
            "sface_l2_genuine": thresholds["sface_l2_genuine"],
        },
        "scope": (
            f"{('Candidate-only' if thresholds['candidate_only'] else 'Frozen live')} "
            f"LBPH {descriptor_id} gate thresholds evaluated on LSDB pre-cropped "
            "hybrid-cascade comparisons; not recalibration."
        ),
        "outputs": {
            "lbph_png": str(output_dir / "hybrid_cascade_lbph_threshold_hist_kde.png"),
            "lbph_svg": str(output_dir / "hybrid_cascade_lbph_threshold_hist_kde.svg"),
            "sface_png": str(output_dir / "hybrid_cascade_sface_threshold_hist_kde.png"),
            "sface_svg": str(output_dir / "hybrid_cascade_sface_threshold_hist_kde.svg"),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
