"""LFW DB1 independence test - ordered N x (N-1), rank-based k-th error pair.

Implements the spec's LFW operating point: one probe image per LFW identity,
all ordered cross-identity comparisons (5,749 ids -> 33,045,252), threshold =
the **331st error pair (~10 ppm)**. This is the second half of the 7/15
threshold deliverable (La Salle DB1 = ``scripts/run_independence_thresholds.py``).

Because 33M comparison records cannot be materialized, this runs a streaming
top-K: distances are symmetric, so every unordered pair appears twice in the
ordered list and the k-th ordered error pair equals the ceil(k/2)-th smallest
unique pair. We keep only the smallest unique distances (plus the global max
for 0-100 normalization) and report through
``src.independence_common.error_pair_report_from_topk``.

Feature extraction per family (same representation the La Salle test uses):

* **lbph**        - OpenCV LBPH histograms (radius 1, 8 neighbours, 8x8 grid),
                    read back from batch-trained temp models; chi-square distance.
* **eigenfaces**  - PCA basis (50 components) trained on a probe subset
                    (``--basis-train-max``), all probes projected; euclidean.
* **fisherfaces** - LDA basis trained on identities with >= 2 images (2 each,
                    capped by ``--fisher-train-identities``) so the within-class
                    scatter is well-posed; all probes projected; euclidean.

GATING: the full LBPH pass is hours of chi-square work (~5.7k x 5.7k x 16k).
Running with more than --gate-identities requires --confirm-full. Use
``--max-identities 300`` for a smoke run.

Usage::

    python scripts/run_lfw_independence.py --max-identities 300          # smoke
    python scripts/run_lfw_independence.py --families eigenfaces --confirm-full
    python scripts/run_lfw_independence.py --confirm-full                # full spec run

Writes ``reports/independence/<family>_lfw/summary.json`` and the consolidated
``reports/benchmark/independence_thresholds_lfw.{json,md}``.
"""

import argparse
import json
import math
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.classical_faces.datasets import list_image_files  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import (  # noqa: E402
    IMG_SIZE,
    detect_largest_face_box,
    normalize_face,
)
from src.classical_faces.variants import lbph_histograms_from_tiles  # noqa: E402
from src.independence_common import (  # noqa: E402
    error_pair_report_from_topk,
    format_error_pair_report,
)

FAMILIES = ["lbph", "eigenfaces", "fisherfaces"]
DISTANCE_METRIC = {
    "lbph": "chi-square (LBPH histograms)",
    "eigenfaces": "euclidean (PCA projections)",
    "fisherfaces": "euclidean (LDA projections)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LFW ordered N x (N-1) independence thresholds.")
    parser.add_argument("--families", default=",".join(FAMILIES))
    parser.add_argument("--dataset-dir", default="data/lfw-dataset")
    parser.add_argument("--max-identities", type=int, default=0,
                        help="Cap identities for a smoke run (0 = all 5,749).")
    parser.add_argument("--gate-identities", type=int, default=2000,
                        help="Runs above this identity count require --confirm-full.")
    parser.add_argument("--confirm-full", action="store_true",
                        help="Acknowledge the multi-hour full run (mainly LBPH).")
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--min-face-size", type=int, default=40)
    parser.add_argument("--target-far-ppm", type=float, default=10.0,
                        help="Spec LFW operating point = 10 ppm (the 331st error pair at N=5749).")
    parser.add_argument("--error-pair-rank", type=int, default=None,
                        help="Explicit ordered rank k (e.g. 331) overriding --target-far-ppm.")
    parser.add_argument("--basis-train-max", type=int, default=2000,
                        help="Eigenfaces: probes used to train the PCA basis (0 = all; memory-heavy).")
    parser.add_argument("--fisher-train-identities", type=int, default=500,
                        help="Fisherfaces: multi-image identities used to train the LDA basis.")
    parser.add_argument("--num-components", type=int, default=50,
                        help="Subspace dimensionality for Eigen/Fisher features.")
    parser.add_argument("--lbph-batch", type=int, default=250,
                        help="Images per LBPH batch model when extracting histograms "
                             "(capped at 250; larger LBPH model files break cv2.FileStorage).")
    parser.add_argument("--keep-top", type=int, default=4096,
                        help="Unique smallest pair distances kept for the FAR curve.")
    parser.add_argument("--output-json", default="reports/benchmark/independence_thresholds_lfw.json")
    parser.add_argument("--output-md", default="reports/benchmark/independence_thresholds_lfw.md")
    return parser.parse_args()


def _abs(path_value: str) -> Path:
    p = Path(path_value)
    return p if p.is_absolute() else PROJECT_ROOT / p


