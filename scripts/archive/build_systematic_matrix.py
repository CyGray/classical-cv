#!/usr/bin/env python3
"""Build the 41-row systematic-suite matrix from per-variant merged outputs.

Reads one merged ``summary.json`` per (modification, level) variant - the
output of ``scripts/utils/merge_lfw2_segments.py`` for that variant - from
anywhere under ``--variants-root`` (conventionally
``reports/independence/systematic_lfw2/<name>_<level>/``), and emits:

  - ``systematic_matrix.json``  - full row data, present + PENDING, no
    invented numbers (missing variants carry null fields, never guesses).
  - ``systematic_matrix.md``    - the same, as a tier-grouped Markdown table
    (light / medium / heavy sections; families sorted alphabetically within
    a tier), with a PENDING list at the end.
  - ``systematic_matrix_far.png`` - grouped bar plot of cascade FAR per
    variant, grouped by tier, skipping missing variants.

A variant is matched to a merged output directory by its summary's own
``modification`` block ({"name", "level", "tier"}), not by directory-name
parsing (robust to negative levels like ``rotation:-10``).

Usage:
    python scripts/archive/build_systematic_matrix.py \\
        --variants-root reports/independence/systematic_lfw2 \\
        --output-dir reports/independence/systematic_lfw2
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.modifications import MODIFICATIONS, variant_tier  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

TIERS = ("light", "medium", "heavy")
TIER_COLORS = {"light": "#4c9be8", "medium": "#ff7f0e", "heavy": "#d62728"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--variants-root", required=True,
                   help="Dir containing one merged variant output dir per (mod, level).")
    p.add_argument("--output-dir", default=str(PROJECT_ROOT / "reports" / "independence" / "systematic_lfw2"),
                   help="Where systematic_matrix.{json,md} + the figure are written.")
    return p.parse_args()


def _expected_variants() -> list[tuple[str, object, str]]:
    """(family, level, tier) for all 41 variants, in MODIFICATIONS order."""
    out = []
    for name, _fn, levels in MODIFICATIONS:
        for level in levels:
            out.append((name, level, variant_tier(name, level)))
    return out


def _discover_summaries(root: Path) -> dict[tuple[str, str], dict]:
    """Scan root for summary.json files carrying a 'modification' block.
    Keyed by (name, str(level)) so int/float level formatting doesn't matter."""
    found: dict[tuple[str, str], dict] = {}
    for summary_path in root.rglob("summary.json"):
        try:
            with summary_path.open("r", encoding="utf-8") as f:
                summary = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        mod = summary.get("modification")
        if not mod:
            continue
        key = (mod["name"], str(mod["level"]))
        if key in found:
            print(f"[WARN] multiple summaries for {mod['name']}:{mod['level']} - "
                  f"keeping {found[key]['_source_dir']}, ignoring {summary_path.parent}")
            continue
        summary["_source_dir"] = str(summary_path.parent)
        found[key] = summary
    return found


def _row_from_summary(family: str, level, tier: str, summary: dict | None) -> dict:
    if summary is None:
        return {
            "family": family, "level": level, "tier": tier, "status": "PENDING",
            "source_dir": None, "comparisons": None,
            "lbph_far_ppm": None, "lbph_far_ppm_ci95_low": None, "lbph_far_ppm_ci95_high": None,
            "sface_far_percent": None, "sface_far_percent_ci95_low": None, "sface_far_percent_ci95_high": None,
            "both_fp_count": None,
            "cascade_far_percent": None, "cascade_far_percent_ci95_low": None, "cascade_far_percent_ci95_high": None,
            "yule_q": None, "fisher_p_two_sided": None, "escalation_percent": None,
        }
    pooled = summary["pooled"]
    ci = pooled["fp_rates_ci95"]
    div = pooled["diversity"]
    return {
        "family": family, "level": level, "tier": tier, "status": "present",
        "source_dir": summary.get("_source_dir"),
        "comparisons": pooled["comparisons"],
        "lbph_far_ppm": ci["lbph"]["percent"] * 1.0e4,
        "lbph_far_ppm_ci95_low": ci["lbph"]["ci95_low_percent"] * 1.0e4,
        "lbph_far_ppm_ci95_high": ci["lbph"]["ci95_high_percent"] * 1.0e4,
        "sface_far_percent": ci["sface"]["percent"],
        "sface_far_percent_ci95_low": ci["sface"]["ci95_low_percent"],
        "sface_far_percent_ci95_high": ci["sface"]["ci95_high_percent"],
        "both_fp_count": div["table"]["both"],
        "cascade_far_percent": ci["cascade"]["percent"],
        "cascade_far_percent_ci95_low": ci["cascade"]["ci95_low_percent"],
        "cascade_far_percent_ci95_high": ci["cascade"]["ci95_high_percent"],
        "yule_q": div["q_statistic"],
        "fisher_p_two_sided": div["fisher"]["p_two_sided"],
        "escalation_percent": summary.get("mean_escalation_percent"),
    }


def build_rows(variants_root: Path) -> list[dict]:
    found = _discover_summaries(variants_root)
    rows = []
    for name, level, tier in _expected_variants():
        summary = found.get((name, str(level)))
        rows.append(_row_from_summary(name, level, tier, summary))
    return rows


def _fmt_ci(val, lo, hi, unit: str, decimals: int = 2) -> str:
    if val is None:
        return ""
    return f"{val:.{decimals}f}{unit} [{lo:.{decimals}f}-{hi:.{decimals}f}]"


def _fmt(val, decimals: int = 3) -> str:
    if val is None:
        return ""
    return f"{val:.{decimals}f}"


