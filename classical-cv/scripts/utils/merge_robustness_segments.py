#!/usr/bin/env python3
"""Merge sharded accuracy_ratio_hybrid segment JSON results into a unified report.

Usage:
    python scripts/utils/merge_robustness_segments.py \\
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.modifications import DL41_DETECTOR_CANONICAL, get_modification_set
from src.stats_utils import mcnemar_test, wilson_interval_percent

AR_TIE_TOLERANCE = 2.0  # keep in sync with src/benchmark/accuracy_ratio_hybrid.py
PAIRING_TABLE_KEYS = ("both_right", "cv_only_right", "dl_only_right", "both_wrong")


def _pairing_stats(table: dict) -> dict:
    """Recompute A/B metrics from a summed paired-correctness table."""
    try:
        counts = {key: int(table[key]) for key in PAIRING_TABLE_KEYS}
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Invalid complementarity pairing table.") from exc
    if any(value < 0 for value in counts.values()):
        raise RuntimeError("Complementarity pairing counts must be non-negative.")

    probes = sum(counts.values())
    lbph_wrong = counts["dl_only_right"] + counts["both_wrong"]
    return {
        "probes": probes,
        "table": counts,
        "recovery_rate_ci95": (
            wilson_interval_percent(counts["dl_only_right"], lbph_wrong)
            if lbph_wrong else None
        ),
        "both_fail_ci95": wilson_interval_percent(counts["both_wrong"], probes) if probes else None,
        "mcnemar": mcnemar_test(counts["cv_only_right"], counts["dl_only_right"]),
    }


def _sum_pairing_stats(stats: list[dict]) -> dict:
    """Sum segment 2x2 cells before deriving rates and p-values."""
    table = {key: 0 for key in PAIRING_TABLE_KEYS}
    for stat in stats:
        source = stat.get("table") if isinstance(stat, dict) else None
        if not isinstance(source, dict):
            raise RuntimeError("Segment is missing complementarity pairing data.")
        for key in PAIRING_TABLE_KEYS:
            try:
                value = int(source[key])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError("Segment has an invalid complementarity pairing table.") from exc
            if value < 0:
                raise RuntimeError("Segment has negative complementarity pairing counts.")
            table[key] += value
        expected_probes = stat.get("probes")
        if expected_probes is not None and int(expected_probes) != sum(int(source[key]) for key in PAIRING_TABLE_KEYS):
            raise RuntimeError("Segment complementarity probe count does not match its pairing table.")
    return _pairing_stats(table)


def _merge_complementarity_battery(payloads: list[dict], modifications_list: list[tuple]) -> dict:
    """Merge only recovery/McNemar A/B evidence from compatible segments."""
    batteries = []
    for payload in payloads:
        battery = payload.get("complementarity_battery")
        if not isinstance(battery, dict):
            raise RuntimeError(
                "All cv_only+dl_only segments must include complementarity_battery; "
                "rerun missing segments with both modes enabled."
            )
        batteries.append(battery)

    expected_names = [entry[0] for entry in modifications_list]
    per_segment = []
    for battery in batteries:
        rows = battery.get("per_modification")
        if not isinstance(rows, list):
            raise RuntimeError("Segment is missing per-modification complementarity data.")
        indexed = {row.get("modification"): row for row in rows if isinstance(row, dict)}
        if set(indexed) != set(expected_names) or len(indexed) != len(expected_names):
            raise RuntimeError("Segment complementarity modifications do not match the configured suite.")
        per_segment.append(indexed)

    clean_rows = [battery.get("clean") for battery in batteries]
    if any(row is None for row in clean_rows):
        raise RuntimeError("Segment is missing clean complementarity pairing data.")
    return {
        "note": (
            "Identification-axis pairing (correct identity within threshold). "
            "cv_correct = cv_only accept; dl_correct = dl_only accept. "
            "recovery = P(SFace right | LBPH wrong); McNemar tests discordant "
            "cells (x = cv-only-right vs y = dl-only-right)."
        ),
        "clean": _sum_pairing_stats(clean_rows),
        "overall_modified": _sum_pairing_stats([battery.get("overall_modified") for battery in batteries]),
        "per_modification": [
            {"modification": name, **_sum_pairing_stats([segment[name] for segment in per_segment])}
            for name in expected_names
        ],
    }


def _fmt_p(result: dict) -> str:
    p_value = result.get("p_exact")
    if p_value is None:
        return "n/a"
    if p_value == 0.0 and result.get("p_exact_log10") is not None:
        return f"< 1e{int(result['p_exact_log10'])}"
    return f"{p_value:.2g}" if p_value >= 1e-4 else f"{p_value:.1e}"


def _battery_markdown(battery: dict) -> list[str]:
    overall = battery["overall_modified"]
    table = overall["table"]
    mcnemar = overall["mcnemar"]
    lines = [
        "## Complementarity Tests A/B (identification axis)",
        "",
        "Same-probe cv_only vs dl_only pairing: w = both right, x = only LBPH right, "
        "y = only SFace right, z = both wrong. Recovery = y/(y+z); McNemar tests x vs y.",
        "",
        f"- Modified probes: {overall['probes']} | w/x/y/z = "
        f"{table['both_right']}/{table['cv_only_right']}/{table['dl_only_right']}/{table['both_wrong']}",
        (
            f"- **Recovery rate** = {overall['recovery_rate_ci95']['percent']:.2f}% "
            f"[{overall['recovery_rate_ci95']['ci95_low_percent']:.2f}-"
            f"{overall['recovery_rate_ci95']['ci95_high_percent']:.2f}] "
            f"({overall['recovery_rate_ci95']['count']}/{overall['recovery_rate_ci95']['trials']})"
            if overall["recovery_rate_ci95"] else "- Recovery rate: n/a (LBPH never wrong)"
        ),
        (
            f"- **McNemar** (x={mcnemar['b']} vs y={mcnemar['c']}): "
            f"p_exact = {_fmt_p(mcnemar)}, chi2_cc = {mcnemar['statistic']:.1f}"
            if not mcnemar["degenerate"] else "- McNemar: degenerate (no discordant probes)"
        ),
        "",
        "| Modification | LBPH wrong | SFace rescues | Recovery | McNemar p |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in battery["per_modification"]:
        pairing = row["table"]
        recovery = row["recovery_rate_ci95"]
        test = row["mcnemar"]
        recovery_text = f"{recovery['percent']:.0f}%" if recovery else "n/a"
        lines.append(
            f"| {row['modification']} | {pairing['dl_only_right'] + pairing['both_wrong']} | "
            f"{pairing['dl_only_right']} | "
            f"{recovery_text} | "
            f"{(_fmt_p(test) if not test['degenerate'] else 'n/a')} |"
        )
    return lines


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
        default="outputs/benchmark/accuracy_ratio_hybrid.json",
        help="Output merged JSON path.",
    )
    parser.add_argument(
        "--output-md",
        default="reports/benchmark/accuracy_ratio_hybrid.md",
        help="Output merged Markdown path.",
    )
    parser.add_argument(
        "--output-battery-csv",
        default="outputs/benchmark/accuracy_ratio_hybrid_probes.csv",
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
    originals_dir = base_payload.get("originals_dir")
    seed = base_payload.get("seed", 42)
    no_face_policy = base_payload.get("no_face_policy", "fallback")
    mod_set = base_payload.get("mod_set", "legacy")
    protocol = base_payload.get("protocol", "transform_sensitivity")
    protocol_label = base_payload.get("protocol_label", "Transform Sensitivity")
    split_manifest = base_payload.get("split_manifest")
    split_manifest_sha = base_payload.get("split_manifest_triples_sha256")
    modifications_list, variant_count = get_modification_set(mod_set)
    is_canonical = (
        (lambda name: name in DL41_DETECTOR_CANONICAL) if mod_set == "dl41"
        else (lambda name: False)
    )
    # Inherited from the segments so the merged headline matches what each
    # segment reported (accuracy_ratio_hybrid --headline-scope). Older segment
    # payloads predate the flag and were always 37-variant headlines.
    headline_scope = base_payload.get("headline_scope", "exclude-canonical")

    total_originals = sum(p["originals"] for p in payloads)
    clean_no_face = sum(p["clean_no_face"] for p in payloads)

    # Rank-1 fields are new (docs/audits/STATE-08-01.md); older segment JSONs
    # from before this change won't have them. Rather than silently reporting
    # a misleading 0%, only compute the merged Rank-1 numbers if every
    # segment being merged actually carries the data.
    have_rank1 = all(
        p.get("clean_rank1_matched") is not None or p.get("clean_rank1_percent") is not None
        for p in payloads
    ) and all(
        all(lv.get("rank1_matched") is not None for me in p["modifications"] for lv in me["levels"])
        for p in payloads
    )

    clean_matched = {m: 0 for m in modes}
    clean_rank1 = {m: 0 for m in modes}
    for p in payloads:
        raw_clean = p.get("clean_matched")
        raw_clean_rank1 = p.get("clean_rank1_matched")
        for m in modes:
            if raw_clean is not None:
                clean_matched[m] += int(raw_clean[m])
            else:
                # Older segment payloads only carry percentages; reconstruct.
                clean_matched[m] += round((p["clean_acceptance_percent"][m] / 100.0) * p["originals"])
            if raw_clean_rank1 is not None:
                clean_rank1[m] += int(raw_clean_rank1[m])
            elif p.get("clean_rank1_percent") is not None:
                clean_rank1[m] += round((p["clean_rank1_percent"][m] / 100.0) * p["originals"])

    # Aggregate modifications. Level keys go through json.dumps, not str():
    # some dl41 levels are tuples (e.g. color_8bit's (3, 3, 2) bit-depths),
    # which round-trip through JSON as lists - str((3, 3, 2)) != str([3, 3, 2])
    # would silently split one modification into two unmatched keys.
    mod_level_data: dict[tuple[str, str], dict] = {}

    for p in payloads:
        for mod_entry in p["modifications"]:
            mod_name = mod_entry["modification"]
            for level_entry in mod_entry["levels"]:
                lvl = level_entry["level"]
                key = (mod_name, json.dumps(lvl))
                if key not in mod_level_data:
                    mod_level_data[key] = {
                        "mod_name": mod_name,
                        "level": lvl,
                        "modified_total": 0,
                        "no_face": 0,
                        "matched": {m: 0 for m in modes},
                        "rank1_matched": {m: 0 for m in modes},
                        "escalated": 0,
                    }
                seg_total = level_entry["modified_total"]
                mod_level_data[key]["modified_total"] += seg_total
                mod_level_data[key]["no_face"] += level_entry["no_face"]
                for m in modes:
                    matched_cnt = level_entry["matched"][m]
                    mod_level_data[key]["matched"][m] += matched_cnt
                    if have_rank1:
                        mod_level_data[key]["rank1_matched"][m] += level_entry["rank1_matched"][m]
                if "cascade" in modes:
                    esc_raw = level_entry.get("escalated")
                    if esc_raw is not None:
                        mod_level_data[key]["escalated"] += int(esc_raw)
                    elif level_entry.get("cascade_escalation_percent") is not None:
                        mod_level_data[key]["escalated"] += round(
                            (level_entry["cascade_escalation_percent"] / 100.0) * seg_total
                        )

    per_mod: list[dict] = []
    for mod_name, fn, levels in modifications_list:
        level_rows = []
        for level in levels:
            key = (mod_name, json.dumps(level))
            ld = mod_level_data.get(key)
            if ld is None:
                raise RuntimeError(
                    f"Segment payloads have no data for modification {mod_name!r} "
                    f"level {level!r} - refusing to merge an incomplete suite."
                )
            tot = ld["modified_total"]
            m_matched = ld["matched"]
            m_rank1 = ld["rank1_matched"]
            esc = ld["escalated"]
            level_rows.append({
                "level": level,
                "modified_total": tot,
                "no_face": ld["no_face"],
                "matched": m_matched,
                "rank1_matched": m_rank1,
                "escalated": esc if "cascade" in modes else None,
                "ar_percent": {m: 100.0 * m_matched[m] / tot for m in modes},
                "rank1_percent": (
                    {m: 100.0 * m_rank1[m] / tot for m in modes} if have_rank1 else None
                ),
                "cascade_escalation_percent": (
                    100.0 * esc / tot if "cascade" in modes else None
                ),
            })
        mod_ar = {
            m: sum(r["ar_percent"][m] for r in level_rows) / len(level_rows) for m in modes
        }
        mod_rank1 = (
            {m: sum(r["rank1_percent"][m] for r in level_rows) / len(level_rows) for m in modes}
            if have_rank1 else None
        )
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
            "rank1_percent": mod_rank1,
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

    # Retention per modification/mode: AR_mod / AR_clean, threshold-gated (see
    # accuracy_ratio_hybrid.py).
    clean_ar_percent = {m: 100.0 * clean_matched[m] / total_originals for m in modes}
    clean_rank1_percent = (
        {m: 100.0 * clean_rank1[m] / total_originals for m in modes} if have_rank1 else None
    )
    for row in per_mod:
        row["retention"] = {
            m: (row["ar_percent"][m] / clean_ar_percent[m]) if clean_ar_percent[m] > 0 else None
            for m in modes
        }

    canonical_rows = [r for r in per_mod if is_canonical(r["modification"])]
    headline_rows = (
        list(per_mod) if headline_scope == "all41"
        else [r for r in per_mod if not is_canonical(r["modification"])]
    )
    canonical_in_headline = headline_scope == "all41" and bool(canonical_rows)

    overall = {
        m: sum(row["ar_percent"][m] for row in headline_rows) / len(headline_rows) for m in modes
    } if headline_rows else {m: 0.0 for m in modes}
    overall_rank1 = (
        {m: sum(row["rank1_percent"][m] for row in headline_rows) / len(headline_rows) for m in modes}
        if have_rank1 and headline_rows else None
    )
    detector_canonical_overall = {
        m: sum(row["ar_percent"][m] for row in canonical_rows) / len(canonical_rows) for m in modes
    } if canonical_rows else None
    detector_canonical_rank1_overall = (
        {m: sum(row["rank1_percent"][m] for row in canonical_rows) / len(canonical_rows) for m in modes}
        if have_rank1 and canonical_rows else None
    )
    total_probes = total_originals * sum(len(r["levels"]) for r in headline_rows)
    overall_ci = {
        m: wilson_interval_percent(
            sum(r["matched"][m] for row in headline_rows for r in row["levels"]),
            total_probes,
        )
        for m in modes
    }
    overall_rank1_ci = (
        {
            m: wilson_interval_percent(
                sum(r["rank1_matched"][m] for row in headline_rows for r in row["levels"]),
                total_probes,
            )
            for m in modes
        } if have_rank1 else None
    )

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
        "protocol": protocol,
        "protocol_label": protocol_label,
        "mod_set": mod_set,
        "split_manifest": split_manifest,
        "split_manifest_triples_sha256": split_manifest_sha,
        "originals_dir": originals_dir,
        "originals": total_originals,
        "total_unsegmented_originals": total_originals,
        "segment_count": len(payloads),
        "segment_index": 0,
        "variant_count": variant_count,
        "headline_scope": headline_scope,
        "headline_variant_count": len(headline_rows),
        "headline_modifications": [r["modification"] for r in headline_rows],
        "detector_canonical_variant_count": len(canonical_rows),
        "modified_probes_per_mode": total_probes,
        "seed": seed,
        "no_face_policy": no_face_policy,
        "clean_no_face": clean_no_face,
        "clean_acceptance_percent": clean_ar_percent,
        "clean_acceptance_ci95": {
            m: wilson_interval_percent(clean_matched[m], total_originals) for m in modes
        },
        "clean_rank1_percent": clean_rank1_percent,
        "clean_rank1_ci95": (
            {m: wilson_interval_percent(clean_rank1[m], total_originals) for m in modes}
            if have_rank1 else None
        ),
        "overall_ar_percent": overall,
        "overall_ar_pooled_ci95": overall_ci,
        "overall_rank1_percent": overall_rank1,
        "overall_rank1_pooled_ci95": overall_rank1_ci,
        "detector_canonical_ar_percent": detector_canonical_overall,
        "detector_canonical_rank1_percent": detector_canonical_rank1_overall,
        "detector_canonical_modifications": [r["modification"] for r in canonical_rows],
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
        # The segment payloads already contain per-probe paired A/B outcomes.
        # Sum those cells first, then recompute recovery and McNemar centrally.
        merged_payload["complementarity_battery"] = _merge_complementarity_battery(
            payloads, modifications_list
        )

    # Save JSON
    out_json_path = Path(args.output_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(merged_payload, indent=2), encoding="utf-8")

    # Build Markdown
    out_md_path = Path(args.output_md)
    lines = [
        f"# {protocol_label} - {mod_set} modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade",
        "",
        f"Protocol: `{protocol}`" + (
            f" | split manifest: `{split_manifest}` (triples sha256 `{split_manifest_sha}`)"
            if split_manifest else " (same-image path - see docs/audits/STATE-08-01.md; "
                                     "NOT to be reported as Accuracy Ratio)"
        ),
        "",
        f"Originals: `{originals_dir or split_manifest}`"
        + (" (manifest probes)" if split_manifest else "")
        + f" ({total_originals} tiles) | "
        f"{variant_count} variants/original "
        + (f"(all {len(headline_rows)} in the headline mean; {len(canonical_rows)} of them "
           f"are detector-canonical and are ALSO broken out separately below)"
           if canonical_in_headline else
           f"({len(headline_rows)} headline + {len(canonical_rows)} detector-canonical)")
        + f" | seed={seed} | no-face policy: `{no_face_policy}`.",
        "",
        "AR = TPIR @ threshold (correct identity AND clears the mode's accept rule). "
        "Rank-1 = threshold-free (did the deciding engine's nearest gallery pick land on "
        "the right identity at all). AR per modification = mean over its levels; overall = "
        + ("mean over ALL 41 modifications, matching the DL team's ar-table.py; the 4 "
           "detector-canonical ones (rot_90/180/270, flip_lr) are included AND broken out "
           "separately below."
           if canonical_in_headline else
           "mean over HEADLINE modifications only (detector-canonical rot_90/180/270/flip_lr "
           "excluded - see their own section below).")
        + " Retention = AR_mod / AR_clean (threshold-gated).",
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
        f"| Clean held-out baseline - TPIR @ threshold | {clean_str} |",
        f"| **Overall AR ({len(headline_rows)} mods, TPIR @ threshold)** | {overall_str} |",
        f"| Pooled AR [95% CI] | {ci_str} |",
    ])
    if have_rank1:
        clean_rank1_str = " | ".join(f"{clean_rank1_percent[m]:.2f}%" for m in modes)
        overall_rank1_str = " | ".join(f"{overall_rank1[m]:.2f}%" for m in modes)
        rank1_ci_str = " | ".join(
            f"{overall_rank1_ci[m]['percent']:.2f}% "
            f"[{overall_rank1_ci[m]['ci95_low_percent']:.2f}-{overall_rank1_ci[m]['ci95_high_percent']:.2f}]"
            for m in modes
        )
        lines.extend([
            f"| Clean held-out baseline - Rank-1 (threshold-free) | {clean_rank1_str} |",
            f"| Overall Rank-1 ({len(headline_rows)} mods, threshold-free) | {overall_rank1_str} |",
            f"| Pooled Rank-1 [95% CI] | {rank1_ci_str} |",
        ])
    lines.extend([
        f"| Mean latency | {lat_str} |",
        "",
        f"## Per modification ({len(headline_rows)} mods) - AR (TPIR @ threshold)",
        "",
        "| Modification | " + " | ".join(modes) + " | retention | winner | escalation |",
        "|---| " + " | ".join("---:" for _ in modes) + " |---:|---|---:|",
    ])

    def _fmt_row(row: dict) -> str:
        mod_name = row["modification"]
        vals = " | ".join(f"{row['ar_percent'][m]:.1f}%" for m in modes)
        ret = " / ".join(
            f"{row['retention'][m]:.2f}" if row['retention'][m] is not None else "n/a" for m in modes
        )
        winner = row.get("winner", "-")
        esc = f"{row['cascade_escalation_percent']:.0f}%" if "cascade_escalation_percent" in row else "-"
        return f"| {mod_name} | {vals} | {ret} | {winner} | {esc} |"

    def _fmt_rank1_row(row: dict) -> str:
        vals = " | ".join(f"{row['rank1_percent'][m]:.1f}%" for m in modes)
        return f"| {row['modification']} | {vals} |"

    for row in headline_rows:
        lines.append(_fmt_row(row))

    if have_rank1:
        lines += [
            "",
            f"## Per modification ({len(headline_rows)} mods) - Rank-1 identification (threshold-free)",
            "",
            "| Modification | " + " | ".join(modes) + " |",
            "|---| " + " | ".join("---:" for _ in modes) + " |",
        ]
        for row in headline_rows:
            lines.append(_fmt_rank1_row(row))

    if canonical_rows:
        lines += [
            "",
            "## Detector-canonical (rot_90/180/270, flip_lr)"
            + (" - INCLUDED in the headline mean above, broken out here as well"
               if canonical_in_headline else
               " - reported separately, NOT averaged into the headline overall-AR mean"),
            "",
            "A recognizer failing on an upside-down face is expected behaviour, and "
            "flip is near-free for a roughly-symmetric embedding, so these four read "
            "differently from the damage-style modifications."
            + (" They are counted in the headline mean (--headline-scope all41, the "
               "default, matching the DL team's ar-table.py) and repeated here so the "
               "headline can be decomposed."
               if canonical_in_headline else
               " Folding them into the headline mean would distort it in both "
               "directions, so they are excluded (--headline-scope exclude-canonical)."),
            "",
        ]
        if detector_canonical_overall:
            dc_str = " | ".join(f"**{detector_canonical_overall[m]:.2f}%**" for m in modes)
            lines += [
                "| Metric | " + " | ".join(modes) + " |",
                "|---| " + " | ".join("---:" for _ in modes) + " |",
                f"| Detector-canonical AR (TPIR @ threshold) | {dc_str} |",
            ]
            if detector_canonical_rank1_overall:
                dc1_str = " | ".join(f"**{detector_canonical_rank1_overall[m]:.2f}%**" for m in modes)
                lines.append(f"| Detector-canonical Rank-1 (threshold-free) | {dc1_str} |")
            lines.append("")
        lines += [
            "| Modification | " + " | ".join(modes) + " | retention | winner | escalation |",
            "|---| " + " | ".join("---:" for _ in modes) + " |---:|---|---:|",
        ]
        for row in canonical_rows:
            lines.append(_fmt_row(row))
        if have_rank1:
            lines += [
                "",
                "| Modification | " + " | ".join(modes) + " |",
                "|---| " + " | ".join("---:" for _ in modes) + " |",
            ]
            for row in canonical_rows:
                lines.append(_fmt_rank1_row(row))

    battery = merged_payload.get("complementarity_battery")
    if battery:
        lines.extend([""] + _battery_markdown(battery))

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
