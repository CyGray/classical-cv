"""Unedited vs variant comparison for the classical recognizers.

For each family this benchmarks the DEPLOYED OpenCV recognizer ("unedited")
against the opt-in variants in ``src/classical_faces/variants.py``:

* **LBPH feature-size options** (docs/SUGGESTION.md): Fisher-score top-K
  histogram dimensions - optionally restricted to the eyebrow/eye/nose/mouth
  grid cells - at <1 KB byte budgets (float32 or uint8), matched by chi-square
  against per-identity centroids or all training templates.
* **Eigen/Fisher accuracy options**: drop leading PCA components, eigenvalue
  whitening (Mahalanobis), cosine distance, per-identity centroid galleries,
  and a capped-components Eigen model.

Protocol matches the clean loop: train on ``data/split_lasalle/train``,
rank-1 + genuine scores on the held-out ``data/split_lasalle/test``, impostor
scores from Haar-cropped LFW (full set by default -> FAR resolvable to
~100 ppm). Writes ``reports/benchmark/variant_comparison.{json,md}``.

Usage::

    python scripts/compare_variants.py                       # full impostor set
    python scripts/compare_variants.py --impostor-max-identities 400   # quick
"""

import argparse
import json
import sys
import time
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.tar_at_far import equal_error_rate, operating_point  # noqa: E402
from src.classical_faces.datasets import list_image_files  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import (  # noqa: E402
    IMG_SIZE,
    detect_largest_face_box,
    normalize_face,
)
from src.classical_faces.variants import (  # noqa: E402
    CompactLBPH,
    SubspaceMatcher,
    lbph_histograms_from_tiles,
    read_subspace_model,
)

OPERATING_FAR = 1.058   # La Salle independence operating point
SPEC_FAR = 0.01         # spec budget (100 ppm)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unedited vs variant classical comparison.")
    parser.add_argument("--families", default="lbph,eigenfaces,fisherfaces")
    parser.add_argument("--train-dir", default="data/split_lasalle/train")
    parser.add_argument("--test-dir", default="data/split_lasalle/test")
    parser.add_argument("--impostor-dir", default="data/lfw-dataset")
    parser.add_argument("--impostor-max-identities", type=int, default=0)
    parser.add_argument("--impostor-max-per-id", type=int, default=0)
    parser.add_argument("--impostor-batch", type=int, default=1000)
    parser.add_argument("--cascade-path", default="haar/haarcascade_frontalface_default.xml")
    parser.add_argument("--output-json", default="reports/benchmark/variant_comparison.json")
    parser.add_argument("--output-md", default="reports/benchmark/variant_comparison.md")
    return parser.parse_args()


