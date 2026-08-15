"""1:1 pairwise verification variant of the LFW2 41-modification robustness test.

``accuracy_ratio_hybrid.py`` scores each probe by 1-to-N identification: find
the nearest of N enrolled gallery identities, then check identity-correct AND
distance-within-threshold. That is why standalone LBPH's headline number
(``1.74% AR``, see docs/experiments/standalone_lbph_robustness/THRESHOLD_CHANGE.md)
looks catastrophic even though the SAME distances, judged pairwise, separate
genuine from impostor at 65-75% accuracy (the published classical baseline
protocol - see docs/experiments/IDENTIFICATION_VS_VERIFICATION.md). A genuine
pair can clear ``tau_accept`` and still lose Rank-1 to a closer impostor
among the other N-1 identities; identification punishes that, verification
does not.

This script isolates the 1:1 question: for each (probe, its own gallery
image) pair - the SAME probes and modifications as the identification
harness, so the two are directly comparable - does the pairwise distance
clear the threshold? A same-seeded impostor pair (probe vs a DIFFERENT
identity's gallery image) is scored alongside it, because "1:1 verification"
without impostor pairs is just Genuine Accept Rate, not accuracy - see
docs/experiments/IDENTIFICATION_VS_VERIFICATION.md Sec 3.1 (3,000 genuine +
3,000 impostor pairs, threshold swept to an EER-optimal cutoff, not the 10
ppm deployment gate). Reporting genuine-only acceptance at the deployment
gate would reproduce the exact identification/verification confound this
script exists to separate out.

Both the genuine and impostor distances come from ONE ``predict_collect()``
call against a throwaway 2-class LBPH model (label 0 = genuine gallery image,
label 1 = impostor gallery image) - the same call ``LBPHAdapter.score()``
uses, so the distance is guaranteed to be on the native ``predict_collect()``
deployment scale (see cv-repo-map Sec 2 on the two non-comparable LBPH
scales) rather than a hand-rolled reimplementation.

Writes ``reports/benchmark/accuracy_ratio_verification.{json,md}`` and a
per-pair CSV (``outputs/benchmark/accuracy_ratio_verification_pairs.csv``) so
thresholds/EER can be re-swept offline without re-running the probes.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2 as cv
import numpy as np

from src.benchmark.accuracy_ratio_hybrid import (
    load_gallery_from_manifest,
    load_probes_from_manifest,
    load_split_manifest,
    tile_sample,
    to_bgr_gray,
)
from src.benchmark.modifications import (
    DL41_DETECTOR_CANONICAL,
    DL41_TIER_MAP,
    get_modification_set,
    stable_rng,
)
from src.classical_faces.detection import create_face_detector
from src.classical_faces.pipeline import SPECS
from src.classical_faces.preprocess import IMG_SIZE, normalize_face
from src.hybrid.recognizer import DEFAULT_THRESHOLDS_PATH, detect_sample, load_thresholds
from src.independence_common import (
    create_lbph_recognizer_for_config,
    lbph_config_metadata,
    resolve_lbph_config,
)
from src.sface.recognizer import SFaceRecognizer, default_sface_model_path
from src.stats_utils import wilson_interval_percent

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINES = ("lbph", "sface")


def _abs(path_value: str) -> str:
    p = Path(path_value)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="1:1 pairwise verification (genuine + impostor pair per probe) "
                    "over the 41-modification LFW2 suite - the verification-protocol "
                    "counterpart to accuracy_ratio_hybrid's 1-to-N identification AR."
    )
    parser.add_argument("--split-manifest", default="data/splits/lfw_ident_split_seed42.json",
                        help="lsface-lfw-ident-split-v1 manifest (gallery/probe-disjoint).")
    parser.add_argument("--engines", default="lbph,sface", help="Comma list from: lbph, sface.")
    parser.add_argument(
        "--lbph-config",
        default=None,
        help="LBPH descriptor config ID/alias (default: active deployed config; "
             "e.g. r3_n8_g6x6 or selected).",
    )
    parser.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH,
                        help="Source of gate.tau_accept (LBPH accept distance). SFace's "
                             "genuine rule uses the module constants in "
                             "src/sface/recognizer.py directly (thresholds.json's "
                             "sface.l2_genuine key is never read at runtime - cv-repo-map "
                             "Sec 3.3) - both are stamped into the output payload either way.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mod-set", choices=["legacy", "dl41"], default="dl41")
    parser.add_argument("--no-face-policy", choices=["fallback", "strict"], default="fallback",
                        help="fallback: score a whole-tile/no-landmark sample when YuNet "
                             "misses. strict: count the probe as a genuine reject and drop "
                             "it from both the GAR and FAR denominators (no probe embedding "
                             "exists to test either pair against).")
    parser.add_argument("--limit-identities", type=int, default=0,
                        help="Debug/smoke-test only: keep the first N sorted-identity gallery "
                             "entries (0 = all 5,749) and intersect probes with that set - same "
                             "prefix rule accuracy_ratio_hybrid uses, so a subset here is a "
                             "strict superset-comparable slice of any larger run.")
    parser.add_argument("--output-json", default="outputs/benchmark/accuracy_ratio_verification.json")
    parser.add_argument("--output-md", default="reports/benchmark/accuracy_ratio_verification.md")
    parser.add_argument("--pairs-csv", default="outputs/benchmark/accuracy_ratio_verification_pairs.csv")
    return parser.parse_args()


def _load_gallery(person_paths: list[tuple[str, str]], detector, equalization: str,
                   sface: SFaceRecognizer | None) -> dict[str, dict]:
    """Preload each enrolled identity's ONE gallery image once: the normalized
    LBPH tile and (if requested) the SFace embedding. Reused across every
    modification/level - the gallery image itself is never modified."""
    out: dict[str, dict] = {}
    for person, path in person_paths:
        img = cv.imread(path)
        if img is None:
            continue
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        sample = detect_sample(detector, image_bgr=img, image_gray=gray, assume_cropped=False)
        if sample is None:
            sample = tile_sample(img, gray)
        entry = {"lbph_face": normalize_face(sample.face_gray, img_size=IMG_SIZE, equalization=equalization)}
        if sface is not None:
            entry["sface_feature"] = (
                sface.feature_from_row(sample.image_bgr, sample.yunet_row)
                if sample.yunet_row is not None
                else sface.feature_from_crop(sample.image_bgr)
            )
        out[person] = entry
    return out


def lbph_pair_distances(genuine_face: np.ndarray, impostor_face: np.ndarray,
                         probe_face: np.ndarray, lbph_config=None) -> tuple[float, float]:
    """(genuine_dist, impostor_dist) from ONE predict_collect() call against a
    throwaway 2-class model - identical codepath to LBPHAdapter.score(), so the
    distances land on the same native predict_collect scale as tau_accept."""
    recognizer = create_lbph_recognizer_for_config(lbph_config)
    recognizer.train([genuine_face, impostor_face], np.array([0, 1], dtype=np.int32))
    collector = cv.face.StandardCollector_create()
    recognizer.predict_collect(probe_face, collector)
    per_label: dict[int, float] = {}
    for label, dist in collector.getResults(True):
        label = int(label)
        dist = float(dist)
        if label not in per_label or dist < per_label[label]:
            per_label[label] = dist
    return per_label.get(0, float("nan")), per_label.get(1, float("nan"))


def cosine_l2(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    l2 = float(np.sqrt(max(2.0 - 2.0 * cos, 0.0)))
    return cos, l2


def equal_error_rate(genuine: list[float], impostor: list[float], lower_is_better: bool) -> dict | None:
    """Sweep every observed score as a candidate threshold; return the point
    where FAR and FRR are closest, vectorized (this repo's earlier per-pair
    Python-loop EER implementation, tar_at_far.equal_error_rate, doesn't scale
    to a 41-modification x 1000s-of-probes sweep)."""
    g = np.asarray(sorted(x for x in genuine if x == x), dtype=np.float64)  # drop NaN
    i = np.asarray(sorted(x for x in impostor if x == x), dtype=np.float64)
    if g.size == 0 or i.size == 0:
        return None
    cands = np.unique(np.concatenate([g, i]))
    if lower_is_better:  # LBPH distance: accept if score <= t
        frr = (g.size - np.searchsorted(g, cands, side="right")) / g.size * 100.0
        far = np.searchsorted(i, cands, side="right") / i.size * 100.0
    else:  # SFace cosine: accept if score >= t
        frr = np.searchsorted(g, cands, side="left") / g.size * 100.0
        far = (i.size - np.searchsorted(i, cands, side="left")) / i.size * 100.0
    idx = int(np.argmin(np.abs(far - frr)))
    return {
        "threshold": float(cands[idx]),
        "far_percent": float(far[idx]),
        "frr_percent": float(frr[idx]),
        "eer_percent": float(0.5 * (far[idx] + frr[idx])),
    }


def accuracy_at_threshold(genuine_accept: list[bool], impostor_accept: list[bool]) -> dict:
    n_g, n_i = len(genuine_accept), len(impostor_accept)
    gar = 100.0 * sum(genuine_accept) / n_g if n_g else None
    far = 100.0 * sum(impostor_accept) / n_i if n_i else None
    accuracy = 0.5 * (gar + (100.0 - far)) if gar is not None and far is not None else None
    return {
        "gar_percent": gar, "far_percent": far, "accuracy_percent": accuracy,
        "genuine_pairs": n_g, "impostor_pairs": n_i,
        "gar_ci95": wilson_interval_percent(sum(genuine_accept), n_g) if n_g else None,
        "far_ci95": wilson_interval_percent(sum(impostor_accept), n_i) if n_i else None,
    }


def main() -> int:
    args = parse_args()
    descriptor_config = resolve_lbph_config(args.lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    for e in engines:
        if e not in ENGINES:
            raise ValueError(f"Unknown engine {e!r}. Valid: {ENGINES}")

    thresholds = load_thresholds(
        _abs(args.thresholds_json),
        expected_lbph_config=descriptor_config,
    )
    tau_accept = float(thresholds["gate"]["tau_accept"])

    manifest = load_split_manifest(_abs(args.split_manifest))
    gallery_pairs = load_gallery_from_manifest(manifest)  # sorted by person, ALL identities
    if args.limit_identities:
        gallery_pairs = gallery_pairs[: args.limit_identities]
    enrolled = [p for p, _ in gallery_pairs]
    enrolled_set = set(enrolled)
    if len(enrolled_set) < 2:
        raise RuntimeError("Need >= 2 enrolled identities to form impostor pairs.")

    probes = [row for row in load_probes_from_manifest(manifest) if row[0] in enrolled_set]
    if not probes:
        raise RuntimeError("No probes intersect the enrolled identity subset.")

    modifications_list, variant_count = get_modification_set(args.mod_set)
    print(f"[INFO] engines={engines} identities={len(enrolled_set)} probes={len(probes)} "
          f"mod_set={args.mod_set} variants/probe={variant_count} tau_accept={tau_accept} "
          f"lbph_config={descriptor_metadata['id']}")

    detector = create_face_detector("yunet")
    equalization = SPECS["lbph"].default_equalization
    sface = SFaceRecognizer(default_sface_model_path()) if "sface" in engines else None

    print(f"[INFO] Preloading {len(enrolled_set)} gallery images...")
    gallery = _load_gallery(gallery_pairs, detector, equalization, sface)
    enrolled = [p for p in enrolled if p in gallery]  # drop unreadable gallery images

    pairs_csv_path = Path(_abs(args.pairs_csv))
    pairs_csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_fields = ["modification", "level", "person", "file", "impostor_person", "no_face",
                  "lbph_genuine_dist", "lbph_impostor_dist",
                  "sface_genuine_cos", "sface_genuine_l2", "sface_impostor_cos", "sface_impostor_l2"]
    csv_file = pairs_csv_path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
    writer.writeheader()

    def process(mod_name: str, level, person: str, fname: str, image_bgr_or_gray: np.ndarray) -> dict:
        image_bgr, image_gray = to_bgr_gray(image_bgr_or_gray)
        sample = detect_sample(detector, image_bgr=image_bgr, image_gray=image_gray, assume_cropped=False)
        no_face = sample is None
        row = {"modification": mod_name, "level": level, "person": person, "file": fname,
               "impostor_person": None, "no_face": no_face,
               "lbph_genuine_dist": None, "lbph_impostor_dist": None,
               "sface_genuine_cos": None, "sface_genuine_l2": None,
               "sface_impostor_cos": None, "sface_impostor_l2": None}
        if no_face and args.no_face_policy == "strict":
            return row  # genuine reject, impostor pair excluded (no probe embedding at all)
        if no_face:
            sample = tile_sample(image_bgr, image_gray)

        rng = stable_rng(args.seed, person, fname, mod_name, level, "impostor")
        candidates = [p for p in enrolled if p != person]
        impostor_person = candidates[int(rng.integers(len(candidates)))]
        row["impostor_person"] = impostor_person

        if "lbph" in engines:
            probe_face = normalize_face(sample.face_gray, img_size=IMG_SIZE, equalization=equalization)
            g_dist, i_dist = lbph_pair_distances(
                gallery[person]["lbph_face"], gallery[impostor_person]["lbph_face"],
                probe_face, descriptor_config)
            row["lbph_genuine_dist"], row["lbph_impostor_dist"] = g_dist, i_dist
        if "sface" in engines:
            probe_feature = (
                sface.feature_from_row(sample.image_bgr, sample.yunet_row)
                if sample.yunet_row is not None else sface.feature_from_crop(sample.image_bgr)
            )
            g_cos, g_l2 = cosine_l2(probe_feature, gallery[person]["sface_feature"])
            i_cos, i_l2 = cosine_l2(probe_feature, gallery[impostor_person]["sface_feature"])
            row["sface_genuine_cos"], row["sface_genuine_l2"] = g_cos, g_l2
            row["sface_impostor_cos"], row["sface_impostor_l2"] = i_cos, i_l2
        return row

    all_rows: list[dict] = []

    print("[INFO] Clean baseline...")
    for person, fname, image in probes:
        row = process("clean", "clean", person, fname, image)
        all_rows.append(row)
        writer.writerow(row)

    for mod_name, fn, levels in modifications_list:
        for level in levels:
            for person, fname, image in probes:
                rng = stable_rng(args.seed, person, fname, mod_name, level)
                modified = fn(image, level, rng)
                row = process(mod_name, level, person, fname, modified)
                all_rows.append(row)
                writer.writerow(row)
        print(f"  {mod_name:<16} done ({len(levels)} level(s))")

    csv_file.close()
    print(f"[OK] Wrote {pairs_csv_path}")

    payload = build_payload(
        all_rows, engines, tau_accept, args, modifications_list, variant_count,
        len(probes), len(enrolled_set), descriptor_config)
    out_json = Path(_abs(args.output_json))
    out_md = Path(_abs(args.output_md))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(to_markdown(payload), encoding="utf-8")
    print(f"[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")
    return 0


def _mod_stats(rows: list[dict], engine: str, tau_accept: float) -> dict:
    """A ``--no-face-policy strict`` row with no detected face has no probe
    embedding at all, so it can't contribute a genuine SCORE (nothing to sweep
    for EER) but per the CLI's own contract it must still count as a genuine
    REJECT in the accept-rate denominator - not silently dropped, which would
    quietly inflate GAR by shrinking N. The impostor side has no pair to test
    at all (no probe embedding exists to compare against anyone), so it is
    excluded from the FAR denominator, matching the CLI help text exactly."""
    lower_is_better = engine == "lbph"
    genuine_scores: list[float] = []
    genuine_accept: list[bool] = []
    impostor_scores: list[float] = []
    impostor_accept: list[bool] = []
    if engine == "lbph":
        for r in rows:
            d = r["lbph_genuine_dist"]
            if d is not None:
                genuine_scores.append(d)
                genuine_accept.append(d <= tau_accept)
            elif r["no_face"]:
                genuine_accept.append(False)
            d = r["lbph_impostor_dist"]
            if d is not None:
                impostor_scores.append(d)
                impostor_accept.append(d <= tau_accept)
    else:
        from src.sface.recognizer import SFaceRecognizer as _S
        for r in rows:
            c, l2 = r["sface_genuine_cos"], r["sface_genuine_l2"]
            if c is not None:
                genuine_scores.append(c)
                genuine_accept.append(_S.is_genuine(c, l2))
            elif r["no_face"]:
                genuine_accept.append(False)
            c, l2 = r["sface_impostor_cos"], r["sface_impostor_l2"]
            if c is not None:
                impostor_scores.append(c)
                impostor_accept.append(_S.is_genuine(c, l2))
    stats = accuracy_at_threshold(genuine_accept, impostor_accept)
    stats["eer"] = equal_error_rate(genuine_scores, impostor_scores, lower_is_better)
    stats["no_face"] = sum(1 for r in rows if r["no_face"])
    return stats


def build_payload(rows, engines, tau_accept, args, modifications_list, variant_count,
                   n_probes, n_identities, lbph_config=None) -> dict:
    clean_rows = [r for r in rows if r["modification"] == "clean"]
    per_mod = []
    for mod_name, _fn, levels in modifications_list:
        mod_rows = [r for r in rows if r["modification"] == mod_name]
        entry = {"modification": mod_name, "category_tier": DL41_TIER_MAP.get(mod_name),
                  "detector_canonical": mod_name in DL41_DETECTOR_CANONICAL, "probes": len(mod_rows)}
        for engine in engines:
            entry[engine] = _mod_stats(mod_rows, engine, tau_accept)
        per_mod.append(entry)

    all_modified = [r for r in rows if r["modification"] != "clean"]
    clean_summary = {e: _mod_stats(clean_rows, e, tau_accept) for e in engines}
    overall_summary = {e: _mod_stats(all_modified, e, tau_accept) for e in engines}

    tiers: dict[str, dict] = {}
    for tier in ("light", "medium", "heavy"):
        tier_rows = [r for r in all_modified if DL41_TIER_MAP.get(r["modification"]) == tier]
        if tier_rows:
            tiers[tier] = {e: _mod_stats(tier_rows, e, tau_accept) for e in engines}

    return {
        "protocol": "pairwise_verification",
        "protocol_note": "genuine pair = probe vs its own split-manifest gallery image; "
                          "impostor pair = SAME modified probe vs a deterministic "
                          "different-identity gallery image (stable_rng token 'impostor').",
        "engines": engines,
        "lbph_config": lbph_config_metadata(lbph_config),
        "tau_accept": tau_accept,
        "tau_accept_source": _abs(args.thresholds_json),
        "sface_genuine_rule": "cosine >= 0.363 and l2 <= 1.0313 (src/sface/recognizer.py "
                               "module constants; thresholds.json sface.l2_genuine is dead - "
                               "cv-repo-map Sec 3.3). No standalone SFace threshold exists in "
                               "this repo (cv-repo-map Sec 3.1); this is the joint-derived value.",
        "split_manifest": args.split_manifest,
        "mod_set": args.mod_set,
        "seed": args.seed,
        "no_face_policy": args.no_face_policy,
        "identities_enrolled": n_identities,
        "probes": n_probes,
        "variant_count": variant_count,
        "clean": clean_summary,
        "overall_modified": overall_summary,
        "tiers": tiers,
        "per_modification": per_mod,
    }


def to_markdown(payload: dict) -> str:
    engines = payload["engines"]
    lines = [
        "# 1:1 Pairwise Verification - LFW2 41-modification suite",
        "",
        f"Protocol: `{payload['protocol']}` | {payload['protocol_note']}",
        "",
        f"Identities enrolled: {payload['identities_enrolled']} | Probes: {payload['probes']} | "
        f"mod_set: `{payload['mod_set']}` | seed: {payload['seed']} | "
        f"no-face policy: `{payload['no_face_policy']}`",
        "",
        f"LBPH descriptor: `{payload['lbph_config']['id']}` "
        f"(radius={payload['lbph_config']['radius']}, "
        f"neighbors={payload['lbph_config']['neighbors']}, "
        f"grid={payload['lbph_config']['grid_x']}x{payload['lbph_config']['grid_y']})",
        "",
        f"LBPH `tau_accept` = **{payload['tau_accept']}** (from `{payload['tau_accept_source']}`).",
        f"SFace genuine rule: {payload['sface_genuine_rule']}",
        "",
        "GAR = Genuine Accept Rate (probe vs its own gallery image, distance/cosine clears "
        "the threshold). FAR = false accept rate on the paired impostor. Accuracy@tau = "
        "(GAR + (100-FAR)) / 2 - the verification-protocol number, comparable to the "
        "published 65-75% classical baseline. EER = threshold swept to the point where "
        "FAR = FRR over this row's pooled genuine+impostor scores (the literature-standard "
        "operating point, distinct from the 10 ppm deployment gate).",
        "",
    ]
    for scope, label in (("clean", "Clean baseline"), ("overall_modified", "Overall (41 mods, TPIR-style)")):
        lines += [f"## {label}", "", "| Engine | GAR | FAR | Accuracy@tau | EER | EER threshold |",
                  "|---|---:|---:|---:|---:|---:|"]
        for e in engines:
            s = payload[scope][e]
            eer = s.get("eer") or {}
            lines.append(
                f"| {e} | {s['gar_percent']:.2f}% | {s['far_percent']:.2f}% | "
                f"**{s['accuracy_percent']:.2f}%** | "
                f"{eer.get('eer_percent', float('nan')):.2f}% | "
                f"{eer.get('threshold', float('nan')):.3f} |"
            )
        lines.append("")

    if payload["tiers"]:
        lines += ["## By tier (modified probes only)", "",
                  "| Tier | Engine | GAR | FAR | Accuracy@tau |", "|---|---|---:|---:|---:|"]
        for tier in ("light", "medium", "heavy"):
            if tier not in payload["tiers"]:
                continue
            for e in engines:
                s = payload["tiers"][tier][e]
                lines.append(f"| {tier} | {e} | {s['gar_percent']:.2f}% | {s['far_percent']:.2f}% | "
                             f"**{s['accuracy_percent']:.2f}%** |")
        lines.append("")

    lines += ["## Per modification", "",
              "| Tier | Modification | " + " | ".join(f"{e} Accuracy@tau" for e in engines) + " |",
              "|---|---|" + "---:|" * len(engines)]
    for row in sorted(payload["per_modification"],
                       key=lambda r: (r["category_tier"] or "", r["modification"])):
        cells = " | ".join(f"{row[e]['accuracy_percent']:.2f}%" for e in engines)
        canon = " *(canonical)*" if row["detector_canonical"] else ""
        lines.append(f"| {row['category_tier']} | {row['modification']}{canon} | {cells} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
