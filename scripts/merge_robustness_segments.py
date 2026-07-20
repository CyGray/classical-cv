#!/usr/bin/env python3
"""Merge sharded accuracy_ratio_hybrid segment JSON results into a unified report.

Usage:
    python scripts/merge_robustness_segments.py \\
        --segment-jsons reports/benchmark/accuracy_ratio_hybrid_seg*.json \\
        --output-json reports/benchmark/accuracy_ratio_hybrid.json \\
        --output-md reports/benchmark/accuracy_ratio_hybrid.md
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.modifications import MODIFICATIONS, VARIANT_COUNT
from src.stats_utils import wilson_interval_percent

AR_TIE_TOLERANCE = 2.0  # keep in sync with src/benchmark/accuracy_ratio_hybrid.py


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge sharded accuracy_ratio_hybrid segment JSON files."
    )
    parser.add_argument(
        "--segment-jsons",
        nargs="+",
        required=True,
        help="Path patterns or explicit list of segment JSON files.",
    )
    parser.add_argument(
        "--battery-csvs",
        nargs="*",
        default=[],
        help="Optional per-segment probe CSV files to concatenate.",
    )
    parser.add_argument(
        "--output-json",
        default="reports/benchmark/accuracy_ratio_hybrid.json",
        help="Output merged JSON path.",
    )
    parser.add_argument(
        "--output-md",
        default="reports/benchmark/accuracy_ratio_hybrid.md",
        help="Output merged Markdown path.",
    )
    parser.add_argument(
        "--output-battery-csv",
        default="reports/benchmark/accuracy_ratio_hybrid_probes.csv",
        help="Merged battery CSV path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Expand any globs in segment-jsons
    json_paths: list[Path] = []
    for pattern in args.segment_jsons:
        expanded = glob.glob(pattern)
        if expanded:
            json_paths.extend(Path(p) for p in sorted(expanded))
        else:
            json_paths.append(Path(pattern))

    json_paths = sorted(list(set(json_paths)))
    if not json_paths:
        raise RuntimeError("No segment JSON files specified or found.")

    payloads = [json.loads(p.read_text(encoding="utf-8")) for p in json_paths if p.exists()]
    if not payloads:
        raise RuntimeError("Failed to load any valid segment JSON payload.")

    base_payload = payloads[0]
    modes = list(base_payload["overall_ar_percent"].keys())
    originals_dir = base_payload["originals_dir"]
    seed = base_payload.get("seed", 42)
    no_face_policy = base_payload.get("no_face_policy", "fallback")

    total_originals = sum(p["originals"] for p in payloads)
    clean_no_face = sum(p["clean_no_face"] for p in payloads)

    clean_matched = {m: 0 for m in modes}
    for p in payloads:
        raw_clean = p.get("clean_matched")
        for m in modes:
            if raw_clean is not None:
                clean_matched[m] += int(raw_clean[m])
            else:
                # Older segment payloads only carry percentages; reconstruct.
                clean_matched[m] += round((p["clean_acceptance_percent"][m] / 100.0) * p["originals"])

    # Aggregate modifications
    mod_level_data: dict[tuple[str, str], dict] = {}

    for p in payloads:
        for mod_entry in p["modifications"]:
            mod_name = mod_entry["modification"]
            for level_entry in mod_entry["levels"]:
                lvl = level_entry["level"]
                key = (mod_name, str(lvl))
                if key not in mod_level_data:
                    mod_level_data[key] = {
                        "mod_name": mod_name,
                        "level": lvl,
                        "modified_total": 0,
                        "no_face": 0,
                        "matched": {m: 0 for m in modes},
                        "escalated": 0,
                    }
                seg_total = level_entry["modified_total"]
                mod_level_data[key]["modified_total"] += seg_total
                mod_level_data[key]["no_face"] += level_entry["no_face"]
                for m in modes:
                    matched_cnt = level_entry["matched"][m]
                    mod_level_data[key]["matched"][m] += matched_cnt
                if "cascade" in modes:
                    esc_raw = level_entry.get("escalated")
                    if esc_raw is not None:
                        mod_level_data[key]["escalated"] += int(esc_raw)
                    elif level_entry.get("cascade_escalation_percent") is not None:
                        mod_level_data[key]["escalated"] += round(
                            (level_entry["cascade_escalation_percent"] / 100.0) * seg_total
                        )

    per_mod: list[dict] = []
    for mod_name, fn, levels in MODIFICATIONS:
        level_rows = []
        for level in levels:
            key = (mod_name, str(level))
            ld = mod_level_data.get(key)
            if ld is None:
                raise RuntimeError(
                    f"Segment payloads have no data for modification {mod_name!r} "
                    f"level {level!r} - refusing to merge an incomplete suite."
                )
            tot = ld["modified_total"]
            m_matched = ld["matched"]
            esc = ld["escalated"]
            level_rows.append({
                "level": level,
                "modified_total": tot,
                "no_face": ld["no_face"],
                "matched": m_matched,
                "escalated": esc if "cascade" in modes else None,
                "ar_percent": {m: 100.0 * m_matched[m] / tot for m in modes},
                "cascade_escalation_percent": (
                    100.0 * esc / tot if "cascade" in modes else None
                ),
            })
        mod_ar = {
            m: sum(r["ar_percent"][m] for r in level_rows) / len(level_rows) for m in modes
        }
        mod_probes = sum(r["modified_total"] for r in level_rows)
        mod_ar_ci = {
            m: wilson_interval_percent(
                sum(r["matched"][m] for r in level_rows), mod_probes
            )
            for m in modes
        }
        row = {
            "modification": mod_name,
            "ar_percent": mod_ar,
            "ar_pooled_ci95": mod_ar_ci,
            "levels": level_rows,
        }
        if "cascade" in modes:
            row["cascade_escalation_percent"] = sum(
                r["cascade_escalation_percent"] for r in level_rows
            ) / len(level_rows)
        if "cv_only" in modes and "dl_only" in modes:
            delta = mod_ar["dl_only"] - mod_ar["cv_only"]
            row["dl_minus_cv_points"] = delta
            row["winner"] = (
                "tie" if abs(delta) <= AR_TIE_TOLERANCE
                else ("dl_stronger" if delta > 0 else "cv_stronger")
            )
            if "cascade" in modes:
                row["cascade_vs_best_points"] = (
                    mod_ar["cascade"] - max(mod_ar["cv_only"], mod_ar["dl_only"])
                )
        per_mod.append(row)

    overall = {
        m: sum(row["ar_percent"][m] for row in per_mod) / len(per_mod) for m in modes
    }
    total_probes = total_originals * VARIANT_COUNT
    overall_ci = {
        m: wilson_interval_percent(
            sum(r["matched"][m] for row in per_mod for r in row["levels"]),
            total_probes,
        )
        for m in modes
    }

    # Latencies (weighted average by probes)
    mean_latencies = {}
    for m in modes:
        total_lat = 0.0
        tot_cnt = 0
        for p in payloads:
            p_cnt = p["modified_probes_per_mode"]
            lat = p.get("mean_latency_ms", {}).get(m, 0.0)
            total_lat += lat * p_cnt
            tot_cnt += p_cnt
        mean_latencies[m] = total_lat / tot_cnt if tot_cnt else 0.0

    merged_payload = {
        "originals_dir": originals_dir,
        "originals": total_originals,
        "total_unsegmented_originals": total_originals,
        "segment_count": len(payloads),
        "segment_index": 0,
        "variant_count": VARIANT_COUNT,
        "modified_probes_per_mode": total_probes,
        "seed": seed,
        "no_face_policy": no_face_policy,
        "clean_no_face": clean_no_face,
        "clean_acceptance_percent": {
            m: 100.0 * clean_matched[m] / total_originals for m in modes
        },
        "clean_acceptance_ci95": {
            m: wilson_interval_percent(clean_matched[m], total_originals) for m in modes
        },
        "overall_ar_percent": overall,
        "overall_ar_pooled_ci95": overall_ci,
        "mean_latency_ms": mean_latencies,
        "modifications": per_mod,
    }
    if "cv_only" in modes and "dl_only" in modes:
        merged_payload["complementarity"] = {
            "cv_stronger": [r["modification"] for r in per_mod if r.get("winner") == "cv_stronger"],
            "dl_stronger": [r["modification"] for r in per_mod if r.get("winner") == "dl_stronger"],
            "tie": [r["modification"] for r in per_mod if r.get("winner") == "tie"],
            "tie_tolerance_points": AR_TIE_TOLERANCE,
        }
        if "cascade" in modes:
            merged_payload["complementarity"]["cascade_within_2pts_of_best"] = sum(
                1 for r in per_mod if r["cascade_vs_best_points"] >= -AR_TIE_TOLERANCE
            )

    # Save JSON
    out_json_path = Path(args.output_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(merged_payload, indent=2), encoding="utf-8")

    # Build Markdown
    out_md_path = Path(args.output_md)
    lines = [
        "# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade",
        "",
        f"Originals: `{originals_dir}` ({total_originals} tiles) | 41 variants/original | seed={seed} | no-face policy: `{no_face_policy}`.",
        "",
        "AR per modification = mean over its levels; overall = mean over modifications.",
        "",
        "| Metric | " + " | ".join(modes) + " |",
        "|---| " + " | ".join("---:" for _ in modes) + " |",
    ]
    clean_str = " | ".join(f"{merged_payload['clean_acceptance_percent'][m]:.2f}%" for m in modes)
    overall_str = " | ".join(f"**{overall[m]:.2f}%**" for m in modes)
    ci_str = " | ".join(
        f"{overall_ci[m]['percent']:.2f}% "
        f"[{overall_ci[m]['ci95_low_percent']:.2f}-{overall_ci[m]['ci95_high_percent']:.2f}]"
        for m in modes
    )
    lat_str = " | ".join(f"{mean_latencies[m]:.2f} ms" for m in modes)
    lines.extend([
        f"| Clean acceptance | {clean_str} |",
        f"| **Overall AR** | {overall_str} |",
        f"| Pooled AR [95% CI] | {ci_str} |",
        f"| Mean latency | {lat_str} |",
        "",
        "## Per modification",
        "",
        "| Modification | " + " | ".join(modes) + " | winner | escalation |",
        "|---| " + " | ".join("---:" for _ in modes) + " |---|---:|",
    ])

    for row in per_mod:
        mod_name = row["modification"]
        vals = " | ".join(f"{row['ar_percent'][m]:.1f}%" for m in modes)
        winner = row.get("winner", "-")
        esc = f"{row['cascade_escalation_percent']:.0f}%" if "cascade_escalation_percent" in row else "-"
        lines.append(f"| {mod_name} | {vals} | {winner} | {esc} |")

    lines.append("")
    out_md_path.write_text("\n".join(lines), encoding="utf-8")

    # Concatenate per-segment battery CSVs (header kept from the first file only).
    if args.battery_csvs:
        csv_paths: list[Path] = []
        for pattern in args.battery_csvs:
            expanded = glob.glob(pattern)
            if expanded:
                csv_paths.extend(Path(p) for p in sorted(expanded))
            else:
                csv_paths.append(Path(pattern))
        csv_paths = [p for p in dict.fromkeys(csv_paths) if p.exists()]
        if csv_paths:
            out_csv_path = Path(args.output_battery_csv)
            out_csv_path.parent.mkdir(parents=True, exist_ok=True)
            with out_csv_path.open("w", encoding="utf-8", newline="") as fh:
                for idx, p in enumerate(csv_paths):
                    rows = p.read_text(encoding="utf-8").splitlines()
                    if not rows:
                        continue
                    for row in rows if idx == 0 else rows[1:]:
                        fh.write(row + "\n")
            print(f"[OK] Concatenated {len(csv_paths)} battery CSVs -> {out_csv_path}")
        else:
            print("[WARN] --battery-csvs given but no files found; skipping CSV merge.")

    print(f"[SUCCESS] Merged {len(payloads)} segments -> {out_json_path} and {out_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