# --------------------------------------------------------------------------- #
# Probe selection + preprocessing
# --------------------------------------------------------------------------- #
def select_probes(dataset_dir: Path, max_identities: int, seed: int) -> list[tuple[str, str, list[str]]]:
    """(person, probe_path, extra_paths). extra_paths = remaining images (for LDA)."""
    rng = random.Random(seed)
    out: list[tuple[str, str, list[str]]] = []
    persons = sorted(p.name for p in dataset_dir.iterdir() if p.is_dir())
    if max_identities > 0:
        persons = persons[:max_identities]
    for person in persons:
        pdir = dataset_dir / person
        files = list_image_files(str(pdir))
        if not files:
            continue
        probe = rng.choice(files)
        extras = [str(pdir / f) for f in files if f != probe]
        out.append((person, str(pdir / probe), extras))
    return out


def preprocess_probe(
    path: str,
    face_cascade: cv.CascadeClassifier,
    min_face_size: int,
    equalization: str,
) -> np.ndarray | None:
    img = cv.imread(path)
    if img is None:
        return None
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    box = detect_largest_face_box(
        image_gray=gray, face_cascade=face_cascade,
        min_face_size=min_face_size, scale_factor=1.1, min_neighbors=5,
    )
    if box is None:
        return None
    x, y, w, h = box
    return normalize_face(gray[y: y + h, x: x + w], IMG_SIZE, equalization)


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #
def lbph_histograms(tiles: list[np.ndarray], batch: int) -> np.ndarray:
    """OpenCV LBPH histograms for every tile, float32 (n, 16384).

    Delegates to the shared extractor, which caps batches at 250 images
    (cv2.FileStorage cannot parse much larger LBPH model files).
    """
    feats = lbph_histograms_from_tiles(tiles, batch)
    print(f"  [lbph-feat] {len(tiles)}/{len(tiles)}", flush=True)
    return feats


def _read_basis(model_path: str, root_key: str) -> tuple[np.ndarray, np.ndarray]:
    fs = cv.FileStorage(model_path, cv.FILE_STORAGE_READ)
    root = fs.getNode(root_key)
    eigenvectors = root.getNode("eigenvectors").mat()
    mean = root.getNode("mean").mat()
    fs.release()
    return np.asarray(eigenvectors, dtype=np.float64), np.asarray(mean, dtype=np.float64).reshape(1, -1)


def _project_all(tiles: list[np.ndarray], eigenvectors: np.ndarray, mean: np.ndarray) -> np.ndarray:
    data = np.stack([t.reshape(-1) for t in tiles], axis=0).astype(np.float64)
    return ((data - mean) @ eigenvectors).astype(np.float32)


def eigen_features(tiles: list[np.ndarray], basis_train_max: int, num_components: int,
                   seed: int) -> np.ndarray:
    rng = random.Random(seed)
    train_idx = list(range(len(tiles)))
    if 0 < basis_train_max < len(train_idx):
        train_idx = rng.sample(train_idx, basis_train_max)
    train_tiles = [tiles[i] for i in train_idx]
    model = cv.face.EigenFaceRecognizer_create(num_components=num_components, threshold=1e9)
    print(f"  [eigen-basis] training PCA on {len(train_tiles)} probes ...", flush=True)
    model.train(train_tiles, np.arange(len(train_tiles), dtype=np.int32))
    tmp = tempfile.NamedTemporaryFile(suffix=".yml", delete=False)
    tmp.close()
    try:
        model.save(tmp.name)
        eigenvectors, mean = _read_basis(tmp.name, "opencv_eigenfaces")
    finally:
        os.unlink(tmp.name)
    return _project_all(tiles, eigenvectors, mean)


def fisher_features(
    tiles: list[np.ndarray],
    probes: list[tuple[str, str, list[str]]],
    kept_indices: list[int],
    face_cascade: cv.CascadeClassifier,
    min_face_size: int,
    equalization: str,
    train_identities: int,
    num_components: int,
) -> np.ndarray | None:
    """LDA basis from multi-image identities (2 imgs each), then project all probes."""
    train_faces: list[np.ndarray] = []
    train_labels: list[int] = []
    label = 0
    for tile_row, probe_idx in enumerate(kept_indices):
        if train_identities > 0 and label >= train_identities:
            break
        person, _probe_path, extras = probes[probe_idx]
        if not extras:
            continue
        extra_tile = None
        for candidate in extras:
            extra_tile = preprocess_probe(candidate, face_cascade, min_face_size, equalization)
            if extra_tile is not None:
                break
        if extra_tile is None:
            continue
        train_faces.extend([tiles[tile_row], extra_tile])
        train_labels.extend([label, label])
        label += 1
    if label < 2:
        print("  [fisher-basis] not enough multi-image identities; skipping fisherfaces.")
        return None
    comps = max(1, min(num_components, label - 1))
    print(f"  [fisher-basis] training LDA on {label} identities x 2 images "
          f"({comps} components) ...", flush=True)
    model = cv.face.FisherFaceRecognizer_create(num_components=comps, threshold=1e9)
    model.train(train_faces, np.array(train_labels, dtype=np.int32))
    tmp = tempfile.NamedTemporaryFile(suffix=".yml", delete=False)
    tmp.close()
    try:
        model.save(tmp.name)
        eigenvectors, mean = _read_basis(tmp.name, "opencv_fisherfaces")
    finally:
        os.unlink(tmp.name)
    return _project_all(tiles, eigenvectors, mean)