def _abs(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else PROJECT_ROOT / q


def load_person_grays(base_dir: Path) -> list[tuple[str, np.ndarray]]:
    out = []
    for pdir in sorted(d for d in base_dir.iterdir() if d.is_dir()):
        for fn in list_image_files(str(pdir)):
            img = cv.imread(str(pdir / fn))
            if img is not None:
                out.append((pdir.name, cv.cvtColor(img, cv.COLOR_BGR2GRAY)))
    return out


def load_impostor_rois(base_dir: Path, cascade, max_ids: int, max_per_id: int) -> list[np.ndarray]:
    rois = []
    persons = sorted(d for d in base_dir.iterdir() if d.is_dir())
    if max_ids > 0:
        persons = persons[:max_ids]
    t0 = time.time()
    for i, pdir in enumerate(persons, 1):
        files = list_image_files(str(pdir))
        if max_per_id > 0:
            files = files[:max_per_id]
        for fn in files:
            img = cv.imread(str(pdir / fn))
            if img is None:
                continue
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            box = detect_largest_face_box(image_gray=gray, face_cascade=cascade,
                                          min_face_size=40, scale_factor=1.1, min_neighbors=5)
            if box is None:
                continue
            x, y, w, h = box
            rois.append(gray[y: y + h, x: x + w])
        if i % 1000 == 0 or i == len(persons):
            print(f"  [crop] {i}/{len(persons)} ids | {len(rois)} faces | {time.time()-t0:.0f}s",
                  flush=True)
    return rois


def metrics_row(
    name: str,
    *,
    unedited: bool,
    feature_bytes: int,
    template_store_bytes: int,
    genuine: list[tuple[float, bool]],
    impostor_dists: list[float],
) -> dict:
    impostor_sorted = sorted(impostor_dists)
    rank1 = 100.0 * sum(1 for _, ok in genuine if ok) / len(genuine)
    op1 = operating_point(genuine, impostor_sorted, OPERATING_FAR)
    op_spec = operating_point(genuine, impostor_sorted, SPEC_FAR)
    eer = equal_error_rate(genuine, impostor_sorted)
    return {
        "variant": name,
        "unedited": unedited,
        "feature_bytes": int(feature_bytes),
        "template_store_bytes": int(template_store_bytes),
        "rank1_percent": rank1,
        "tar_at_independence_far": op1["tar_percent"],
        "frr_at_independence_far": op1["frr_percent"],
        "threshold_at_independence_far": op1["threshold_predict_scale"],
        "tar_at_spec_far": op_spec["tar_percent"],
        "spec_far_resolvable": op_spec["resolvable"],
        "eer_percent": eer.get("eer_percent"),
        "n_impostor": len(impostor_sorted),
    }


# --------------------------------------------------------------------------- #
# LBPH
# --------------------------------------------------------------------------- #
def run_lbph(train_set, test_set, impostor_rois, batch: int) -> list[dict]:
    eq = SPECS["lbph"].default_equalization
    train_tiles = [normalize_face(g, IMG_SIZE, eq) for _, g in train_set]
    test_tiles = [normalize_face(g, IMG_SIZE, eq) for _, g in test_set]
    label_map: dict[str, int] = {}
    for person, _ in train_set:
        label_map.setdefault(person, len(label_map))
    train_labels = np.array([label_map[p] for p, _ in train_set], dtype=np.int32)
    test_truth = np.array([label_map[p] for p, _ in test_set], dtype=np.int32)

    print("  [lbph] extracting histograms (train/test) ...", flush=True)
    train_h = lbph_histograms_from_tiles(train_tiles, batch)
    test_h = lbph_histograms_from_tiles(test_tiles, batch)

    # Variant grid: full-dim customs + SUGGESTION.md compact options.
    variants: list[CompactLBPH] = [
        CompactLBPH(budget_bytes=65536, dtype="float32", restrict_to_landmarks=False, gallery="all"),
        CompactLBPH(budget_bytes=65536, dtype="float32", restrict_to_landmarks=False, gallery="centroid"),
    ]
    for budget, dtype in ((960, "float32"), (960, "uint8"), (480, "float32"), (480, "uint8")):
        for landmarks in (False, True):
            for gallery in ("centroid", "all"):
                variants.append(CompactLBPH(budget_bytes=budget, dtype=dtype,
                                            restrict_to_landmarks=landmarks, gallery=gallery))
    for v in variants:
        v.fit(train_h, train_labels)

    print("  [lbph] training unedited cv2 model ...", flush=True)
    cv2_model = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    cv2_model.train(train_tiles, train_labels)

    # Genuine scores.
    cv2_genuine = []
    for tile, truth in zip(test_tiles, test_truth):
        pred, dist = cv2_model.predict(tile)
        cv2_genuine.append((float(dist), pred == truth))
    var_genuine: list[list[tuple[float, bool]]] = []
    for v in variants:
        labels, dists = v.predict_batch(test_h)
        var_genuine.append([(float(d), int(l) == int(t))
                            for l, d, t in zip(labels, dists, test_truth)])

    # Impostor scores, streamed in batches so the 13k x 16k histogram matrix
    # never lives in memory at once.
    cv2_imp: list[float] = []
    var_imp: list[list[float]] = [[] for _ in variants]
    t0 = time.time()
    for start in range(0, len(impostor_rois), batch):
        rois = impostor_rois[start: start + batch]
        tiles = [normalize_face(r, IMG_SIZE, eq) for r in rois]
        for tile in tiles:
            cv2_imp.append(float(cv2_model.predict(tile)[1]))
        batch_h = lbph_histograms_from_tiles(tiles, batch)
        for vi, v in enumerate(variants):
            _, dists = v.predict_batch(batch_h)
            var_imp[vi].extend(float(d) for d in dists)
        print(f"  [lbph] impostors {min(start + batch, len(impostor_rois))}/{len(impostor_rois)} "
              f"({time.time()-t0:.0f}s)", flush=True)

    rows = [metrics_row(
        "unedited cv2 LBPH (64 KB, NN over all templates)", unedited=True,
        feature_bytes=65536, template_store_bytes=65536 * len(train_tiles),
        genuine=cv2_genuine, impostor_dists=cv2_imp,
    )]
    for v, gen, imp in zip(variants, var_genuine, var_imp):
        rows.append(metrics_row(
            v.describe(), unedited=False,
            feature_bytes=v.feature_bytes, template_store_bytes=v.template_store_bytes,
            genuine=gen, impostor_dists=imp,
        ))
    return rows


# --------------------------------------------------------------------------- #
# Eigen / Fisher
# --------------------------------------------------------------------------- #
def run_subspace(family: str, train_set, test_set, impostor_rois, batch: int) -> list[dict]:
    spec = SPECS[family]
    eq = spec.default_equalization
    train_tiles = [normalize_face(g, IMG_SIZE, eq) for _, g in train_set]
    test_tiles = [normalize_face(g, IMG_SIZE, eq) for _, g in test_set]
    label_map: dict[str, int] = {}
    for person, _ in train_set:
        label_map.setdefault(person, len(label_map))
    train_labels = np.array([label_map[p] for p, _ in train_set], dtype=np.int32)
    test_truth = np.array([label_map[p] for p, _ in test_set], dtype=np.int32)

    component_configs = [0, 100] if family == "eigenfaces" else [0]
    drops = (0, 1, 2) if family == "eigenfaces" else (0, 1)
    root_key = "opencv_eigenfaces" if family == "eigenfaces" else "opencv_fisherfaces"

    rows: list[dict] = []
    for comps in component_configs:
        print(f"  [{family}] training cv2 model (num_components={comps}) ...", flush=True)
        model = spec.create(num_components=comps)
        model.train(train_tiles, train_labels)
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".yml", delete=False)
        tmp.close()
        try:
            model.save(tmp.name)
            eigenvectors, mean, eigenvalues, projections, labels = read_subspace_model(
                tmp.name, root_key)
        finally:
            os.unlink(tmp.name)
        k = eigenvectors.shape[1]

        # Unedited row = the deployed cv2 predict behaviour.
        cv2_genuine = []
        for tile, truth in zip(test_tiles, test_truth):
            pred, dist = model.predict(tile)
            cv2_genuine.append((float(dist), pred == truth))
        cv2_imp = []
        for start in range(0, len(impostor_rois), batch):
            for roi in impostor_rois[start: start + batch]:
                cv2_imp.append(float(model.predict(normalize_face(roi, IMG_SIZE, eq))[1]))
        suffix = f"{k} comps" + ("" if comps == 0 else " (capped)")
        rows.append(metrics_row(
            f"unedited cv2 {family} ({suffix}, NN, L2)", unedited=(comps == 0),
            feature_bytes=k * 4, template_store_bytes=k * 4 * len(train_tiles),
            genuine=cv2_genuine, impostor_dists=cv2_imp,
        ))

        # Project test + impostors ONCE per trained model; variants re-use them.
        base = SubspaceMatcher(eigenvectors=eigenvectors, mean=mean, eigenvalues=eigenvalues,
                               train_projections=projections, train_labels=labels)
        test_proj = base.project_tiles(test_tiles)
        imp_proj_parts = []
        for start in range(0, len(impostor_rois), batch):
            tiles = [normalize_face(r, IMG_SIZE, eq) for r in impostor_rois[start: start + batch]]
            imp_proj_parts.append(base.project_tiles(tiles))
        imp_proj = np.concatenate(imp_proj_parts, axis=0) if imp_proj_parts else np.zeros((0, k))

        for drop in drops:
            if drop >= k:
                continue
            for distance in ("l2", "cosine", "whiten-l2", "whiten-cosine"):
                for gallery in ("nn", "centroid"):
                    if comps == 0 and drop == 0 and distance == "l2" and gallery == "nn":
                        continue  # numerically the unedited row
                    matcher = SubspaceMatcher(
                        eigenvectors=eigenvectors, mean=mean, eigenvalues=eigenvalues,
                        train_projections=projections, train_labels=labels,
                        drop_first=drop, distance=distance, gallery=gallery,
                    )
                    g_labels, g_dists = matcher.predict_batch(test_proj)
                    genuine = [(float(d), int(l) == int(t))
                               for l, d, t in zip(g_labels, g_dists, test_truth)]
                    _, i_dists = matcher.predict_batch(imp_proj)
                    rows.append(metrics_row(
                        matcher.describe(), unedited=False,
                        feature_bytes=matcher.feature_bytes,
                        template_store_bytes=matcher.template_store_bytes,
                        genuine=genuine, impostor_dists=[float(d) for d in i_dists],
                    ))
        print(f"  [{family}] comps={comps}: {len(rows)} rows so far", flush=True)
    return rows


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def to_markdown(results: dict[str, list[dict]], cfg: dict) -> str:
    lines = [
        "# Classical Variants - unedited vs feature-size / accuracy options",
        "",
        f"Train `{cfg['train_dir']}` | held-out genuine `{cfg['test_dir']}` (56) | "
        f"impostors `{cfg['impostor_dir']}` ({cfg['n_impostor']} Haar-cropped).",
        "",
        "**Unedited** = the deployed OpenCV recognizer exactly as the clean loop runs it. "
        "LBPH variants implement docs/SUGGESTION.md: keep only the most discriminative "
        "histogram dimensions (optionally restricted to eyebrow/eye/nose/mouth grid cells) "
        "within a byte budget. Eigen/Fisher variants change the matcher only "
        "(drop leading components / whitening / cosine / centroid gallery).",
        "",
        "TAR/FRR at the La Salle independence FAR (~1.058%); `TAR@100ppm` at the spec budget "
        "(blank when the impostor sample cannot resolve it). Rows sorted by TAR@1.058%.",
        "",
    ]
    for family, rows in results.items():
        lines.append(f"## {family}")
        lines.append("")
        lines.append("| Variant | Feature B | <1 KB? | Gallery store | Rank-1 % | TAR@1.058% | "
                     "FRR | TAR@100ppm | EER % |")
        lines.append("|---|---:|:--:|---:|---:|---:|---:|---:|---:|")
        ordered = sorted(rows, key=lambda r: (not r["unedited"], -r["tar_at_independence_far"]))
        for r in ordered:
            name = ("**" + r["variant"] + "**") if r["unedited"] else r["variant"]
            spec_tar = f"{r['tar_at_spec_far']:.2f}%" if r["spec_far_resolvable"] else "-"
            eer = f"{r['eer_percent']:.2f}" if r.get("eer_percent") is not None else "n/a"
            store = r["template_store_bytes"]
            store_h = f"{store/1024:.0f} KB" if store < 1024 ** 2 else f"{store/1024**2:.1f} MB"
            lines.append(
                f"| {name} | {r['feature_bytes']} | "
                f"{'YES' if r['feature_bytes'] < 1024 else 'no'} | {store_h} | "
                f"{r['rank1_percent']:.2f} | {r['tar_at_independence_far']:.2f}% | "
                f"{r['frr_at_independence_far']:.2f}% | {spec_tar} | {eer} |"
            )
        lines.append("")
    lines += [
        "## Notes",
        "",
        "- LBPH variant naming: `top<K>-<area>-<dtype>-<gallery>`; K = histogram dimensions kept "
        "(Fisher-score ranked), `landmarks` = restricted to the eyebrow/eye/nose/mouth cells of "
        "the 8x8 grid, dtype uint8 = 4x more dims per byte. `Gallery store` is the total "
        "enrolled-template storage (the model-size analogue).",
        "- Subspace variant naming: `<K>c-drop<d>-<distance>-<gallery>`; dropping leading PCA "
        "components removes illumination-dominated directions; whitening divides by sqrt of the "
        "eigenvalues (Mahalanobis).",
        "- These are OPT-IN options, not replacements: the deployed pipeline still uses the "
        "unedited recognizers; promote a variant only after it also clears a live run.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    families = [f.strip().lower() for f in args.families.split(",") if f.strip()]
    cascade = cv.CascadeClassifier(str(_abs(args.cascade_path)))
    if cascade.empty():
        raise FileNotFoundError("Could not load Haar cascade.")

    print("[INFO] loading datasets ...")
    train_set = load_person_grays(_abs(args.train_dir))
    test_set = load_person_grays(_abs(args.test_dir))
    print(f"[INFO] train={len(train_set)} test={len(test_set)}")
    print("[INFO] Haar-cropping impostors once ...")
    impostor_rois = load_impostor_rois(_abs(args.impostor_dir), cascade,
                                       args.impostor_max_identities, args.impostor_max_per_id)
    print(f"[INFO] impostors={len(impostor_rois)}")

    results: dict[str, list[dict]] = {}
    for family in families:
        print(f"\n[FAMILY] {family}")
        if family == "lbph":
            results[family] = run_lbph(train_set, test_set, impostor_rois, args.impostor_batch)
        else:
            results[family] = run_subspace(family, train_set, test_set, impostor_rois,
                                           args.impostor_batch)
        best = max(results[family], key=lambda r: r["tar_at_independence_far"])
        print(f"[BEST] {family}: {best['variant']} TAR@1.058%={best['tar_at_independence_far']:.2f}%")

    cfg = {"train_dir": args.train_dir, "test_dir": args.test_dir,
           "impostor_dir": args.impostor_dir, "n_impostor": len(impostor_rois)}
    out_json = _abs(args.output_json)
    out_md = _abs(args.output_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump({"config": cfg, "results": results}, f, indent=2)
    with out_md.open("w", encoding="utf-8") as f:
        f.write(to_markdown(results, cfg))
    print(f"\n[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")


if __name__ == "__main__":
    main()
