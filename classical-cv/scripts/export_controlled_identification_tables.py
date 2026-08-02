"""Summary + per-modification PNG tables for a controlled-dataset 1-to-N
IDENTIFICATION robustness run (``accuracy_ratio_hybrid.py --split-manifest``),
parameterized by dataset so the SAME script serves both the La Salle DB1 and
AT&T/ORL faces runs (docs/experiments/lasalle-db1-identification/,
docs/experiments/att-faces-identification/).

Two tables per dataset, both full-bleed PNGs via
``export_verification_png_tables.render_full_bleed_table``:

* Summary: Mode x [AR% clean, Rank-1% clean, AR% (41-mod avg), Rank-1% (41-mod
  avg), Escalation %, Latency]. Latency is always "N/A" here — neither
  controlled-dataset run needed an isolated latency measurement (see the
  README), unlike the LFW2 identification run
  (docs/experiments/hybrid-identification/README.md), which had one.
* Per-modification: same 17-family/tier grouping as
  ``export_verification_png_tables.MOD_FAMILIES``, with LBPH / SFace /
  Cascade AR% and cascade escalation% per modification.

Every exported PNG carries the LFW-derived-threshold caveat as an in-image
caption (not just README prose) — captions travel with the PNG into a paper,
prose next to it may not.

``--true-noop-mods``: comma list of dl41 modification names that were
EMPIRICALLY VERIFIED (not assumed) to produce a probe bit-identical to the
clean tile on this dataset's probe-loading path — see the ORL run's README
for why only ``monochrome`` qualifies there (``color_8bit``/``rgb565`` are
NOT no-ops on ORL despite the source being grayscale, because
``load_probes_from_manifest`` reads every probe via plain ``cv.imread`` =
``IMREAD_COLOR``, which promotes an 8-bit grayscale ``.pgm`` to a 3-channel
replicated-BGR array BEFORE modification, so ``_is_color()`` is True and the
color-reduction no-op guard in ``src/benchmark/modifications.py`` never
fires). When given, those rows are flagged in the per-modification table and
a second "adjusted headline" AR (41 mods minus the verified no-ops) is added
to the summary table alongside the raw 41-mod mean.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from export_verification_png_tables import MOD_FAMILIES, render_full_bleed_table  # noqa: E402

CLASSICAL_CV_DIR = SCRIPT_DIR.parent
WORKSPACE_ROOT = CLASSICAL_CV_DIR.parent

MODE_LABELS = {
    "cv_only": "LBPH (cv_only)",
    "dl_only": "SFace (dl_only)",
    "cascade": "Cascade (hybrid)",
}

THRESHOLD_CAPTION = (
    "Scored at LFW-derived thresholds (gate.tau_accept=67.03325520645528, "
    "tau_reject=140.13, SFace l2_genuine=1.0313 -- 10 ppm FAR target on LFW1, "
    "src/hybrid/thresholds.json). Not re-derived for this dataset -- actual "
    "FAR here is unmeasured."
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ar-json", required=True)
    p.add_argument("--dataset-name", required=True, help='e.g. "La Salle DB1" or "AT&T/ORL faces"')
    p.add_argument("--out-dir", required=True)
    p.add_argument("--true-noop-mods", default="",
                    help="Comma list of dl41 modification names empirically verified as "
                         "producing a probe identical to clean on this dataset (see docstring).")
    p.add_argument("--extra-caption", default="",
                    help="Optional dataset-specific caveat appended to the caption "
                         "(e.g. crop-mode or upscale note).")
    p.add_argument("--no-rank1", action="store_true", help="Omit Rank-1 clean and 41-mod avg columns from summary table.")
    p.add_argument("--no-latency", action="store_true", help="Omit Mean latency column from summary table.")
    p.add_argument("--no-caption", action="store_true", help="Omit caption/footnote from summary table PNG.")
    return p.parse_args()


def fmt_pct(v) -> str:
    return f"{v:.2f}%" if v is not None else "N/A"


def full_caption(extra: str) -> str:
    if extra:
        return THRESHOLD_CAPTION + " " + extra
    return THRESHOLD_CAPTION


def main() -> None:
    args = parse_args()
    ar_path = Path(args.ar_json)
    if not ar_path.exists():
        print(f"[ERROR] AR JSON not found at {ar_path}")
        sys.exit(1)
    payload = json.loads(ar_path.read_text(encoding="utf-8"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    true_noops = {m.strip() for m in args.true_noop_mods.split(",") if m.strip()}
    modes = [m for m in ("cv_only", "dl_only", "cascade") if m in payload["overall_ar_percent"]]

    mods = payload["modifications"]
    mean_escalation = (
        sum(m["cascade_escalation_percent"] for m in mods) / len(mods)
        if "cascade" in modes else None
    )

    clean_ar = payload["clean_acceptance_percent"]
    clean_rank1 = payload["clean_rank1_percent"]
    overall_ar = payload["overall_ar_percent"]
    overall_rank1 = payload["overall_rank1_percent"]

    # Adjusted headline: 41-mod mean minus verified true no-op mods (if any).
    adjusted_ar = None
    if true_noops:
        kept = [m for m in mods if m["modification"] not in true_noops]
        adjusted_ar = {
            mode: sum(m["ar_percent"][mode] for m in kept) / len(kept) for mode in modes
        }

    # ----------------------------------------------------------------- #
    # Summary table
    # ----------------------------------------------------------------- #
    headers = ["Mode", "AR % (clean)"]
    widths = [3.0, 2.2]
    if not args.no_rank1:
        headers.append("Rank-1 % (clean)")
        widths.append(2.4)
    headers.append(f"AR % ({len(mods)}-mod avg)")
    widths.append(2.6)
    if not args.no_rank1:
        headers.append(f"Rank-1 % ({len(mods)}-mod avg)")
        widths.append(2.8)
    if adjusted_ar is not None:
        headers.append(f"AR % ({len(mods) - len(true_noops)}-mod adj., excl. verified no-ops)")
        widths.append(3.8)
    headers.append("Escalation %")
    widths.append(2.2)
    if not args.no_latency:
        headers.append("Mean latency (ms)")
        widths.append(2.0)

    rows = []
    for mode in modes:
        esc = f"{mean_escalation:.2f}%" if (mode == "cascade" and mean_escalation is not None) else "-"
        row = [
            MODE_LABELS.get(mode, mode),
            fmt_pct(clean_ar.get(mode)),
        ]
        if not args.no_rank1:
            row.append(fmt_pct(clean_rank1.get(mode)))
        row.append(fmt_pct(overall_ar.get(mode)))
        if not args.no_rank1:
            row.append(fmt_pct(overall_rank1.get(mode)))
        if adjusted_ar is not None:
            row.append(fmt_pct(adjusted_ar.get(mode)))
        row.append(esc)
        if not args.no_latency:
            row.append("N/A")
        rows.append(row)

    summary_extra = "Mean latency: N/A (no isolated single-process latency run for this dataset; see README)."
    if true_noops:
        summary_extra += (
            f" Verified no-op modification(s) on this dataset ({', '.join(sorted(true_noops))}) "
            f"excluded from the adjusted-headline column; see per-modification table/README for detail."
        )
    summary_out = out_dir / "summary_identification_table.png"
    render_full_bleed_table(
        headers, rows, widths, summary_out,
        caption=None if args.no_caption else full_caption(summary_extra),
    )

    # ----------------------------------------------------------------- #
    # Per-modification table (41 rows, grouped by family/tier)
    # ----------------------------------------------------------------- #
    mod_lookup = {m["modification"]: m for m in mods}
    per_mod_headers = ["Modification Family", "Severity Tier & Detail"]
    per_mod_widths = [3.2, 2.6]
    for mode in modes:
        per_mod_headers.append(f"{MODE_LABELS.get(mode, mode)} AR %")
        per_mod_widths.append(2.3)
    if "cascade" in modes:
        per_mod_headers.append("Escalation %")
        per_mod_widths.append(2.0)

    per_mod_rows = []
    family_first_rows = []
    current_row_idx = 0
    for fam_name, variants in MOD_FAMILIES:
        family_first_rows.append(current_row_idx)
        for i, (tech_key, tier_name, tier_detail) in enumerate(variants):
            fam_display = fam_name if i == 0 else ""
            severity_display = f"{tier_name} ({tier_detail})" if tier_detail != tier_name else tier_name
            m_data = mod_lookup.get(tech_key)
            row = [fam_display, severity_display]
            if m_data is None:
                row += ["N/A"] * (len(modes) + (1 if "cascade" in modes else 0))
            else:
                for mode in modes:
                    val = fmt_pct(m_data["ar_percent"].get(mode))
                    if tech_key in true_noops:
                        val += " (no-op)"
                    row.append(val)
                if "cascade" in modes:
                    esc = m_data.get("cascade_escalation_percent")
                    row.append(f"{esc:.1f}%" if esc is not None else "N/A")
            per_mod_rows.append(row)
            current_row_idx += 1

    per_mod_out = out_dir / "per_modification_identification_table.png"
    per_mod_extra = ""
    if true_noops:
        per_mod_extra = (
            f"Rows tagged \"(no-op)\" ({', '.join(sorted(true_noops))}) were empirically "
            f"verified to produce a probe bit-identical to the clean tile on this dataset -- "
            f"see README for why the other color-reduction mods are NOT no-ops here."
        )
    render_full_bleed_table(
        per_mod_headers, per_mod_rows, per_mod_widths, per_mod_out,
        family_boundaries=family_first_rows,
        caption=full_caption(per_mod_extra),
    )

    print(f"[SUCCESS] wrote {summary_out}")
    print(f"[SUCCESS] wrote {per_mod_out}")
    print(f"[INFO] dataset={args.dataset_name} mean cascade escalation across {len(mods)} mods: "
          f"{mean_escalation if mean_escalation is not None else 'n/a'}")
    print(f"[INFO] clean AR: {clean_ar}")
    print(f"[INFO] overall ({len(mods)}-mod) AR: {overall_ar}")
    if adjusted_ar is not None:
        print(f"[INFO] adjusted ({len(mods) - len(true_noops)}-mod) AR: {adjusted_ar}")
    print(f"[INFO] clean Rank-1: {clean_rank1}")
    print(f"[INFO] overall Rank-1: {overall_rank1}")


if __name__ == "__main__":
    main()
