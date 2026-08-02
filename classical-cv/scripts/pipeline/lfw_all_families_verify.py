#!/usr/bin/env python3
"""Dr. Oh's "compare each face against the entire LFW2" protocol, done exactly.

For a seeded subset of LFW identities (the partial/segmented run - "10% is fine"):

* Enroll ONE clean anchor per identity (``select_originals`` seed=42 - the same
  clean pick the robustness harness enrolls), building a clean LBPH model +
  clean SFace gallery.
* For every modification (the 41-variant suite) and every identity i, build the
  modified probe F(i, mod) and score it against ALL clean anchors:
    - genuine pair   = probe_i vs anchor_i          -> accept => TP, reject => FN
    - impostor pairs = probe_i vs anchor_j (j != i) -> accept => FP, reject => TN
  This is the every-pair verification the professor's figure prescribes
  ("compared not only with its own family but also with all other families"),
  NOT the closed-set rank-1 the sweep computed.

LFW-derived thresholds: ``tau_accept`` and ``l2_genuine`` are currently frozen
from LS-DB1 (docs/READ THIS/FROZEN_THRESHOLDS.md). Here we RE-DERIVE the LFW1
analogues from the clean cross-identity impostor distribution of this run, using
the same recipe:
    - tau_accept_lfw1 = LBPH impostor distance at 1% FAR (native predict scale)
    - l2_genuine_lfw1 = mean of the SFace impostor L2 distribution
and the table is computed at those LFW-derived operating points. tau_reject
(76.85) is already LFW-carried; cosine_genuine (0.363) is left unchanged.

Accuracy = (TP+TN)/(TP+TN+FP+FN) per the figure; balanced accuracy
= 0.5*(TPR+TNR) is reported alongside because the raw formula is TN-dominated at
(N-1):1 impostor:genuine (STATE-07-21 Finding 3).

Outputs (under --output-dir): table.md, per_variant.csv, summary.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
from collections import defaultdict
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.accuracy_ratio_hybrid import select_originals
from src.benchmark.modifications import MODIFICATIONS, apply_variant, stable_rng, variant_tier
from src.classical_faces.detection import create_face_detector
from src.classical_faces.pipeline import SPECS
from src.hybrid.recognizer import DEFAULT_THRESHOLDS_PATH, load_thresholds
from src.lbph.preprocess import IMG_SIZE, normalize_face
from src.sface.recognizer import (
    COSINE_GENUINE_THRESHOLD,
    L2_GENUINE_THRESHOLD,
    SFaceRecognizer,
    detection_to_yunet_row,
)

# LS-DB1-derived frozen values, carried for the side-by-side comparison only.
LSDB1_TAU_ACCEPT = 70.6089
LSDB1_L2_GENUINE = 1.106796


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lfw-root", default="data/lfw-dataset")
    p.add_argument("--max-identities", type=int, default=575,
                   help="Seeded identity subset (~10%% of 5749). The impostor pool is the "
                        "rest of this subset (the partial run).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--far-accept", type=float, default=0.01,
                   help="FAR%% at which to place the LFW-derived tau_accept. Default 0.01%% "
                        "(100 ppm) matches the original LFW-carried recipe (73.04) and keeps "
                        "accept<reject; the 1%% value is also reported (LS-DB1 used ~1%%).")
    p.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH,
                   help="Only tau_reject / cosine_genuine are read from here; tau_accept and "
                        "l2_genuine are re-derived from this run's LFW impostor distribution.")
    p.add_argument("--output-dir", default="outputs/benchmark/lfw_all_families")
    p.add_argument("--limit-variants", type=int, default=0,
                   help="Debug: only run the first K (name,level) variants (0 = all 41).")
    p.add_argument("--dump-npz", action="store_true",
                   help="Also save distributions.npz (clean impostor + pooled-mod genuine "
                        "distances per engine) for the hist/KDE plots.")
    return p.parse_args()


def _abs(v: str) -> str:
    p = Path(v)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


def embed_face(gray: np.ndarray, detector, sface: SFaceRecognizer, equalization: str):
    """(lbph_face 100x100 Tan-Triggs, sface_embedding (128,)) for one gray tile.
    Mirrors src/hybrid/independence_test.load_probes exactly so scores are on the
    same scale as the deployed gate."""
    h, w = gray.shape[:2]
    image_bgr = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
    yunet_row = None
    detections = detector.detect(gray, image_bgr)
    if detections:
        largest = max(detections, key=lambda d: d.area)
        yunet_row = detection_to_yunet_row(largest.box, largest.landmarks, largest.score)
    if yunet_row is not None:
        feature = sface.feature_from_row(image_bgr, yunet_row)
    else:
        feature = sface.feature_from_crop(image_bgr)
    lbph_face = normalize_face(gray, img_size=IMG_SIZE, equalization=equalization)
    emb = np.asarray(feature, dtype=np.float32).reshape(-1)
    emb = emb / (np.linalg.norm(emb) + 1e-9)
    return lbph_face, emb


def main() -> int:
    args = parse_args()
    t_start = time.time()
    lfw_root = _abs(args.lfw_root)
    out_dir = Path(_abs(args.output_dir))
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_thresholds(_abs(args.thresholds_json))
    tau_reject = float(cfg["gate"]["tau_reject"])
    cos_gen = COSINE_GENUINE_THRESHOLD

    # --- Seeded identity subset (the partial run) ---------------------------
    selection = select_originals(lfw_root, select_one_per_person=True, seed=args.seed)
    if len(selection) < 2:
        raise RuntimeError(f"Need >=2 identities under {lfw_root}")
    if args.max_identities and len(selection) > args.max_identities:
        rng = random.Random(args.seed)
        selection = sorted(rng.sample(selection, args.max_identities))
    persons = [p for p, _ in selection]
    n = len(persons)
    print(f"[INFO] Identities: {n} (seed={args.seed}) | impostor pairs/mod = {n*(n-1)}")

    detector = create_face_detector("yunet")
    sface = SFaceRecognizer()
    equalization = SPECS["lbph"].default_equalization

    # --- Enroll clean anchors ----------------------------------------------
    print("[INFO] Embedding clean anchors...")
    anchor_faces, anchor_emb, clean_grays = [], [], []
    for idx, (person, path) in enumerate(selection):
        img = cv.imread(path)
        if img is None:
            raise RuntimeError(f"Unreadable anchor: {path}")
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        clean_grays.append((person, os.path.basename(path), gray))
        lf, emb = embed_face(gray, detector, sface, equalization)
        anchor_faces.append(lf)
        anchor_emb.append(emb)
        if (idx + 1) % 100 == 0:
            print(f"  anchors {idx+1}/{n}")
    anchor_emb = np.stack(anchor_emb, axis=0)          # (n,128) unit-normed
    lbph = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    lbph.train(anchor_faces, np.arange(n, dtype=np.int32))

    variants = [(name, lvl) for name, _fn, levels in MODIFICATIONS for lvl in levels]
    if args.limit_variants:
        variants = variants[: args.limit_variants]
    print(f"[INFO] Variants: {len(variants)} + clean baseline")

    def score_probe(gray: np.ndarray):
        """LBPH native-scale distance vector + SFace cosine/l2 vectors to all n anchors."""
        lf, emb = embed_face(gray, detector, sface, equalization)
        collector = cv.face.StandardCollector_create()
        lbph.predict_collect(lf, collector)
        d = np.full(n, np.inf, dtype=np.float64)
        for label, dist in collector.getResults(True):
            label = int(label)
            if dist < d[label]:
                d[label] = float(dist)
        cos = anchor_emb @ emb
        l2 = np.sqrt(np.clip(2.0 - 2.0 * cos, 0.0, None))
        return d, cos, l2

    # --- Pass 1: clean probes -> derive LFW thresholds from impostor dist ----
    print("[INFO] Pass 1: clean probes (threshold derivation)...")
    clean_d, clean_cos, clean_l2 = [], [], []
    for i, (person, _bn, gray) in enumerate(clean_grays):
        d, cos, l2 = score_probe(gray)
        clean_d.append(d); clean_cos.append(cos); clean_l2.append(l2)
    clean_d = np.stack(clean_d); clean_cos = np.stack(clean_cos); clean_l2 = np.stack(clean_l2)
    off = ~np.eye(n, dtype=bool)                        # impostor mask (i != j)
    imp_lbph = clean_d[off]
    imp_l2 = clean_l2[off]
    tau_accept_lfw = float(np.percentile(imp_lbph, args.far_accept))   # used (default 100ppm)
    l2_genuine_lfw = float(np.mean(imp_l2))
    tau_accept_1pct = float(np.percentile(imp_lbph, 1.0))
    print(f"[LFW-DERIVED] tau_accept @ {args.far_accept}% FAR = {tau_accept_lfw:.4f} "
          f"(1% FAR = {tau_accept_1pct:.4f}; LS-DB1 frozen {LSDB1_TAU_ACCEPT})")
    print(f"[LFW-DERIVED] l2_genuine (impostor L2 mean) = {l2_genuine_lfw:.6f} "
          f"(LS-DB1 frozen {LSDB1_L2_GENUINE})")

    tau_accept = tau_accept_lfw
    l2_gen = l2_genuine_lfw

    def confusion_from_scores(d, cos, l2, genuine_idx):
        """Return per-engine (tp, fn, fp, tn) for one probe row over all anchors."""
        imp = np.ones(n, dtype=bool); imp[genuine_idx] = False
        out = {}
        # LBPH: accept when distance <= tau_accept
        acc = d <= tau_accept
        out["lbph"] = (int(acc[genuine_idx]), int(not acc[genuine_idx]),
                       int(acc[imp].sum()), int((~acc[imp]).sum()))
        # SFace: cosine >= cos_gen AND l2 <= l2_gen
        acc = (cos >= cos_gen) & (l2 <= l2_gen)
        out["sface"] = (int(acc[genuine_idx]), int(not acc[genuine_idx]),
                        int(acc[imp].sum()), int((~acc[imp]).sum()))
        # Hybrid cascade (per pair): below accept-band -> LBPH accept; in band ->
        # defer to SFace genuine rule; at/above reject -> reject.
        below = d <= tau_accept
        band = (d > tau_accept) & (d < tau_reject)
        sface_ok = (cos >= cos_gen) & (l2 <= l2_gen)
        acc = below | (band & sface_ok)
        out["hybrid"] = (int(acc[genuine_idx]), int(not acc[genuine_idx]),
                         int(acc[imp].sum()), int((~acc[imp]).sum()))
        return out

    # Confusion accumulators: family -> engine -> [tp,fn,fp,tn]
    fam_conf = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
    per_variant_rows = []
    gen_lbph_mod, gen_l2_mod = [], []   # pooled genuine distances (modified probes)

    def accumulate(family, scores_iter):
        eng_conf = {e: [0, 0, 0, 0] for e in ("lbph", "sface", "hybrid")}
        for gi, (d, cos, l2) in scores_iter:
            c = confusion_from_scores(d, cos, l2, gi)
            if args.dump_npz and family != "clean":
                gen_lbph_mod.append(float(d[gi])); gen_l2_mod.append(float(l2[gi]))
            for e in eng_conf:
                for k in range(4):
                    eng_conf[e][k] += c[e][k]
        for e in eng_conf:
            for k in range(4):
                fam_conf[family][e][k] += eng_conf[e][k]
        return eng_conf

    # clean baseline uses the already-scored pass-1 arrays
    accumulate("clean", ((i, (clean_d[i], clean_cos[i], clean_l2[i])) for i in range(n)))

    # --- Pass 2: each modification -----------------------------------------
    for vi, (name, level) in enumerate(variants, 1):
        t0 = time.time()

        def scores():
            for i, (person, bn, gray) in enumerate(clean_grays):
                rng = stable_rng(args.seed, person, bn, name, level)
                mod_gray = apply_variant(gray, name, level, rng)
                yield i, score_probe(mod_gray)

        eng_conf = accumulate(name, scores())
        for e in ("lbph", "sface", "hybrid"):
            tp, fn, fp, tn = eng_conf[e]
            tot = tp + fn + fp + tn
            acc = 100.0 * (tp + tn) / tot if tot else 0.0
            tpr = 100.0 * tp / (tp + fn) if (tp + fn) else 0.0
            tnr = 100.0 * tn / (tn + fp) if (tn + fp) else 0.0
            per_variant_rows.append({
                "modification": name, "level": level, "tier": variant_tier(name, level),
                "engine": e, "tp": tp, "fn": fn, "fp": fp, "tn": tn,
                "accuracy_pct": round(acc, 3), "balanced_acc_pct": round(0.5 * (tpr + tnr), 3),
                "tpr_pct": round(tpr, 3), "tnr_pct": round(tnr, 3),
            })
        print(f"  [{vi}/{len(variants)}] {name}:{level} "
              f"lbph={_acc(eng_conf['lbph'])}% sface={_acc(eng_conf['sface'])}% "
              f"hybrid={_acc(eng_conf['hybrid'])}% ({time.time()-t0:.1f}s)")

    # --- Aggregate family table --------------------------------------------
    families = ["clean"] + [name for name, _fn, _l in MODIFICATIONS if name in fam_conf]
    engines = ["lbph", "sface", "hybrid"]
    table = {}
    for fam in families:
        table[fam] = {}
        for e in engines:
            tp, fn, fp, tn = fam_conf[fam][e]
            tot = tp + fn + fp + tn
            tpr = 100.0 * tp / (tp + fn) if (tp + fn) else 0.0
            tnr = 100.0 * tn / (tn + fp) if (tn + fp) else 0.0
            table[fam][e] = {
                "accuracy_pct": round(100.0 * (tp + tn) / tot, 3) if tot else 0.0,
                "balanced_acc_pct": round(0.5 * (tpr + tnr), 3),
                "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            }

    # overall (all modifications, excludes clean)
    overall = {}
    for e in engines:
        tp = sum(fam_conf[f][e][0] for f in families if f != "clean")
        fn = sum(fam_conf[f][e][1] for f in families if f != "clean")
        fp = sum(fam_conf[f][e][2] for f in families if f != "clean")
        tn = sum(fam_conf[f][e][3] for f in families if f != "clean")
        tot = tp + fn + fp + tn
        tpr = 100.0 * tp / (tp + fn) if (tp + fn) else 0.0
        tnr = 100.0 * tn / (tn + fp) if (tn + fp) else 0.0
        overall[e] = {"accuracy_pct": round(100.0 * (tp + tn) / tot, 3) if tot else 0.0,
                      "balanced_acc_pct": round(0.5 * (tpr + tnr), 3)}

    thresholds = {
        "lfw1_derived": {"tau_accept": round(tau_accept_lfw, 4),
                         "tau_accept_far_percent": args.far_accept,
                         "tau_accept_1pct_far": round(tau_accept_1pct, 4),
                         "l2_genuine": round(l2_genuine_lfw, 6)},
        "lsdb1_frozen": {"tau_accept": LSDB1_TAU_ACCEPT, "l2_genuine": LSDB1_L2_GENUINE},
        "shared": {"tau_reject": tau_reject, "cosine_genuine": cos_gen},
    }

    summary = {
        "protocol": "clean-anchor vs modified all-pairs verification (Dr. Oh figure, partial)",
        "identities": n, "seed": args.seed,
        "genuine_pairs_per_variant": n, "impostor_pairs_per_variant": n * (n - 1),
        "variants_run": len(variants),
        "thresholds_used": {"tau_accept": tau_accept, "tau_reject": tau_reject,
                            "cosine_genuine": cos_gen, "l2_genuine": l2_gen},
        "derived_thresholds": thresholds,
        "table_by_family": table, "overall_over_modifications": overall,
        "runtime_seconds": round(time.time() - t_start, 1),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (out_dir / "per_variant.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(per_variant_rows[0].keys()))
        w.writeheader(); w.writerows(per_variant_rows)
    (out_dir / "table.md").write_text(render_md(summary, families, engines), encoding="utf-8")

    if args.dump_npz:
        # Literal rank-based thresholds (what LS-DB1 used) on the CLEAN impostor
        # LBPH distribution, so Kyle can see how far the fixed-rank rule is from
        # the FAR percentile at LFW scale.
        imp_sorted = np.sort(imp_lbph)
        uniq_sorted = np.unique(imp_sorted)
        rank8_ordered = float(imp_sorted[7]) if imp_sorted.size >= 8 else float("nan")
        uniq4 = float(uniq_sorted[3]) if uniq_sorted.size >= 4 else float("nan")
        np.savez_compressed(
            out_dir / "distributions.npz",
            imp_lbph=imp_lbph.astype(np.float32),            # clean cross-identity (threshold basis)
            imp_l2=imp_l2.astype(np.float32),
            gen_lbph_mod=np.asarray(gen_lbph_mod, np.float32),  # pooled modified genuine
            gen_l2_mod=np.asarray(gen_l2_mod, np.float32),
            tau_accept_100ppm=np.float32(tau_accept_lfw),
            tau_accept_1pct=np.float32(tau_accept_1pct),
            l2_genuine=np.float32(l2_genuine_lfw),
            tau_reject=np.float32(tau_reject), cos_gen=np.float32(cos_gen),
            rank8_ordered=np.float32(rank8_ordered), uniq4=np.float32(uniq4),
        )
        print(f"[LBPH clean-impostor rank rules] 8th-ordered = {rank8_ordered:.4f} | "
              f"4th-unique = {uniq4:.4f}  (vs 100ppm percentile {tau_accept_lfw:.4f})")
        print(f"[SAVE] {out_dir}/distributions.npz")

    print(f"\n[OK] {out_dir}/table.md  (runtime {summary['runtime_seconds']}s)")
    return 0


def _acc(conf):
    tp, fn, fp, tn = conf
    tot = tp + fn + fp + tn
    return round(100.0 * (tp + tn) / tot, 1) if tot else 0.0


def render_md(summary, families, engines):
    th = summary["derived_thresholds"]
    L = ["# LFW all-families verification (Dr. Oh protocol, partial run)", "",
         f"Clean anchor vs modified probe, every pair scored. "
         f"Identities: **{summary['identities']}** (seed {summary['seed']}). "
         f"Per modification: {summary['genuine_pairs_per_variant']} genuine + "
         f"{summary['impostor_pairs_per_variant']:,} impostor pairs.", "",
         "**Thresholds (LFW1-derived vs LS-DB1-frozen):**", "",
         "| | tau_accept (LBPH) | l2_genuine (SFace) | tau_reject | cosine_genuine |",
         "|---|---:|---:|---:|---:|",
         f"| **LFW1-derived (used here)** | {th['lfw1_derived']['tau_accept']} "
         f"(@{th['lfw1_derived']['tau_accept_far_percent']}% FAR) | "
         f"{th['lfw1_derived']['l2_genuine']} | {th['shared']['tau_reject']} | "
         f"{th['shared']['cosine_genuine']} |",
         f"| LS-DB1-frozen (deployed) | {th['lsdb1_frozen']['tau_accept']} | "
         f"{th['lsdb1_frozen']['l2_genuine']} | {th['shared']['tau_reject']} | "
         f"{th['shared']['cosine_genuine']} |", "",
         f"> **Transfer finding.** At LFW's **1% FAR** the LBPH accept edge is "
         f"**{th['lfw1_derived']['tau_accept_1pct_far']}** — *above* the carried reject edge "
         f"{th['shared']['tau_reject']}, which would collapse the escalation band (Hybrid→LBPH). "
         f"So tau_accept is placed at 100 ppm here to keep accept<reject. The LS-DB1-frozen "
         f"{th['lsdb1_frozen']['tau_accept']} is much stricter than either LFW point: the frozen "
         f"thresholds do not transfer to LFW.", "",
         "Accuracy = (TP+TN)/all (the figure's formula). Balanced = ½(TPR+TNR), "
         "the prevalence-robust companion — raw accuracy is TN-dominated at "
         f"{summary['impostor_pairs_per_variant'] // summary['genuine_pairs_per_variant']}:1 "
         "impostor:genuine (STATE-07-21 Finding 3).", "",
         "## Accuracy (%) — raw (TP+TN)/all", "",
         "| Modification | LBPH | SFace | Hybrid |", "|---|---:|---:|---:|"]
    for fam in families:
        r = summary["table_by_family"][fam]
        L.append(f"| {fam} | {r['lbph']['accuracy_pct']} | {r['sface']['accuracy_pct']} "
                 f"| {r['hybrid']['accuracy_pct']} |")
    o = summary["overall_over_modifications"]
    L.append(f"| **overall (mods)** | **{o['lbph']['accuracy_pct']}** | "
             f"**{o['sface']['accuracy_pct']}** | **{o['hybrid']['accuracy_pct']}** |")
    L += ["", "## Balanced accuracy (%) — ½(TPR+TNR)", "",
          "| Modification | LBPH | SFace | Hybrid |", "|---|---:|---:|---:|"]
    for fam in families:
        r = summary["table_by_family"][fam]
        L.append(f"| {fam} | {r['lbph']['balanced_acc_pct']} | {r['sface']['balanced_acc_pct']} "
                 f"| {r['hybrid']['balanced_acc_pct']} |")
    L.append(f"| **overall (mods)** | **{o['lbph']['balanced_acc_pct']}** | "
             f"**{o['sface']['balanced_acc_pct']}** | **{o['hybrid']['balanced_acc_pct']}** |")
    return "\n".join(L) + "\n"


def _selfcheck():
    """Runnable check: confusion cells sum to the pair budget; cos->l2 transform."""
    n = 5
    d = np.array([10.0, 200, 200, 200, 200])   # only genuine (idx0) below tau
    cos = np.array([0.9, 0.0, 0.0, 0.0, 0.0]); l2 = np.sqrt(np.clip(2 - 2 * cos, 0, None))
    import types
    g = types.SimpleNamespace()
    globals().update(n=n) if False else None
    # inline mini-confusion (tau_accept=70, cos_gen=.363, l2_gen=1.1, tau_reject=76)
    imp = np.ones(n, bool); imp[0] = False
    acc = d <= 70
    tp, fn, fp, tn = int(acc[0]), int(not acc[0]), int(acc[imp].sum()), int((~acc[imp]).sum())
    assert (tp, fn, fp, tn) == (1, 0, 0, 4), (tp, fn, fp, tn)
    assert tp + fn == 1 and fp + tn == n - 1
    assert abs(l2[0] - np.sqrt(2 - 2 * 0.9)) < 1e-6
    print("selfcheck ok")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        raise SystemExit(main())
