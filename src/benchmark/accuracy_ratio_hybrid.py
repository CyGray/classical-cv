"""41-modification Accuracy Ratio for CV (LBPH), DL (SFace), and the hybrid cascade.

This is the complementarity benchmark: the SAME 41 deterministic (modification,
level) probes from ``src/benchmark/modifications.py`` (identical seeds, so the
probes are bit-identical to the classical ``accuracy_ratio.py`` run) are scored
by three configurations of the one hybrid system:

* ``cv_only``  - LBPH alone (accept = correct identity AND distance <= tau_reject),
* ``dl_only``  - SFace alone (accept = correct identity AND the genuine rule
                 cosine >= 0.363 AND l2 <= 1.128),
* ``cascade``  - the gated hybrid (LBPH fast path, SFace escalation),
* ``parallel`` - both engines on every probe (the cascade's obvious rival: the
                 accuracy ceiling of running everything, at full DL cost).
                 The cascade earns its keep only if it stays within tolerance
                 of parallel while escalating a fraction of the probes.

For each modification the report gives AR side by side plus the cascade's
escalation rate, so the output directly answers: where does CV hold up, where
does DL hold up, and does the gate route the broken frames to the engine that
survives them. A modification is tagged ``cv_stronger`` / ``dl_stronger`` /
``tie`` and the cascade is checked against ``max(cv, dl)`` per modification.

Probes are the held-out originals (``data/split_lasalle/test`` by default), the
modification is applied to the raw gray tile BEFORE any engine-specific
normalization (like a real capture corruption), and YuNet runs on every probe
for landmarks. When YuNet misses a heavily degraded tile, ``--no-face-policy``
decides: ``fallback`` (default) scores the whole tile without landmarks (SFace
resizes the crop; measures recognizer robustness), ``strict`` counts the probe
as failed for every mode (measures the deployed system, detection included).
No-face counts are reported per modification either way.

Writes ``reports/benchmark/accuracy_ratio_hybrid.{json,md}``.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import cv2 as cv
import numpy as np

from src.benchmark.modifications import MODIFICATIONS, VARIANT_COUNT, stable_rng
from src.stats_utils import wilson_interval_percent
from src.classical_faces.datasets import list_image_files
from src.classical_faces.detection import create_face_detector
from src.hybrid.recognizer import (
    DEFAULT_LBPH_LABELS,
    DEFAULT_LBPH_MODEL,
    DEFAULT_SFACE_GALLERY,
    DEFAULT_SFACE_IMPOSTORS,
    DEFAULT_THRESHOLDS_PATH,
    FaceSample,
    HybridRecognizer,
    LBPHAdapter,
    SFaceAdapter,
    detect_sample,
    load_thresholds,
)
from src.hybrid.gate import GateThresholds
from src.hybrid.quality import QualityThresholds

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODES = ("cv_only", "dl_only", "cascade", "parallel")
AR_TIE_TOLERANCE = 2.0  # percentage points before a modification counts as won


def _abs(path_value: str) -> str:
    p = Path(path_value)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Accuracy Ratio over the 41-modification suite: LBPH vs SFace vs hybrid cascade."
    )
    parser.add_argument("--originals-dir", default="data/split_lasalle/test",
                        help="Identity folders of ORIGINAL images (default: held-out test).")
    parser.add_argument("--modes", default=",".join(MODES),
                        help="Comma list from: cv_only, dl_only, cascade, parallel.")
    parser.add_argument("--lbph-model", default=DEFAULT_LBPH_MODEL)
    parser.add_argument("--lbph-labels", default=DEFAULT_LBPH_LABELS)
    parser.add_argument("--sface-gallery", default=DEFAULT_SFACE_GALLERY)
    parser.add_argument("--sface-impostors", default=DEFAULT_SFACE_IMPOSTORS,
                        help="Optional impostor embeddings for FAR annotation (may be absent).")
    parser.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--no-face-policy", choices=["fallback", "strict"], default="fallback",
                        help="fallback: score undetected tiles without landmarks; "
                             "strict: count them as failures (deployed-system view).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Keep at 42 to reproduce the classical accuracy_ratio.py probes.")
    parser.add_argument("--output-json", default="reports/benchmark/accuracy_ratio_hybrid.json")
    parser.add_argument("--output-md", default="reports/benchmark/accuracy_ratio_hybrid.md")
    return parser.parse_args()


def load_originals(base_dir: str) -> list[tuple[str, str, np.ndarray]]:
    """(person, filename, gray_tile) for every original image."""
    out: list[tuple[str, str, np.ndarray]] = []
    for person in sorted(os.listdir(base_dir)):
        pdir = os.path.join(base_dir, person)
        if not os.path.isdir(pdir):
            continue
        for fn in list_image_files(pdir):
            img = cv.imread(os.path.join(pdir, fn))
            if img is None:
                continue
            out.append((person, fn, cv.cvtColor(img, cv.COLOR_BGR2GRAY)))
    return out


def tile_sample(image_bgr: np.ndarray, image_gray: np.ndarray) -> FaceSample:
    """FaceSample for a pre-cropped tile when YuNet found nothing: the whole
    tile is the face, no landmarks (SFace falls back to a plain resize)."""
    h, w = image_gray.shape[:2]
    quality_gray = cv.resize(image_gray, (100, 100), interpolation=cv.INTER_AREA)
    return FaceSample(
        image_bgr=image_bgr,
        yunet_row=None,
        face_gray=image_gray,
        quality_gray=quality_gray,
        landmarks=None,
        face_px=int(min(h, w)),
        score=0.0,
    )


def build_recognizers(args: argparse.Namespace, modes: list[str]) -> dict[str, HybridRecognizer]:
    cfg = load_thresholds(_abs(args.thresholds_json))
    gate_thresholds = GateThresholds.from_dict(cfg.get("gate"))
    quality_thresholds = QualityThresholds.from_dict(cfg.get("quality"))
    lbph = LBPHAdapter(
        model_path=_abs(args.lbph_model),
        labels_path=_abs(args.lbph_labels),
        far_anchors=cfg.get("lbph_far_anchors"),
    )
    sface = None
    if any(m != "cv_only" for m in modes):
        impostors = _abs(args.sface_impostors) if args.sface_impostors else None
        if impostors and not Path(impostors).exists():
            impostors = None
        sface = SFaceAdapter(
            gallery_path=_abs(args.sface_gallery),
            impostors_path=impostors,
        )
    return {
        mode: HybridRecognizer(
            lbph=lbph,
            sface=sface,
            gate_thresholds=gate_thresholds,
            quality_thresholds=quality_thresholds,
            mode=mode,
        )
        for mode in modes
    }


def score_probe(
    recognizers: dict[str, HybridRecognizer],
    sample: FaceSample | None,
    person: str,
) -> dict[str, dict]:
    """Run every mode on one probe; ``sample=None`` means strict no-face fail."""
    out: dict[str, dict] = {}
    for mode, hybrid in recognizers.items():
        if sample is None:
            out[mode] = {"matched": False, "escalated": False, "latency_ms": 0.0}
            continue
        t0 = time.perf_counter()
        decision = hybrid.predict(sample)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        out[mode] = {
            "matched": decision.name == person,
            "escalated": bool(decision.escalated),
            "latency_ms": latency_ms,
        }
    return out


def main() -> int:
    args = parse_args()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in MODES:
            raise ValueError(f"Unknown mode {m!r}. Valid: {MODES}")

    originals = load_originals(_abs(args.originals_dir))
    if not originals:
        raise RuntimeError(
            f"No original images found under {args.originals_dir}. "
            "Expected identity folders of pre-cropped tiles (data/split_lasalle/test)."
        )
    print(f"[INFO] originals={len(originals)} -> modified probes per mode = "
          f"{len(originals)} x {VARIANT_COUNT} = {len(originals) * VARIANT_COUNT}")

    recognizers = build_recognizers(args, modes)
    detector = create_face_detector("yunet")

    def probe(image_gray: np.ndarray, person: str) -> tuple[dict[str, dict], bool]:
        image_bgr = cv.cvtColor(image_gray, cv.COLOR_GRAY2BGR)
        sample = detect_sample(
            detector, image_bgr=image_bgr, image_gray=image_gray, assume_cropped=True
        )
        no_face = sample is None
        if no_face and args.no_face_policy == "fallback":
            sample = tile_sample(image_bgr, image_gray)
        return score_probe(recognizers, sample, person), no_face

    # Clean (unmodified) acceptance per mode, for the robustness-loss baseline.
    clean_matched = {m: 0 for m in modes}
    clean_no_face = 0
    for person, _, gray in originals:
        scores, no_face = probe(gray, person)
        clean_no_face += no_face
        for m in modes:
            clean_matched[m] += scores[m]["matched"]

    per_mod: list[dict] = []
    latencies: dict[str, list[float]] = {m: [] for m in modes}
    for mod_name, fn, levels in MODIFICATIONS:
        level_rows = []
        for level in levels:
            matched = {m: 0 for m in modes}
            escalated = 0
            no_face_count = 0
            for person, fname, gray in originals:
                rng = stable_rng(args.seed, person, fname, mod_name, level)
                modified = fn(gray, level, rng)
                scores, no_face = probe(modified, person)
                no_face_count += no_face
                for m in modes:
                    matched[m] += scores[m]["matched"]
                    latencies[m].append(scores[m]["latency_ms"])
                if "cascade" in scores:
                    escalated += scores["cascade"]["escalated"]
            level_rows.append({
                "level": level,
                "modified_total": len(originals),
                "no_face": no_face_count,
                "matched": matched,
                "ar_percent": {m: 100.0 * matched[m] / len(originals) for m in modes},
                "cascade_escalation_percent": (
                    100.0 * escalated / len(originals) if "cascade" in modes else None
                ),
            })
        mod_ar = {
            m: sum(r["ar_percent"][m] for r in level_rows) / len(level_rows) for m in modes
        }
        # Pooled binomial view of the same modification (matched over all its
        # level probes), so each AR carries a Wilson 95% CI.
        mod_probes = len(level_rows) * len(originals)
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
        if "cascade" in modes and "parallel" in modes:
            row["cascade_vs_parallel_points"] = mod_ar["cascade"] - mod_ar["parallel"]
        per_mod.append(row)
        summary = "  ".join(f"{m}={mod_ar[m]:6.2f}%" for m in modes)
        print(f"  {mod_name:<16} {summary}")

    overall = {
        m: sum(row["ar_percent"][m] for row in per_mod) / len(per_mod) for m in modes
    }
    # Pooled over ALL 41-variant probes: one binomial per mode -> Wilson CI.
    total_probes = len(originals) * VARIANT_COUNT
    overall_ci = {
        m: wilson_interval_percent(
            sum(r["matched"][m] for row in per_mod for r in row["levels"]),
            total_probes,
        )
        for m in modes
    }
    payload = {
        "originals_dir": args.originals_dir,
        "originals": len(originals),
        "variant_count": VARIANT_COUNT,
        "modified_probes_per_mode": total_probes,
        "seed": args.seed,
        "no_face_policy": args.no_face_policy,
        "clean_no_face": clean_no_face,
        "clean_acceptance_percent": {
            m: 100.0 * clean_matched[m] / len(originals) for m in modes
        },
        "clean_acceptance_ci95": {
            m: wilson_interval_percent(clean_matched[m], len(originals)) for m in modes
        },
        "overall_ar_percent": overall,
        "overall_ar_pooled_ci95": overall_ci,
        "mean_latency_ms": {
            m: (float(np.mean(latencies[m])) if latencies[m] else 0.0) for m in modes
        },
        "latency_ms_percentiles": {
            m: (
                {
                    "median": float(np.percentile(latencies[m], 50)),
                    "p95": float(np.percentile(latencies[m], 95)),
                }
                if latencies[m] else {"median": 0.0, "p95": 0.0}
            )
            for m in modes
        },
        "modifications": per_mod,
    }
    if "cv_only" in modes and "dl_only" in modes:
        payload["complementarity"] = {
            "cv_stronger": [r["modification"] for r in per_mod if r.get("winner") == "cv_stronger"],
            "dl_stronger": [r["modification"] for r in per_mod if r.get("winner") == "dl_stronger"],
            "tie": [r["modification"] for r in per_mod if r.get("winner") == "tie"],
            "tie_tolerance_points": AR_TIE_TOLERANCE,
        }
        if "cascade" in modes:
            payload["complementarity"]["cascade_within_2pts_of_best"] = sum(
                1 for r in per_mod if r["cascade_vs_best_points"] >= -AR_TIE_TOLERANCE
            )
    if "cascade" in modes and "parallel" in modes:
        payload.setdefault("complementarity", {})["cascade_vs_parallel"] = {
            "overall_points": overall["cascade"] - overall["parallel"],
            "within_tolerance_mods": sum(
                1 for r in per_mod
                if r["cascade_vs_parallel_points"] >= -AR_TIE_TOLERANCE
            ),
            "total_mods": len(per_mod),
        }

    out_json = Path(_abs(args.output_json))
    out_md = Path(_abs(args.output_md))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(to_markdown(payload, modes), encoding="utf-8")

    print("\n[RESULT] overall AR: " + "  ".join(f"{m}={overall[m]:.2f}%" for m in modes))
    comp = payload.get("complementarity", {})
    if "cv_stronger" in comp:
        print(f"[COMPLEMENTARITY] cv_stronger={comp['cv_stronger']} "
              f"dl_stronger={comp['dl_stronger']} tie={len(comp['tie'])} mods")
    if "cascade_vs_parallel" in comp:
        cvp = comp["cascade_vs_parallel"]
        print(f"[CASCADE vs PARALLEL] overall {cvp['overall_points']:+.2f} pts; "
              f"within tolerance on {cvp['within_tolerance_mods']}/{cvp['total_mods']} mods")
    print(f"[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")
    return 0


def to_markdown(payload: dict, modes: list[str]) -> str:
    lines = [
        "# Accuracy Ratio - 41-modification suite: CV (LBPH) vs DL (SFace) vs hybrid cascade",
        "",
        f"Originals: `{payload['originals_dir']}` ({payload['originals']} tiles) | "
        f"{payload['variant_count']} variants/original | seed={payload['seed']} | "
        f"no-face policy: `{payload['no_face_policy']}`.",
        "",
        "Same probes as `accuracy_ratio.py` (identical per-image seeds). "
        "AR per modification = mean over its levels; overall = mean over modifications.",
        "",
        "| Metric | " + " | ".join(modes) + " |",
        "|---|" + "---:|" * len(modes),
        "| Clean acceptance | " + " | ".join(
            f"{payload['clean_acceptance_percent'][m]:.2f}%" for m in modes) + " |",
        "| **Overall AR** | " + " | ".join(
            f"**{payload['overall_ar_percent'][m]:.2f}%**" for m in modes) + " |",
        "| Pooled AR [95% CI] | " + " | ".join(
            "{percent:.2f}% [{ci95_low_percent:.2f}-{ci95_high_percent:.2f}]".format(
                **payload["overall_ar_pooled_ci95"][m]) for m in modes) + " |",
        "| Mean latency | " + " | ".join(
            f"{payload['mean_latency_ms'][m]:.2f} ms" for m in modes) + " |",
        "| Latency median / p95 | " + " | ".join(
            "{median:.2f} / {p95:.2f} ms".format(
                **payload["latency_ms_percentiles"][m]) for m in modes) + " |",
        "",
        "## Per modification",
        "",
    ]
    header = "| Modification | " + " | ".join(modes) + " |"
    sep = "|---|" + "---:|" * len(modes)
    extra_cols = ""
    if "cv_only" in modes and "dl_only" in modes:
        header = header[:-2] + " | winner |"
        sep += "---|"
        extra_cols = "winner"
    if "cascade" in modes:
        header = header[:-2] + " | escalation |"
        sep += "---:|"
    lines += [header, sep]
    for r in payload["modifications"]:
        cells = " | ".join(f"{r['ar_percent'][m]:.1f}%" for m in modes)
        row = f"| {r['modification']} | {cells} |"
        if extra_cols:
            row = row[:-2] + f" | {r.get('winner', '')} |"
        if "cascade" in modes:
            row = row[:-2] + f" | {r.get('cascade_escalation_percent', 0.0):.0f}% |"
        lines.append(row)
    lines.append("")

    comp = payload.get("complementarity")
    if comp:
        lines += ["## Complementarity summary", ""]
        if "cv_stronger" in comp:
            tol = comp["tie_tolerance_points"]
            lines += [
                f"- CV stronger (> {tol:.0f} pts): "
                + (", ".join(comp["cv_stronger"]) or "none"),
                f"- DL stronger (> {tol:.0f} pts): "
                + (", ".join(comp["dl_stronger"]) or "none"),
                f"- Ties: {len(comp['tie'])} modifications",
            ]
            if "cascade_within_2pts_of_best" in comp:
                lines.append(
                    f"- Cascade within {tol:.0f} pts of the better "
                    f"engine on {comp['cascade_within_2pts_of_best']} / "
                    f"{len(payload['modifications'])} modifications"
                )
        if "cascade_vs_parallel" in comp:
            cvp = comp["cascade_vs_parallel"]
            lines.append(
                f"- Cascade vs parallel (run-both ceiling): "
                f"{cvp['overall_points']:+.2f} pts overall, within tolerance on "
                f"{cvp['within_tolerance_mods']} / {cvp['total_mods']} modifications"
            )
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
