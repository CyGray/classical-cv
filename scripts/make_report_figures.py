"""Report deliverables: the classical-track metrics tables + figures.

Builds, strictly from committed run artifacts (no invented numbers):

TABLES  -> reports/figures/METRICS.md
  1. Main Performance Summary (TAR / FAR / FRR / mean AR / latency / model
     size / feature size / Pass-Fail) - one row per algorithm.
  2. Accuracy Ratio by modification category (Heavy/Medium/Light/Mean per
     algorithm) + a merged 3-algorithm comparison.
  3. Independence Test Results (algorithm x dataset: La Salle / LFW).

FIGURES -> reports/figures/*.png
  1. fig1_tar_far_roc.png       TAR vs FAR (ROC, log-FAR) - one curve/algorithm.
  2. fig2_interidentity_hist.png  cross-identity distance distribution + thr line.
  3. fig3_ar_by_modification.png  grouped AR bars (LBPH/Eigen/Fisher).
  4. fig4_latency_fps.png         end-to-end FPS + latency bars.

Data sources (all under reports/):
  benchmark/tar_at_far.json, benchmark/accuracy_ratio.json,
  benchmark/independence_thresholds.json (+ _lfw), benchmark/live_fps/aggregate_summary.json,
  evaluation/{family}_eval.json, independence/{family}_lasalle/comparisons.csv (+ summary.json).

The ROC needs the genuine/impostor predict-distance arrays, which the committed
tar_at_far.json does not store; this script regenerates them once (reusing the
canonical scoring in src.benchmark.tar_at_far) and caches them to
reports/figures/data/roc_scores.json. Pass --refresh-roc to recompute.

Usage:
    python scripts/make_report_figures.py                 # full LFW impostors (slow once)
    python scripts/make_report_figures.py --impostor-max-identities 300   # quick validate
    python scripts/make_report_figures.py --skip-roc      # tables + figs 2-4 only
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FAMILIES = ["lbph", "eigenfaces", "fisherfaces"]
DISPLAY = {"lbph": "LBPH", "eigenfaces": "Eigenfaces", "fisherfaces": "Fisherfaces"}
COLORS = {"lbph": "#1f77b4", "eigenfaces": "#ff7f0e", "fisherfaces": "#2ca02c"}

REPORTS = PROJECT_ROOT / "reports"
OUT_DIR = REPORTS / "figures"
DATA_DIR = OUT_DIR / "data"

# Spec-sheet targets (BRIEFING.md S6 / SPEC_COMPARISON.md).
SPEC = {
    "tar_min": 90.0,           # %
    "tar_max": 95.0,           # % (read band; exceeding is still a pass)
    "far_max_ppm": 100.0,      # < 0.01 %
    "frr_min": 1.0, "frr_max": 5.0,  # %
    "latency_max_ms": 100.0,
    "fps_min": 30.0,
    "feature_max_bytes": 1024,
}
SPEC_FAR_PERCENT = 0.01        # the spec FAR budget operating point (100 ppm)
INDEP_FAR_PERCENT = 1.058      # La Salle DB1 independence operating point (8th pair)

# Deterministic modification suite (mirrors src/benchmark/accuracy_ratio.py).
# severity(level) -> magnitude of the perturbation from the identity transform,
# used to bucket levels into Light / Medium / Heavy tiers.
SEVERITY = {
    "brightness_up": lambda lv: abs(lv),
    "brightness_down": lambda lv: abs(lv),
    "contrast_up": lambda lv: abs(lv - 1.0),
    "contrast_down": lambda lv: abs(lv - 1.0),
    "gamma_up": lambda lv: abs(math.log(lv)),
    "gamma_down": lambda lv: abs(math.log(lv)),
    "gaussian_noise": lambda lv: abs(lv),
    "gaussian_blur": lambda lv: abs(lv),
    "motion_blur": lambda lv: abs(lv),
    "rotation": lambda lv: abs(lv),
    "zoom": lambda lv: abs(lv - 1.0),
    "occlusion": lambda lv: abs(lv),
}


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_csv_distances(path: Path) -> np.ndarray:
    vals = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vals.append(float(row["distance_normalized"]))
    return np.asarray(vals, dtype=np.float64)


def op_point(tar_far: dict, family: str, target_far_percent: float) -> dict:
    row = next(r for r in tar_far["rows"] if r["family"] == family)
    return min(row["operating_points"],
               key=lambda o: abs(o["target_far_percent"] - target_far_percent))


def fps_map(live: dict) -> dict[str, float]:
    return {a["algorithm"]: a["average_fps"] for a in live["algorithms"]}


# --------------------------------------------------------------------------- #
# AR severity tiering
# --------------------------------------------------------------------------- #
def tier_ar(modification: str, levels: list[dict]) -> dict:
    """Bucket a modification's levels into Light/Medium/Heavy by severity.

    distinct severities sorted ascending -> fraction f=(rank-1)/(m-1);
    tier index = round(f*2) (0=Light, 1=Medium, 2=Heavy). Symmetric-direction
    levels (e.g. rotation -5 & +5) share a severity and land in the same tier.
    Mean AR within each tier; the all-level mean equals the reported mod AR.
    """
    sev_fn = SEVERITY[modification]
    sevs = sorted({round(sev_fn(lv["level"]), 9) for lv in levels})
    m = len(sevs)
    buckets = {0: [], 1: [], 2: []}
    for lv in levels:
        s = round(sev_fn(lv["level"]), 9)
        rank = sevs.index(s)
        f = rank / (m - 1) if m > 1 else 0.0
        buckets[int(round(f * 2))].append(lv["ar_percent"])
    out = {}
    for idx, name in [(0, "light"), (1, "medium"), (2, "heavy")]:
        out[name] = float(np.mean(buckets[idx])) if buckets[idx] else None
    out["mean"] = float(np.mean([lv["ar_percent"] for lv in levels]))
    return out


# --------------------------------------------------------------------------- #
# Tables -> METRICS.md
# --------------------------------------------------------------------------- #
def fmt(x, nd=2, suffix=""):
    return "n/a" if x is None else f"{x:.{nd}f}{suffix}"


def build_tables(tar_far, accuracy, live, evals, indep_ls, indep_lfw) -> str:
    fps = fps_map(live)
    L = []
    L += [
        "# Classical Track - Metrics Tables",
        "",
        "*Generated by `scripts/make_report_figures.py` from committed run artifacts "
        "(no invented numbers). Genuine = held-out La Salle test (56 probes); "
        "impostors = LFW (13,149 Haar-cropped); 41-modification AR on the same "
        "held-out originals. Operating point = spec FAR budget (100 ppm; actual "
        "76 ppm, the LFW-resolvable floor).*",
        "",
        "---",
        "",
        "## Table 1 - Main Performance Summary",
        "",
        "| Algorithm | TAR % | FAR (ppm) | FRR % | Mean AR % (41 mods) | "
        "Latency (ms) | Model size (KB) | Feature (bytes) | Pass/Fail vs spec |",
        "|---|---:|---:|---:|---:|---:|---:|---:|:--|",
    ]
    # spec reference row
    L.append(
        f"| **Spec target** | {SPEC['tar_min']:.0f}-{SPEC['tar_max']:.0f} | "
        f"< {SPEC['far_max_ppm']:.0f} | {SPEC['frr_min']:.0f}-{SPEC['frr_max']:.0f} | "
        f"(robustness) | < {SPEC['latency_max_ms']:.0f} | (Pi context) | "
        f"< {SPEC['feature_max_bytes']} | - |"
    )
    summary_rows = {}
    for fam in FAMILIES:
        op = op_point(tar_far, fam, SPEC_FAR_PERCENT)
        ar = next(r for r in accuracy["rows"] if r["family"] == fam)["overall_ar_percent"]
        foot = evals[fam]["footprint"]
        model_kb = foot["model_file_bytes"] / 1024.0
        feat_b = foot["feature_vector_bytes"]
        fps_v = fps.get(fam)
        latency = 1000.0 / fps_v if fps_v else None
        far_ppm = op["actual_far_percent"] * 1e4
        tar, frr = op["tar_percent"], op["frr_percent"]

        tar_ok = tar >= SPEC["tar_min"]
        frr_ok = frr <= SPEC["frr_max"]
        far_ok = far_ppm <= SPEC["far_max_ppm"]
        verdict = ("**PASS** (accuracy block)" if (tar_ok and frr_ok and far_ok)
                   else "**FAIL** (TAR/FRR)")
        notes = []
        if feat_b >= SPEC["feature_max_bytes"]:
            notes.append("feature >1 KB")
        else:
            notes.append("feature <1 KB OK")
        if latency and latency < SPEC["latency_max_ms"]:
            notes.append("latency OK")
        verdict = verdict + "; " + ", ".join(notes)

        summary_rows[fam] = dict(tar=tar, frr=frr, far_ppm=far_ppm, ar=ar,
                                 latency=latency, model_kb=model_kb, feat_b=feat_b,
                                 fps=fps_v)
        L.append(
            f"| {DISPLAY[fam]} | {fmt(tar)} | {far_ppm:.0f} | {fmt(frr)} | "
            f"{fmt(ar)} | {fmt(latency,1)} | {model_kb:,.0f} | {feat_b:,} | {verdict} |"
        )
    L += [
        "",
        "TAR/FAR/FRR are verification operating points on each recognizer's native "
        "`predict()` scale at the 100 ppm spec FAR budget (`tar_at_far.json`). "
        "Latency = 1000 / measured end-to-end live FPS (detection + recognition; the "
        "recognizer `predict()` itself is sub-ms - the Haar detector dominates, and the "
        "LBPH FPS log predates the Tan-Triggs switch). Model size is the saved `.yml`; "
        "feature size is per-face (LBPH 8x8x256 hist; Eigen/Fisher comps x 4 B).",
        "",
        "---",
        "",
    ]

    # ---- Table 2: AR by modification ------------------------------------- #
    L += [
        "## Table 2 - Accuracy Ratio by modification category",
        "",
        "AR = K/M (correct identity AND within the deployable threshold) per "
        "(modification, level); the mean over a modification's levels is its AR. "
        "Levels are bucketed into severity tiers - **Light** (mildest) / **Medium** / "
        "**Heavy** (most severe) - by perturbation magnitude; symmetric levels "
        "(e.g. rotation -5deg & +5deg) share a tier, so rotation/zoom have an empty "
        "Medium. `Mean` is the all-level mean (the headline per-modification AR).",
        "",
    ]
    mod_order = [m["modification"]
                 for m in sorted(
                     next(r for r in accuracy["rows"] if r["family"] == "lbph")["modifications"],
                     key=lambda x: -x["ar_percent"])]
    tier_tables = {}
    for fam in FAMILIES:
        rec = next(r for r in accuracy["rows"] if r["family"] == fam)
        by_mod = {m["modification"]: m for m in rec["modifications"]}
        tier_tables[fam] = {mod: tier_ar(mod, by_mod[mod]["levels"]) for mod in by_mod}

    # 2a: merged comparison
    L += [
        "### 2a - Merged comparison (mean AR % per modification)",
        "",
        "| Modification | LBPH | Eigenfaces | Fisherfaces |",
        "|---|---:|---:|---:|",
    ]
    for mod in mod_order:
        cells = " | ".join(fmt(tier_tables[f][mod]["mean"], 1) for f in FAMILIES)
        L.append(f"| {mod} | {cells} |")
    overall = {f: next(r for r in accuracy["rows"] if r["family"] == f)["overall_ar_percent"]
               for f in FAMILIES}
    L.append(f"| **Overall (mean of mods)** | **{overall['lbph']:.1f}** | "
             f"**{overall['eigenfaces']:.1f}** | **{overall['fisherfaces']:.1f}** |")
    L.append("")

    # 2b: per-algorithm Heavy/Medium/Light/Mean
    for fam in FAMILIES:
        L += [
            f"### 2b - {DISPLAY[fam]}: AR % by severity tier",
            "",
            "| Modification | Light | Medium | Heavy | Mean |",
            "|---|---:|---:|---:|---:|",
        ]
        for mod in mod_order:
            t = tier_tables[fam][mod]
            L.append(f"| {mod} | {fmt(t['light'],1)} | "
                     f"{'-' if t['medium'] is None else fmt(t['medium'],1)} | "
                     f"{fmt(t['heavy'],1)} | {fmt(t['mean'],1)} |")
        L.append(f"| **Overall** | | | | **{overall[fam]:.1f}** |")
        L.append("")
    L += [
        "> Geometric distortion is the classical failure mode: **rotation** is the "
        "single weakest modification for Eigenfaces (26.3 %) and Fisherfaces (14.3 %). "
        "The suite has no pure translation/crop modification - rotation and zoom (scale) "
        "are the geometric proxies present; LBPH absorbs them (83 % / 88 %) far better "
        "than the subspace methods.",
        "",
        "---",
        "",
    ]

    # ---- Table 3: Independence -------------------------------------------- #
    L += [
        "## Table 3 - Independence Test Results",
        "",
        "Threshold = feature distance of the k-th nearest cross-identity (impostor) "
        "pair at the target FAR (spec rank rule). Scales are per-model and per-dataset "
        "(not comparable across rows). La Salle and LFW use different feature bases.",
        "",
        "| Algorithm | Dataset | Comparison set size | FAR target (ppm) | Realized FAR (ppm) | "
        "Threshold (raw) | Threshold (norm 0-100) | Boundary pair | Status |",
        "|---|---|---:|---:|---:|---:|---:|:--|:--|",
    ]
    ls_rows = {r["family"]: r["spec"] for r in indep_ls["rows"]}
    for fam in FAMILIES:
        s = ls_rows[fam]
        L.append(
            f"| {DISPLAY[fam]} | La Salle DB1 | {s['comparisons']} ({int(round(math.sqrt(s['comparisons'])))+1}x{int(round(math.sqrt(s['comparisons'])))}) | "
            f"10,000 (8th pair) | {s['realized_far_ppm']:,.0f} | {s['raw_threshold']:.2f} | "
            f"{s['normalized_threshold']:.2f} | {s['query_identity']} vs {s['candidate_identity']} | "
            f"Determined (1.06% FAR floor) |"
        )
    lfw_rows = {r["family"]: r["spec"] for r in indep_lfw["rows"]}
    for fam in FAMILIES:
        s = lfw_rows[fam]
        L.append(
            f"| {DISPLAY[fam]} | LFW DB1 (smoke) | {s['comparisons']:,} (300 ids) | "
            f"10 (331st pair) | {s['realized_far_ppm']:.1f} | {s['raw_threshold']:.2f} | "
            f"{s['normalized_threshold']:.2f} | {s['query_identity']} vs {s['candidate_identity']} | "
            f"Smoke; full 33M run pending |"
        )
    L += [
        "",
        "- **La Salle DB1** (756 = 28x27 comparisons) determines each model's threshold at "
        "its design operating point (8th error pair = 10,582 ppm = 1.058 %). 756 comparisons "
        "cannot resolve the spec's 100 ppm / 10 ppm - that needs LFW DB1.",
        "- **LFW DB1** is the gated full protocol (5,749 ids -> 33,045,252 comparisons, 331st "
        "pair ~ 10 ppm). The committed run is a **300-identity smoke** (89,700 comparisons, "
        "k=1 ~ 11 ppm); all three families flag the **same boundary pair "
        "(Andrew_Caldecott vs Andrew_Gilligan)** - the known LFW annotation-error failure "
        "mode to eyeball before trusting full-run thresholds.",
        "- 'Pass/Fail' for the independence test is whether the target FAR is *resolvable*: "
        "La Salle resolves only ~1,300 ppm (so 100 ppm is a FAIL on La Salle alone, PASS as a "
        "1.058 % operating point); the LFW full run is the protocol-grade certification and is "
        "**pending**.",
        "",
    ]
    return "\n".join(L), summary_rows, tier_tables, mod_order, overall


# --------------------------------------------------------------------------- #
# Figure 2 - inter-identity distance histogram
# --------------------------------------------------------------------------- #
def fig_histogram(indep_ls, summaries_ls):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    ls_rows = {r["family"]: r["spec"] for r in indep_ls["rows"]}
    for ax, fam in zip(axes, FAMILIES):
        dists = load_csv_distances(REPORTS / "independence" / f"{fam}_lasalle" / "comparisons.csv")
        spec = ls_rows[fam]
        thr = spec["normalized_threshold"]
        # self-check: the 8th-smallest distance must reproduce the committed threshold.
        eighth = float(np.sort(dists)[spec["error_pair_rank"] - 1])
        assert abs(eighth - thr) < 1e-3, f"{fam}: 8th={eighth} != thr={thr}"
        below = int(np.sum(dists <= thr + 1e-9))

        ax.hist(dists, bins=30, color=COLORS[fam], alpha=0.78, edgecolor="white")
        ax.axvline(thr, color="red", linestyle="--", linewidth=2,
                   label=f"threshold = {thr:.2f}\n(8th pair, {below} accepts = 1.06% FAR)")
        ax.set_title(f"{DISPLAY[fam]}", fontsize=12, fontweight="bold")
        ax.set_xlabel("cross-identity distance (normalized 0-100)")
        ax.set_ylabel("count" if fam == "lbph" else "")
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Inter-identity (impostor) distance distribution - La Salle DB1, "
                 "756 cross-identity comparisons", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = OUT_DIR / "fig2_interidentity_hist.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# Figure 3 - AR by modification (grouped bars)
# --------------------------------------------------------------------------- #
def fig_ar(tier_tables, mod_order, overall):
    x = np.arange(len(mod_order))
    w = 0.26
    fig, ax = plt.subplots(figsize=(14, 6))
    for i, fam in enumerate(FAMILIES):
        vals = [tier_tables[fam][m]["mean"] for m in mod_order]
        ax.bar(x + (i - 1) * w, vals, w, label=f"{DISPLAY[fam]} (overall {overall[fam]:.1f}%)",
               color=COLORS[fam])
    for i, fam in enumerate(FAMILIES):
        ax.axhline(overall[fam], color=COLORS[fam], linestyle=":", linewidth=1, alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(mod_order, rotation=40, ha="right")
    ax.set_ylabel("Accuracy Ratio (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Accuracy Ratio by modification - held-out La Salle, 41-mod suite, "
                 "at the independence threshold", fontsize=12, fontweight="bold")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    out = OUT_DIR / "fig3_ar_by_modification.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# Figure 4 - latency / FPS
# --------------------------------------------------------------------------- #
def fig_latency(live, summaries):
    fps = fps_map(live)
    dl = ["mobilefacenet", "edgeface", "arcface", "arcface_int8"]
    dl_present = [d for d in dl if d in fps]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.2))

    # Left: throughput (FPS), classical highlighted + DL context.
    names = FAMILIES + dl_present
    labels = [DISPLAY.get(n, n) for n in names]
    vals = [fps[n] for n in names]
    bar_colors = [COLORS.get(n, "#9467bd") for n in FAMILIES] + ["#999999"] * len(dl_present)
    bars = ax1.bar(labels, vals, color=bar_colors)
    ax1.axhline(SPEC["fps_min"], color="red", linestyle="--", linewidth=1.5,
                label=f"real-time spec ({SPEC['fps_min']:.0f} fps)")
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v:.1f}", ha="center", fontsize=8)
    ax1.set_ylabel("End-to-end throughput (FPS)")
    ax1.set_title("Measured live FPS (detection + recognition)\nclassical = color, DL = grey",
                  fontsize=11, fontweight="bold")
    ax1.tick_params(axis="x", rotation=35)
    ax1.legend(fontsize=8)
    ax1.grid(axis="y", alpha=0.25)

    # Right: latency (ms/frame), classical only against the 100 ms spec.
    lat = [summaries[f]["latency"] for f in FAMILIES]
    bars2 = ax2.bar([DISPLAY[f] for f in FAMILIES], lat, color=[COLORS[f] for f in FAMILIES])
    ax2.axhline(SPEC["latency_max_ms"], color="red", linestyle="--", linewidth=1.5,
                label=f"latency spec (< {SPEC['latency_max_ms']:.0f} ms)")
    for b, v in zip(bars2, lat):
        ax2.text(b.get_x() + b.get_width() / 2, v + 1.0, f"{v:.0f}", ha="center", fontsize=9)
    ax2.set_ylabel("End-to-end latency (ms / frame)")
    ax2.set_ylim(0, max(120, max(lat) * 1.3))
    ax2.set_title("Per-frame latency (1000 / FPS)\nclassical recognizers", fontsize=11,
                  fontweight="bold")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    out = OUT_DIR / "fig4_latency_fps.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# ROC score regeneration (reuses canonical tar_at_far scoring) + Figure 1
# --------------------------------------------------------------------------- #
def compute_roc_scores(impostor_max_ids: int) -> dict:
    import cv2 as cv
    from src.benchmark.tar_at_far import load_genuine_grays, load_impostor_rois
    from src.classical_faces.pipeline import SPECS, load_label_map, load_recognizer
    from src.classical_faces.preprocess import IMG_SIZE, normalize_face

    genuine_dir = str(PROJECT_ROOT / "data" / "split_lasalle" / "test")
    impostor_dir = str(PROJECT_ROOT / "data" / "lfw-dataset")
    cascade = str(PROJECT_ROOT / "haar" / "haarcascade_frontalface_default.xml")
    face_cascade = cv.CascadeClassifier(cascade)

    known_names: set = set()
    for fam in FAMILIES:
        lp = PROJECT_ROOT / "models" / fam / "labels_lasalle_clean.json"
        if lp.exists():
            _, _, known_names = load_label_map(str(lp))
            break

    print(f"[roc] loading genuine ({genuine_dir})")
    genuine_grays = load_genuine_grays(genuine_dir)
    print(f"[roc] cropping impostors once ({impostor_dir}); max_ids={impostor_max_ids or 'all'}")
    impostor_rois, skipped = load_impostor_rois(
        impostor_dir, face_cascade=face_cascade, known_names=known_names,
        min_face_size=40, max_ids=impostor_max_ids, max_per_id=0)
    print(f"[roc] impostors={len(impostor_rois)} (skipped {skipped})")

    out = {"config": {"n_genuine": len(genuine_grays), "n_impostor": len(impostor_rois),
                      "impostor_skipped": skipped}, "families": {}}
    for fam in FAMILIES:
        spec = SPECS[fam]
        model = PROJECT_ROOT / "models" / fam / "lasalle_clean.yml"
        labels = PROJECT_ROOT / "models" / fam / "labels_lasalle_clean.json"
        _, id_to_name, _ = load_label_map(str(labels))
        rec = load_recognizer(spec, str(model))
        eq = spec.default_equalization
        genuine = []
        for person, gray in genuine_grays:
            pid, dist = rec.predict(normalize_face(gray, IMG_SIZE, eq))
            genuine.append([float(dist), bool(id_to_name.get(pid) == person)])
        impostor = sorted(float(rec.predict(normalize_face(roi, IMG_SIZE, eq))[1])
                          for roi in impostor_rois)
        out["families"][fam] = {"equalization": eq, "genuine": genuine, "impostor": impostor}
        print(f"[roc] {fam}: scored {len(genuine)} genuine + {len(impostor)} impostor")
    return out


def roc_points(genuine: list, impostor_sorted: list):
    import bisect
    n_imp = len(impostor_sorted)
    n_gen = len(genuine)
    cands = sorted(set([d for d, _ in genuine] + list(impostor_sorted)))
    fars, tars = [], []
    for t in cands:
        far = 100.0 * bisect.bisect_right(impostor_sorted, t) / n_imp
        tar = 100.0 * sum(1 for d, ok in genuine if ok and d <= t) / n_gen
        fars.append(far)
        tars.append(tar)
    return np.asarray(fars), np.asarray(tars)


def fig_roc(scores, tar_far):
    fig, ax = plt.subplots(figsize=(8.5, 6.4))
    floor = 100.0 / max(1, scores["config"]["n_impostor"])  # min resolvable FAR (%)
    for fam in FAMILIES:
        g = [(d, ok) for d, ok in scores["families"][fam]["genuine"]]
        imp = scores["families"][fam]["impostor"]
        far, tar = roc_points(g, imp)
        mask = far > 0
        far_p = np.clip(far[mask], floor, None)
        ax.semilogx(far_p, tar[mask], color=COLORS[fam], linewidth=2,
                    label=f"{DISPLAY[fam]}")
        # mark the spec 100 ppm operating point
        op = op_point(tar_far, fam, SPEC_FAR_PERCENT)
        ax.scatter([max(op["actual_far_percent"], floor)], [op["tar_percent"]],
                   color=COLORS[fam], s=55, zorder=5, edgecolor="black", linewidth=0.6)

    ax.axvline(SPEC_FAR_PERCENT, color="red", linestyle="--", linewidth=1.3,
               label="spec FAR budget (100 ppm)")
    ax.axvline(INDEP_FAR_PERCENT, color="grey", linestyle=":", linewidth=1.3,
               label="independence op. point (1.06%)")
    ax.set_xlabel("False Acceptance Rate (%, log scale)")
    ax.set_ylabel("True Acceptance Rate (%)")
    ax.set_ylim(0, 102)
    ax.set_title("TAR vs FAR (ROC) - held-out La Salle genuine vs LFW impostors\n"
                 "markers = 100 ppm operating point", fontsize=12, fontweight="bold")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    out = OUT_DIR / "fig1_tar_far_roc.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impostor-max-identities", type=int, default=0,
                    help="Cap LFW impostor identities for the ROC (0 = all; use ~300 to validate).")
    ap.add_argument("--refresh-roc", action="store_true", help="Recompute the ROC score cache.")
    ap.add_argument("--skip-roc", action="store_true", help="Skip figure 1 (ROC) entirely.")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    tar_far = load_json(REPORTS / "benchmark" / "tar_at_far.json")
    accuracy = load_json(REPORTS / "benchmark" / "accuracy_ratio.json")
    live = load_json(REPORTS / "benchmark" / "live_fps" / "aggregate_summary.json")
    indep_ls = load_json(REPORTS / "benchmark" / "independence_thresholds.json")
    indep_lfw = load_json(REPORTS / "benchmark" / "independence_thresholds_lfw.json")
    evals = {f: load_json(REPORTS / "evaluation" / f"{f}_eval.json") for f in FAMILIES}
    summaries_ls = {r["family"]: load_json(REPORTS / "independence" / f"{r['family']}_lasalle" / "summary.json")
                    for r in indep_ls["rows"]}

    md, summaries, tier_tables, mod_order, overall = build_tables(
        tar_far, accuracy, live, evals, indep_ls, indep_lfw)
    (OUT_DIR / "METRICS.md").write_text(md, encoding="utf-8")
    print(f"[ok] wrote {OUT_DIR / 'METRICS.md'}")

    print("[ok] figure 2 ->", fig_histogram(indep_ls, summaries_ls))
    print("[ok] figure 3 ->", fig_ar(tier_tables, mod_order, overall))
    print("[ok] figure 4 ->", fig_latency(live, summaries))

    if not args.skip_roc:
        cache = DATA_DIR / "roc_scores.json"
        if cache.exists() and not args.refresh_roc:
            print(f"[roc] using cached scores {cache}")
            scores = load_json(cache)
        else:
            scores = compute_roc_scores(args.impostor_max_identities)
            cache.write_text(json.dumps(scores), encoding="utf-8")
            print(f"[roc] cached scores -> {cache}")
        print("[ok] figure 1 ->", fig_roc(scores, tar_far))

    print("\n[done] deliverables in", OUT_DIR)


if __name__ == "__main__":
    main()
