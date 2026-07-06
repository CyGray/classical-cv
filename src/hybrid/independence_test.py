"""Hybrid (LBPH + SFace cascade) Independence Test: joint N x (N-1) impostor sweep.

One image per identity means every cross-identity comparison is an impostor
pair by construction. This test runs the SAME N x (N-1) sweep the classical and
DL tracks each ran alone, but scores every ordered pair with BOTH engines at
once and then with the gated cascade, so one run answers three questions:

1. **Separation** - does each engine keep impostors far apart? (the classic
   independence question, per engine, with the rank-based k-th-error-pair
   threshold report on each engine's own scale)
2. **Error overlap** - do the two engines fail on the SAME impostor pairs?
   If the false-accept sets barely overlap (observed joint FP rate is close to
   the product of the marginal rates - statistically independent errors), the
   engines are complementary and a cascade can beat either alone.
3. **Cascade FP rate** - with the deployed gate (quality flags, ambiguous
   band, relative margin), how many impostor probes does the fused system
   actually accept?

Pair scoring, per ordered pair (i, j), i != j:

* ``lbph_distance``  - LBPH predict-scale distance from probe i's tile to
  identity j in a temporary model trained on the N selected tiles (same
  radius/neighbors/grid and Tan-Triggs contract as the deployed adapter, so
  ``tau_accept``/``tau_reject`` from ``thresholds.json`` apply directly).
  LBPH false accept: ``distance <= tau_accept``.
* ``sface_cosine`` / ``sface_l2`` - between per-image SFace embeddings.
  SFace false accept: the DL genuine rule (cosine >= 0.363 AND l2 <= 1.128).
* ``cascade_fp`` - the gate runs once per probe i on the full non-self ranking
  (top-1 distance, relative margin, quality probes on the tile); at most one
  pair per probe can be a cascade false accept, mirroring one decision per
  frame in deployment.

Self-comparisons (i == i) are excluded; with one image per identity the LBPH
self-distance is ~0 by memorization and means nothing.

Runs ``--iterations`` times with different per-identity image picks and
aggregates. Writes CSV + JSON under ``outputs/hybrid/independence_test`` and
prints a console report.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path

import cv2 as cv
import numpy as np

from src.classical_faces.detection import create_face_detector
from src.classical_faces.pipeline import SPECS
from src.hybrid.gate import GateThresholds, decide_escalation
from src.hybrid.quality import QualityThresholds, compute_quality
from src.hybrid.recognizer import DEFAULT_THRESHOLDS_PATH, load_thresholds
from src.independence_common import error_pair_report, format_error_pair_report
from src.lbph.preprocess import IMG_SIZE, normalize_face
from src.stats_utils import error_diversity, wilson_interval_percent
from src.sface.recognizer import (
    COSINE_GENUINE_THRESHOLD,
    L2_GENUINE_THRESHOLD,
    SFaceRecognizer,
    detection_to_yunet_row,
)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(path_value: str) -> str:
    candidate = Path(path_value)
    return str(candidate if candidate.is_absolute() else PROJECT_ROOT / candidate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hybrid independence test: joint LBPH + SFace + cascade N x (N-1) impostor sweep."
    )
    parser.add_argument("--dataset-dir", default=root_path("data", "lasalle_db1_processed"),
                        help="Identity folders of pre-cropped face tiles (one is picked per person).")
    parser.add_argument("--output-dir", default=root_path("outputs", "hybrid", "independence_test"))
    parser.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH,
                        help="Gate + quality thresholds (tau_accept/tau_reject/margin_min).")
    parser.add_argument("--iterations", type=int, default=10,
                        help="Independent repeats with different per-person image picks.")
    parser.add_argument("--max-identities", type=int, default=0,
                        help="If > 0, use a seeded random subset of this many identities "
                             "(makes LFW-scale sweeps tractable; 0 = all).")
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--target-far-ppm", type=float, default=10000.0,
                        help="Target FAR for the rank-based threshold report "
                             "(La Salle DB1 spec: 10,000 ppm = 8th error pair of 756).")
    parser.add_argument("--error-pair-rank", type=int, default=None,
                        help="Explicit k-th error pair (overrides --target-far-ppm).")
    return parser.parse_args()


# --------------------------------------------------------------------------- #
# Dataset selection (same protocol as the per-family independence tests)
# --------------------------------------------------------------------------- #
def get_person_dirs(dataset_root: str) -> list[tuple[str, str]]:
    if not os.path.isdir(dataset_root):
        return []
    return [
        (person, os.path.join(dataset_root, person))
        for person in sorted(os.listdir(dataset_root))
        if os.path.isdir(os.path.join(dataset_root, person))
    ]


def select_one_image_per_person(
    person_dirs: list[tuple[str, str]], random_seed: int
) -> dict[str, str]:
    rng = random.Random(random_seed)
    selected: dict[str, str] = {}
    for person, person_path in person_dirs:
        image_files = [
            f for f in sorted(os.listdir(person_path))
            if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
        ]
        if image_files:
            selected[person] = os.path.join(person_path, rng.choice(image_files))
    return selected


# --------------------------------------------------------------------------- #
# One iteration = one joint sweep
# --------------------------------------------------------------------------- #
@dataclass
class ProbeData:
    person: str
    image_path: str
    lbph_face: np.ndarray          # Tan-Triggs-normalized 100x100 (training + probing)
    sface_feature: np.ndarray      # (1, 128) embedding
    quality_gray: np.ndarray       # raw 100x100 gray for the quality probes
    landmarks: np.ndarray | None
    face_px: int


def load_probes(
    selected: dict[str, str],
    detector,
    sface: SFaceRecognizer,
    equalization: str,
) -> list[ProbeData]:
    probes: list[ProbeData] = []
    for person in sorted(selected):
        path = selected[person]
        image_bgr = cv.imread(path)
        if image_bgr is None:
            print(f"[WARN] Unreadable image skipped: {path}")
            continue
        gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        # YuNet for landmarks (SFace alignment + pose probe), tolerant of misses
        # on pre-cropped tiles - deployment behaves the same way.
        landmarks = None
        face_px = min(h, w)
        yunet_row = None
        detections = detector.detect(gray, image_bgr)
        if detections:
            largest = max(detections, key=lambda d: d.area)
            landmarks = largest.landmarks
            bx, by, bw, bh = (int(v) for v in largest.box)
            face_px = max(1, min(bw, bh))
            yunet_row = detection_to_yunet_row(largest.box, landmarks, largest.score)

        if yunet_row is not None:
            feature = sface.feature_from_row(image_bgr, yunet_row)
        else:
            feature = sface.feature_from_crop(image_bgr)

        probes.append(ProbeData(
            person=person,
            image_path=path,
            lbph_face=normalize_face(gray, img_size=IMG_SIZE, equalization=equalization),
            sface_feature=np.asarray(feature, dtype=np.float32).reshape(1, -1),
            quality_gray=cv.resize(gray, (100, 100), interpolation=cv.INTER_AREA),
            landmarks=landmarks,
            face_px=int(face_px),
        ))
    return probes


def run_sweep(
    probes: list[ProbeData],
    sface: SFaceRecognizer,
    gate_thresholds: GateThresholds,
    quality_thresholds: QualityThresholds,
) -> tuple[list[dict], dict]:
    """Score all ordered pairs with both engines + the cascade gate.

    Returns (pair_records, iteration_summary).
    """
    n = len(probes)
    if n < 2:
        raise ValueError("Need at least 2 identities with a usable image.")
    names = [p.person for p in probes]

    # -- LBPH: train once on the N tiles, then predict_collect per probe ------
    recognizer = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train([p.lbph_face for p in probes], np.arange(n, dtype=np.int32))
    lbph_dist = np.full((n, n), np.inf, dtype=np.float64)
    for i, probe in enumerate(probes):
        collector = cv.face.StandardCollector_create()
        recognizer.predict_collect(probe.lbph_face, collector)
        for label, dist in collector.getResults(True):
            label = int(label)
            d = float(dist)
            if d < lbph_dist[i, label]:
                lbph_dist[i, label] = d

    # -- SFace: pairwise cosine / L2 via cv.match (the DL track's exact rule) --
    cos = np.zeros((n, n), dtype=np.float64)
    l2 = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            c, d = sface.match(probes[i].sface_feature, probes[j].sface_feature)
            cos[i, j] = cos[j, i] = c
            l2[i, j] = l2[j, i] = d

    # -- Cascade: one gate decision per probe over the non-self ranking -------
    cascade_fp_pair: dict[int, int] = {}   # probe i -> accepted impostor j
    gate_reasons: dict[str, int] = {}
    escalated_probes = 0
    for i, probe in enumerate(probes):
        others = [j for j in range(n) if j != i]
        ranked = sorted(others, key=lambda j: lbph_dist[i, j])
        d1 = lbph_dist[i, ranked[0]]
        d2 = lbph_dist[i, ranked[1]] if len(ranked) > 1 else d1 + 999.0
        margin = float((d2 - d1) / max(d1, 1e-6))
        quality = compute_quality(
            gray_roi=probe.quality_gray,
            landmarks=probe.landmarks,
            face_px=probe.face_px,
            thresholds=quality_thresholds,
        )
        gate = decide_escalation(
            lbph_distance=float(d1), lbph_margin=margin,
            quality=quality, thresholds=gate_thresholds,
        )
        gate_reasons[gate.reason.split(":")[0]] = (
            gate_reasons.get(gate.reason.split(":")[0], 0) + 1
        )
        if gate.escalate:
            escalated_probes += 1
            j_dl = max(others, key=lambda j: cos[i, j])
            if cos[i, j_dl] >= COSINE_GENUINE_THRESHOLD and l2[i, j_dl] <= L2_GENUINE_THRESHOLD:
                cascade_fp_pair[i] = j_dl
        elif gate.lbph_accept:
            cascade_fp_pair[i] = ranked[0]

    # -- Pair records + engine FP flags ---------------------------------------
    records: list[dict] = []
    fp_lbph = fp_sface = fp_both = fp_cascade = 0
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = float(lbph_dist[i, j])
            c = float(cos[i, j])
            e = float(l2[i, j])
            is_lbph_fp = d <= gate_thresholds.tau_accept
            is_sface_fp = c >= COSINE_GENUINE_THRESHOLD and e <= L2_GENUINE_THRESHOLD
            is_cascade_fp = cascade_fp_pair.get(i) == j
            fp_lbph += is_lbph_fp
            fp_sface += is_sface_fp
            fp_both += is_lbph_fp and is_sface_fp
            fp_cascade += is_cascade_fp
            records.append({
                "query_identity": names[i],
                "candidate_identity": names[j],
                "query_image_path": probes[i].image_path,
                "candidate_image_path": probes[j].image_path,
                "lbph_distance": d,
                "sface_cosine": c,
                "sface_l2": e,
                "lbph_fp": int(is_lbph_fp),
                "sface_fp": int(is_sface_fp),
                "both_fp": int(is_lbph_fp and is_sface_fp),
                "cascade_fp": int(is_cascade_fp),
            })

    comparisons = n * (n - 1)
    p_lbph = fp_lbph / comparisons
    p_sface = fp_sface / comparisons
    expected_both = p_lbph * p_sface * comparisons
    fp_union = fp_lbph + fp_sface - fp_both
    summary = {
        "identities": n,
        "comparisons": comparisons,
        "false_accepts": {
            "lbph": fp_lbph,
            "sface": fp_sface,
            "both": fp_both,
            "union": fp_union,
            "cascade": fp_cascade,
        },
        "fp_percent": {
            "lbph": 100.0 * p_lbph,
            "sface": 100.0 * p_sface,
            "both": 100.0 * fp_both / comparisons,
            "cascade": 100.0 * fp_cascade / comparisons,
        },
        # Every rate with its 95% Wilson interval - 756 comparisons cannot
        # support a bare point estimate.
        "fp_rates_ci95": {
            "lbph": wilson_interval_percent(fp_lbph, comparisons),
            "sface": wilson_interval_percent(fp_sface, comparisons),
            "both": wilson_interval_percent(fp_both, comparisons),
            "cascade": wilson_interval_percent(fp_cascade, comparisons),
        },
        "error_overlap": {
            # If the engines' errors were statistically independent, the joint
            # FP count would be ~expected_both; observed >> expected means the
            # engines fail together (NOT complementary), observed <= expected
            # means the failures are decorrelated.
            "observed_joint_fp": fp_both,
            "expected_joint_fp_if_independent": expected_both,
            "observed_over_expected": (fp_both / expected_both) if expected_both > 0 else None,
            "p_sface_fp_given_lbph_fp": (fp_both / fp_lbph) if fp_lbph else None,
            "p_lbph_fp_given_sface_fp": (fp_both / fp_sface) if fp_sface else None,
        },
        # Standard MCS diversity measures (Kuncheva & Whitaker 2003) on the
        # LBPH-FP x SFace-FP 2x2 table, plus Fisher's exact test of
        # association. Q < 0 / p_negative small = complementary errors;
        # double_fault is the error floor of any fusion of the two engines.
        "diversity": error_diversity(
            fp_both, fp_lbph - fp_both, fp_sface - fp_both, comparisons - fp_union
        ),
        "gate": {
            "escalated_probes": escalated_probes,
            "escalation_percent": 100.0 * escalated_probes / n,
            "reasons": gate_reasons,
        },
        "thresholds": {
            "lbph_tau_accept": gate_thresholds.tau_accept,
            "lbph_tau_reject": gate_thresholds.tau_reject,
            "margin_min": gate_thresholds.margin_min,
            "sface_cosine_genuine": COSINE_GENUINE_THRESHOLD,
            "sface_l2_genuine": L2_GENUINE_THRESHOLD,
        },
    }
    return records, summary


# --------------------------------------------------------------------------- #
# Aggregation + reporting
# --------------------------------------------------------------------------- #
def aggregate_iterations(all_records: list[list[dict]]) -> list[dict]:
    """Mean LBPH distance / SFace cosine / L2 per ordered pair across runs."""
    acc: dict[tuple[str, str], dict] = {}
    for run in all_records:
        for r in run:
            key = (r["query_identity"], r["candidate_identity"])
            slot = acc.setdefault(key, {
                "lbph": [], "cos": [], "l2": [],
                "lbph_fp": 0, "sface_fp": 0, "both_fp": 0, "cascade_fp": 0, "runs": 0,
            })
            slot["lbph"].append(r["lbph_distance"])
            slot["cos"].append(r["sface_cosine"])
            slot["l2"].append(r["sface_l2"])
            slot["lbph_fp"] += r["lbph_fp"]
            slot["sface_fp"] += r["sface_fp"]
            slot["both_fp"] += r["both_fp"]
            slot["cascade_fp"] += r["cascade_fp"]
            slot["runs"] += 1
    out = []
    for (q, c), slot in acc.items():
        out.append({
            "query_identity": q,
            "candidate_identity": c,
            "mean_lbph_distance": float(np.mean(slot["lbph"])),
            "mean_sface_cosine": float(np.mean(slot["cos"])),
            "mean_sface_l2": float(np.mean(slot["l2"])),
            "lbph_fp_runs": slot["lbph_fp"],
            "sface_fp_runs": slot["sface_fp"],
            "both_fp_runs": slot["both_fp"],
            "cascade_fp_runs": slot["cascade_fp"],
            "runs": slot["runs"],
        })
    return out


def save_csv(records: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not records:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    print(f"[SAVE] CSV: {path}")


def main() -> int:
    args = parse_args()
    args.dataset_dir = resolve_path(args.dataset_dir)
    args.output_dir = resolve_path(args.output_dir)

    print(f"[INFO] Hybrid Independence Test (aggregated {args.iterations}x)")
    print(f"[INFO] Dataset: {args.dataset_dir}")

    person_dirs = get_person_dirs(args.dataset_dir)
    if len(person_dirs) < 2:
        print(f"[ERROR] Need >= 2 identity folders under {args.dataset_dir}.")
        return 1
    if args.max_identities and len(person_dirs) > args.max_identities:
        subset_rng = random.Random(args.random_seed)
        person_dirs = sorted(subset_rng.sample(person_dirs, args.max_identities))
        print(f"[INFO] Seeded identity subset: {len(person_dirs)} of the available folders")

    cfg = load_thresholds(resolve_path(args.thresholds_json))
    gate_thresholds = GateThresholds.from_dict(cfg.get("gate"))
    quality_thresholds = QualityThresholds.from_dict(cfg.get("quality"))
    equalization = SPECS["lbph"].default_equalization
    detector = create_face_detector("yunet")
    sface = SFaceRecognizer()

    all_records: list[list[dict]] = []
    iteration_summaries: list[dict] = []
    for it in range(args.iterations):
        print(f"\n[ITERATION {it + 1}/{args.iterations}]")
        selected = select_one_image_per_person(person_dirs, args.random_seed + it)
        probes = load_probes(selected, detector, sface, equalization)
        if len(probes) < 2:
            print("[WARN] Not enough usable probes; iteration skipped.")
            continue
        records, summary = run_sweep(probes, sface, gate_thresholds, quality_thresholds)
        fp = summary["false_accepts"]
        print(f"  N={summary['identities']} comparisons={summary['comparisons']} | "
              f"FP: lbph={fp['lbph']} sface={fp['sface']} both={fp['both']} "
              f"cascade={fp['cascade']} | escalation={summary['gate']['escalation_percent']:.1f}%")
        save_csv(records, os.path.join(args.output_dir, "_raw_runs", f"run_{it + 1}", "comparisons.csv"))
        all_records.append(records)
        iteration_summaries.append(summary)

    if not all_records:
        print("[ERROR] No successful iterations.")
        return 1

    aggregated = aggregate_iterations(all_records)
    comparisons = iteration_summaries[0]["comparisons"]

    def _mean(path_a: str, path_b: str) -> float:
        return float(np.mean([s[path_a][path_b] for s in iteration_summaries]))

    # Rank-based threshold reports on each engine's own impostor scale, from the
    # aggregated mean distances (LBPH: predict distance; SFace: 1 - cosine).
    lbph_pairs = [
        {"raw_distance": r["mean_lbph_distance"],
         "query_identity": r["query_identity"], "candidate_identity": r["candidate_identity"]}
        for r in aggregated
    ]
    sface_pairs = [
        {"raw_distance": 1.0 - r["mean_sface_cosine"],
         "query_identity": r["query_identity"], "candidate_identity": r["candidate_identity"]}
        for r in aggregated
    ]
    lbph_rank_report = error_pair_report(
        lbph_pairs, target_far_ppm=args.target_far_ppm, explicit_rank=args.error_pair_rank)
    sface_rank_report = error_pair_report(
        sface_pairs, target_far_ppm=args.target_far_ppm, explicit_rank=args.error_pair_rank)

    overlap_ratios = [
        s["error_overlap"]["observed_over_expected"]
        for s in iteration_summaries
        if s["error_overlap"]["observed_over_expected"] is not None
    ]

    # Pooled 2x2 across iterations: maximum statistical power for the
    # complementarity test. Caveat (stated in the JSON): iterations reuse the
    # same identities with different image picks, so pooled pairs are not
    # fully independent samples - the per-iteration diversity blocks are the
    # conservative per-sweep view.
    def _sum_fp(key: str) -> int:
        return int(sum(s["false_accepts"][key] for s in iteration_summaries))

    pooled_n = comparisons * len(iteration_summaries)
    pool_lbph, pool_sface = _sum_fp("lbph"), _sum_fp("sface")
    pool_both, pool_cascade = _sum_fp("both"), _sum_fp("cascade")
    pool_union = pool_lbph + pool_sface - pool_both
    pooled = {
        "comparisons": pooled_n,
        "note": "pairs pooled over iterations reuse identities; "
                "see per_iteration for the conservative per-sweep view",
        "fp_rates_ci95": {
            "lbph": wilson_interval_percent(pool_lbph, pooled_n),
            "sface": wilson_interval_percent(pool_sface, pooled_n),
            "both": wilson_interval_percent(pool_both, pooled_n),
            "cascade": wilson_interval_percent(pool_cascade, pooled_n),
        },
        "diversity": error_diversity(
            pool_both, pool_lbph - pool_both, pool_sface - pool_both,
            pooled_n - pool_union,
        ),
    }

    summary = {
        "dataset": {"path": args.dataset_dir, "identities": iteration_summaries[0]["identities"]},
        "iterations": len(iteration_summaries),
        "comparisons_per_iteration": comparisons,
        "mean_fp_percent": {
            "lbph": _mean("fp_percent", "lbph"),
            "sface": _mean("fp_percent", "sface"),
            "both": _mean("fp_percent", "both"),
            "cascade": _mean("fp_percent", "cascade"),
        },
        "mean_escalation_percent": float(np.mean(
            [s["gate"]["escalation_percent"] for s in iteration_summaries])),
        "error_overlap_observed_over_expected_mean": (
            float(np.mean(overlap_ratios)) if overlap_ratios else None
        ),
        "pooled": pooled,
        "thresholds": iteration_summaries[0]["thresholds"],
        "lbph_rank_thresholds": lbph_rank_report,
        "sface_rank_thresholds": sface_rank_report,
        "per_iteration": iteration_summaries,
    }

    save_csv(aggregated, os.path.join(args.output_dir, "comparisons.csv"))
    json_path = os.path.join(args.output_dir, "summary.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[SAVE] JSON summary: {json_path}")

    # -- console report -------------------------------------------------------
    mfp = summary["mean_fp_percent"]
    print("\n" + "=" * 80)
    print("HYBRID INDEPENDENCE TEST REPORT (joint LBPH + SFace + cascade)")
    print("=" * 80)
    print(f"  Identities: {summary['dataset']['identities']}  "
          f"Comparisons/iter: {comparisons}  Iterations: {summary['iterations']}")
    pci = pooled["fp_rates_ci95"]

    def _ci(name: str) -> str:
        v = pci[name]
        return (f"{v['percent']:.4f}% [95% CI {v['ci95_low_percent']:.4f}"
                f"-{v['ci95_high_percent']:.4f}%]")

    print(f"\n[FALSE-ACCEPT RATES (mean over iterations; CI from pooled counts)]")
    print(f"  LBPH alone   (d <= {gate_thresholds.tau_accept}): {mfp['lbph']:.4f}%  pooled {_ci('lbph')}")
    print(f"  SFace alone  (cos >= {COSINE_GENUINE_THRESHOLD}): {mfp['sface']:.4f}%  pooled {_ci('sface')}")
    print(f"  Both engines (same pair)              : {mfp['both']:.4f}%  pooled {_ci('both')}")
    print(f"  Hybrid cascade (gated)                : {mfp['cascade']:.4f}%  pooled {_ci('cascade')}")
    ratio = summary["error_overlap_observed_over_expected_mean"]
    div = pooled["diversity"]
    fisher = div["fisher"]
    print(f"\n[ERROR OVERLAP / COMPLEMENTARITY (pooled over iterations)]")
    if ratio is None:
        print("  No joint false accepts observed - engines never failed together.")
    else:
        print(f"  Observed / expected joint FP (1.0 = statistically independent "
              f"errors): {ratio:.2f}")
    q = div["q_statistic"]
    print(f"  Yule Q = {q:.3f}" if q is not None else "  Yule Q = n/a (a zero cell product)",
          f"| disagreement = {100.0 * div['disagreement']:.4f}%"
          f" | double-fault = {100.0 * div['double_fault']:.4f}%")
    if fisher.get("degenerate"):
        print("  Fisher exact: degenerate margin (an engine had 0 or all FPs) - no test possible")
    else:
        print(f"  Fisher exact: p(errors co-occur) = {fisher['p_positive']:.4g}, "
              f"p(errors avoid each other) = {fisher['p_negative']:.4g}, "
              f"two-sided = {fisher['p_two_sided']:.4g}")
    print(f"  Mean escalation on impostor probes: {summary['mean_escalation_percent']:.1f}%")
    print("\n[LBPH RANK-BASED THRESHOLD]")
    print(format_error_pair_report(lbph_rank_report))
    print("\n[SFACE RANK-BASED THRESHOLD (distance = 1 - cosine)]")
    print(format_error_pair_report(sface_rank_report))
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