# --------------------------------------------------------------------------- #
# Streaming unique top-K over all pairs
# --------------------------------------------------------------------------- #
def topk_unique_pairs(
    features: np.ndarray,
    metric: str,
    k_keep: int,
    chunk: int = 1024,
    progress_every: int = 250,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Smallest k_keep unique-pair distances (ascending) + indices + global max."""
    n = features.shape[0]
    best_d = np.full(k_keep, np.inf, dtype=np.float64)
    best_i = np.full(k_keep, -1, dtype=np.int64)
    best_j = np.full(k_keep, -1, dtype=np.int64)
    dmax = 0.0
    start_time = time.time()
    for i in range(n - 1):
        q = features[i]
        for s in range(i + 1, n, chunk):
            cand = features[s: s + chunk]
            if metric == "chi2":
                diff = cand - q
                d = 0.5 * np.sum((diff * diff) / (cand + q + 1e-10), axis=1, dtype=np.float64)
            else:
                diff = (cand - q).astype(np.float64)
                d = np.sqrt(np.einsum("ij,ij->i", diff, diff))
            if d.size == 0:
                continue
            chunk_max = float(d.max())
            if chunk_max > dmax:
                dmax = chunk_max
            worst = best_d[-1]
            sel = d < worst
            if np.any(sel):
                cat_d = np.concatenate([best_d, d[sel]])
                cat_i = np.concatenate([best_i, np.full(int(sel.sum()), i, dtype=np.int64)])
                cat_j = np.concatenate([best_j, (np.arange(s, s + d.size, dtype=np.int64))[sel]])
                order = np.argsort(cat_d, kind="stable")[:k_keep]
                best_d, best_i, best_j = cat_d[order], cat_i[order], cat_j[order]
        if (i + 1) % progress_every == 0 or i == n - 2:
            elapsed = time.time() - start_time
            done = (i + 1) / max(n - 1, 1)
            # outer loop i covers ~ (n-i) candidates; fraction of pair work done:
            pair_done = 1.0 - (1.0 - done) ** 2
            eta = elapsed / max(pair_done, 1e-9) * (1.0 - pair_done)
            print(f"  [pairs] query {i + 1}/{n - 1} | elapsed {elapsed/60:.1f} min "
                  f"| eta {eta/60:.1f} min", flush=True)
    valid = np.isfinite(best_d)
    return best_d[valid], best_i[valid], best_j[valid], dmax


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run_family(family: str, args: argparse.Namespace, probes, face_cascade) -> dict | None:
    spec = SPECS[family]
    equalization = spec.default_equalization
    print(f"\n[RUN] {family} (equalization={equalization})")

    tiles: list[np.ndarray] = []
    kept_indices: list[int] = []
    skipped = 0
    t0 = time.time()
    for idx, (person, probe_path, _extras) in enumerate(probes):
        tile = preprocess_probe(probe_path, face_cascade, args.min_face_size, equalization)
        if tile is None:
            skipped += 1
            continue
        kept_indices.append(idx)
        tiles.append(tile)
        if (idx + 1) % 500 == 0 or idx == len(probes) - 1:
            print(f"  [probe] {idx + 1}/{len(probes)} (kept {len(tiles)}, skipped {skipped}, "
                  f"{time.time() - t0:.0f}s)", flush=True)
    n = len(tiles)
    if n < 2:
        print(f"[WARN] {family}: not enough probes.")
        return None
    names = [probes[i][0] for i in kept_indices]

    if family == "lbph":
        features = lbph_histograms(tiles, args.lbph_batch)
        metric = "chi2"
    elif family == "eigenfaces":
        features = eigen_features(tiles, args.basis_train_max, args.num_components,
                                  args.random_seed)
        metric = "l2"
    else:
        features = fisher_features(
            tiles, probes, kept_indices, face_cascade, args.min_face_size, equalization,
            args.fisher_train_identities, args.num_components,
        )
        if features is None:
            return None
        metric = "l2"

    total_ordered = n * (n - 1)
    print(f"  [pairs] {n} probes -> {total_ordered:,} ordered comparisons "
          f"({n * (n - 1) // 2:,} unique)")
    top_d, top_i, top_j, dmax = topk_unique_pairs(features, metric, args.keep_top)

    report = error_pair_report_from_topk(
        top_unique_distances=top_d,
        top_unique_pairs=[(names[i], names[j]) for i, j in zip(top_i, top_j)],
        total_ordered_comparisons=total_ordered,
        max_distance=dmax,
        target_far_ppm=args.target_far_ppm,
        explicit_rank=args.error_pair_rank,
    )
    print(format_error_pair_report(report))

    summary = {
        "dataset": {
            "path": str(_abs(args.dataset_dir)),
            "total_identities": len(probes),
            "selected_identities": n,
            "skipped_no_face_or_unreadable": skipped,
        },
        "protocol": {
            "ordered_comparisons": total_ordered,
            "distance": DISTANCE_METRIC[family],
            "equalization": equalization,
            "target_far_ppm": args.target_far_ppm,
            "explicit_rank": args.error_pair_rank,
            "num_components": (None if family == "lbph" else args.num_components),
        },
        "max_raw_distance": dmax,
        "error_pair_thresholds": report,
    }
    out_dir = _abs(f"reports/independence/{family}_lfw")
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  [save] {out_dir / 'summary.json'}")
    return {"family": family, "n_probes": n, "spec": report.get("spec")}


def to_markdown(rows: list[dict], args: argparse.Namespace) -> str:
    lines = ["# Classical Match Thresholds - LFW DB1 Independence Test (rank-based)", ""]
    lines.append(f"Dataset: `{args.dataset_dir}` | one probe per identity, Haar-cropped | "
                 "ordered N x (N-1) comparisons, k-th error pair (spec: 331st ~ 10 ppm at N=5749).")
    lines.append("")
    lines.append("| Model | Feature distance | Probes | Comparisons | Rank (k) | Realized FAR | "
                 "Threshold (raw) | Threshold (norm 0-100) | Boundary impostor pair |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        s = r.get("spec")
        if not s:
            lines.append(f"| {r['family']} | {DISTANCE_METRIC[r['family']]} | {r['n_probes']} "
                         f"| - | - | - | - | - | (no result) |")
            continue
        pair = f"{s.get('query_identity', '')} vs {s.get('candidate_identity', '')}"
        lines.append(
            f"| {r['family']} | {DISTANCE_METRIC[r['family']]} | {r['n_probes']} | "
            f"{s['comparisons']:,} | {s['error_pair_rank']} | {s['realized_far_ppm']:.2f} ppm | "
            f"{s['raw_threshold']:.4f} | {s['normalized_threshold']:.4f} | {pair} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- Haar misses shrink N below the nominal 5,749; the rank k is recomputed from the "
        "realized ordered count (ceil(target_ppm x N x (N-1))), or pass `--error-pair-rank 331` "
        "to pin the spec rank.",
        "- Eigen/Fisher features are subspace projections (basis trained on a capped subset; "
        "Fisher uses multi-image identities so the LDA is well-posed); LBPH features are exact "
        "OpenCV histograms.",
        "- Scales are per-model and live on the independence feature scale, not the recognizer's "
        "`predict()` scale (see `tar_at_far.py` for the deployable threshold).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    families = [f.strip().lower() for f in args.families.split(",") if f.strip()]
    dataset_dir = _abs(args.dataset_dir)
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Missing dataset dir: {dataset_dir}")

    probes = select_probes(dataset_dir, args.max_identities, args.random_seed)
    n_ids = len(probes)
    if n_ids > args.gate_identities and not args.confirm_full:
        raise SystemExit(
            f"[GATED] {n_ids} identities selected (> {args.gate_identities}). The full LBPH "
            f"pass is multi-hour work. Re-run with --confirm-full to proceed, or use "
            f"--max-identities 300 for a smoke run."
        )
    print(f"[INFO] identities={n_ids} | target {args.target_far_ppm} ppm "
          f"(ordered comparisons if all probes survive: {n_ids * (n_ids - 1):,})")

    face_cascade = cv.CascadeClassifier(str(_abs("haar/haarcascade_frontalface_default.xml")))
    if face_cascade.empty():
        raise FileNotFoundError("Could not load Haar cascade.")

    rows = []
    for family in families:
        row = run_family(family, args, probes, face_cascade)
        if row:
            rows.append(row)

    if not rows:
        raise RuntimeError("No families completed.")

    out_json = _abs(args.output_json)
    out_md = _abs(args.output_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump({"dataset_dir": args.dataset_dir, "max_identities": args.max_identities,
                   "rows": rows}, f, indent=2)
    with out_md.open("w", encoding="utf-8") as f:
        f.write(to_markdown(rows, args))
    print(f"\n[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")


if __name__ == "__main__":
    main()