def write_json(rows: list[dict], output_dir: Path) -> Path:
    pending = [f"{r['family']}:{r['level']}" for r in rows if r["status"] == "PENDING"]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "variant_count_expected": len(rows),
        "variant_count_present": sum(1 for r in rows if r["status"] == "present"),
        "pending": pending,
        "rows": rows,
    }
    path = output_dir / "systematic_matrix.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def write_markdown(rows: list[dict], output_dir: Path) -> Path:
    lines = [
        "# Systematic Single-Modification LFW2 Independence Matrix",
        "",
        "One row per (modification family, level). Frozen thresholds "
        "(`src/hybrid/thresholds.json`); FAR figures and CIs are pooled "
        "across iterations from summed counts (never averaged percentages). "
        "Blank cells = not yet run (see Pending, below) - no invented numbers.",
        "",
        "Statistical honesty note: impostor pairs share identities, so "
        "pair-count Wilson intervals overstate effective precision "
        "(docs/SYSTEMATIC_INDEPENDENCE_TEST.md sec 7).",
        "",
    ]
    present_count = sum(1 for r in rows if r["status"] == "present")
    lines.append(f"Present: {present_count} / {len(rows)} variants.")
    lines.append("")

    header = ("| Family | Level | Comparisons | LBPH FAR (ppm) [95% CI] | "
               "SFace FAR (%) [95% CI] | Both-FP | Cascade FAR (%) [95% CI] | "
               "Yule Q | Fisher p (2-sided) | Escalation % |")
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"

    for tier in TIERS:
        tier_rows = sorted(
            (r for r in rows if r["tier"] == tier), key=lambda r: (r["family"], r["level"])
        )
        if not tier_rows:
            continue
        lines.append(f"## Tier: {tier}")
        lines.append("")
        lines.append(header)
        lines.append(sep)
        for r in tier_rows:
            comparisons = "" if r["comparisons"] is None else str(r["comparisons"])
            lbph = _fmt_ci(r["lbph_far_ppm"], r["lbph_far_ppm_ci95_low"], r["lbph_far_ppm_ci95_high"], "", 1)
            sface = _fmt_ci(r["sface_far_percent"], r["sface_far_percent_ci95_low"],
                             r["sface_far_percent_ci95_high"], "%")
            both = "" if r["both_fp_count"] is None else str(r["both_fp_count"])
            cascade = _fmt_ci(r["cascade_far_percent"], r["cascade_far_percent_ci95_low"],
                               r["cascade_far_percent_ci95_high"], "%")
            yq = _fmt(r["yule_q"])
            fp = _fmt(r["fisher_p_two_sided"], 4)
            esc = "" if r["escalation_percent"] is None else f"{r['escalation_percent']:.1f}"
            status_marker = "" if r["status"] == "present" else " *(PENDING)*"
            lines.append(
                f"| {r['family']}{status_marker} | {r['level']} | {comparisons} | {lbph} | "
                f"{sface} | {both} | {cascade} | {yq} | {fp} | {esc} |"
            )
        lines.append("")

    pending = [r for r in rows if r["status"] == "PENDING"]
    if pending:
        lines.append("## Pending (not yet run)")
        lines.append("")
        for r in sorted(pending, key=lambda r: (TIERS.index(r["tier"]), r["family"], str(r["level"]))):
            lines.append(f"- `{r['family']}:{r['level']}` (tier: {r['tier']})")
        lines.append("")

    path = output_dir / "systematic_matrix.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_figure(rows: list[dict], output_dir: Path) -> Path | None:
    present = [r for r in rows if r["status"] == "present" and r["cascade_far_percent"] is not None]
    if not present:
        print("[WARN] no present variants with cascade FAR data - skipping figure.")
        return None

    present_sorted = sorted(present, key=lambda r: (TIERS.index(r["tier"]), r["family"], str(r["level"])))
    labels = [f"{r['family']}\n{r['level']}" for r in present_sorted]
    vals = [r["cascade_far_percent"] for r in present_sorted]
    err_low = [r["cascade_far_percent"] - r["cascade_far_percent_ci95_low"] for r in present_sorted]
    err_high = [r["cascade_far_percent_ci95_high"] - r["cascade_far_percent"] for r in present_sorted]
    colors = [TIER_COLORS[r["tier"]] for r in present_sorted]

    x = np.arange(len(present_sorted))
    fig, ax = plt.subplots(figsize=(max(8, 0.55 * len(present_sorted)), 5))
    ax.bar(x, vals, 0.6, color=colors, yerr=[err_low, err_high], capsize=3, ecolor="#555555")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Hybrid cascade FAR (%)")
    ax.set_title("Systematic single-modification suite: cascade FAR per variant, grouped by tier")
    ax.grid(axis="y", alpha=0.3)

    from matplotlib.patches import Patch
    handles = [Patch(color=TIER_COLORS[t], label=t) for t in TIERS if any(r["tier"] == t for r in present_sorted)]
    ax.legend(handles=handles, title="tier", loc="upper left", frameon=False)

    fig.tight_layout()
    path = output_dir / "systematic_matrix_far.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> int:
    args = parse_args()
    variants_root = Path(args.variants_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not variants_root.exists():
        print(f"[ERROR] --variants-root does not exist: {variants_root}", file=sys.stderr)
        return 1

    rows = build_rows(variants_root)
    json_path = write_json(rows, output_dir)
    md_path = write_markdown(rows, output_dir)
    fig_path = write_figure(rows, output_dir)

    present = sum(1 for r in rows if r["status"] == "present")
    print(f"[SUCCESS] {present}/{len(rows)} variants present.")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"  Figure: {fig_path if fig_path else '(skipped - no data)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
