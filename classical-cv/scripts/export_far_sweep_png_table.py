"""Full-bleed PNG table for the LBPH FAR-target sweep (far_sweep_tar_report.py),
per docs/experiments/pairwise-verification/GUIDE.md's full-bleed table
convention. Reuses render_full_bleed_table rather than duplicating it.
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from export_verification_png_tables import render_full_bleed_table  # noqa: E402

CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent

REPORT_JSON = CLASSICAL_CV_DIR / "reports" / "benchmark" / "far_sweep_tar_report.json"
OUT_DIR = WORKSPACE_ROOT / "docs" / "experiments" / "pairwise-verification" / "lfw-results" / "SWEEP"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "summary-table.png"


def format_far(ppm) -> str:
    if ppm is None:
        return "-"
    if ppm >= 10000:
        return f"{ppm / 10000:.1f}%"
    if ppm >= 1000:
        return f"{ppm / 10000:.2f}%"
    return f"{ppm:.2f} ppm"


def main() -> None:
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    headers = ["Operating Point", "Realized FAR", "Raw Threshold", "Clean TAR (%)", "Overall TAR (%)"]
    col_widths = [3.4, 1.6, 1.6, 1.6, 1.9]

    data = []
    family_boundaries = []
    last_family = None
    for row in payload["rows"]:
        if row["family"] != last_family and last_family is not None:
            family_boundaries.append(len(data))
        last_family = row["family"]
        data.append(
            [
                row["label"],
                format_far(row["realized_far_ppm"]),
                f"{row['raw_threshold']:.4f}",
                f"{row['clean_tar_percent']:.2f}%",
                f"{row['overall_tar_percent']:.2f}%",
            ]
        )

    render_full_bleed_table(headers, data, col_widths, str(OUT_PATH), family_boundaries=family_boundaries)
    print(f"[SAVE] {OUT_PATH}")


if __name__ == "__main__":
    main()
