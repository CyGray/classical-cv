"""
Shared utilities for independence tests across face recognition models.

Provides:
  - train_and_extract_features: trains a multi-identity model and extracts
    feature vectors (LBPH histograms or PCA projections) from the saved model file
  - compute_pairwise_distances: builds N×(N-1) distance matrix from feature vectors
  - normalize_distances_0_100: maps raw distances to [0, 100] scale
"""

import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import cv2 as cv
import numpy as np


# ---------------------------------------------------------------------------
# Feature-vector extraction via saved model YAML
# ---------------------------------------------------------------------------

def _read_lbph_histograms(model_path: str) -> Tuple[List[np.ndarray], np.ndarray]:
    """Read LBPH histograms and labels from a saved OpenCV model file."""
    fs = cv.FileStorage(model_path, cv.FILE_STORAGE_READ)
    root = fs.getNode("opencv_lbphfaces")
    hist_node = root.getNode("histograms")
    n = hist_node.size()
    histograms: List[np.ndarray] = []
    for i in range(n):
        mat = hist_node.at(i).mat()
        histograms.append(mat.flatten().astype(np.float64))
    labels_node = root.getNode("labels")
    labels = labels_node.mat().flatten().astype(np.int32)
    fs.release()
    return histograms, labels


def _read_projections(model_path: str, root_key: str) -> Tuple[np.ndarray, np.ndarray]:
    """Read PCA/LDA projections and labels from an Eigenfaces/Fisherfaces model file."""
    fs = cv.FileStorage(model_path, cv.FILE_STORAGE_READ)
    root = fs.getNode(root_key)
    proj_node = root.getNode("projections")
    # projections is a sequence of opencv-matrix entries (one per training sample)
    n = proj_node.size()
    rows: List[np.ndarray] = []
    for i in range(n):
        mat = proj_node.at(i).mat()
        rows.append(mat.flatten())
    projections = np.stack(rows, axis=0).astype(np.float64)
    labels_node = root.getNode("labels")
    labels = labels_node.mat().flatten().astype(np.int32)
    fs.release()
    return projections, labels


def train_and_extract_features(
    faces: Dict[str, "np.ndarray | List[np.ndarray]"],
    label_map: Dict[str, int],
    model_type: str,
) -> Tuple[np.ndarray, List[str]]:
    """
    Train a single multi-identity recognizer on all faces, then extract
    feature vectors by round-tripping through a temporary model file.

    Parameters
    ----------
    faces : dict mapping identity name -> preprocessed face image, or a LIST of
        face images. Extra images per identity are used for TRAINING only (this
        is required for Fisherfaces: LDA with one image per class has zero
        within-class scatter and degenerates). The comparison feature for each
        identity is always the FIRST image's feature, so the pairwise protocol
        stays N x (N-1) with one probe per identity.
    label_map : dict mapping identity name -> integer label
    model_type : 'lbph', 'eigenfaces', or 'fisherfaces'

    Returns
    -------
    feature_matrix : np.ndarray, shape (N, feature_dim)
        Row i corresponds to identity[i] (its first/probe image).
    identities : list of str
        Sorted identity names matching feature_matrix rows.
    """
    identities = sorted(faces.keys())
    n = len(identities)
    if n < 2:
        raise ValueError("Need at least 2 identities.")

    faces_list: List[np.ndarray] = []
    labels: List[int] = []
    probe_row: Dict[str, int] = {}
    for p in identities:
        person_faces = faces[p]
        if not isinstance(person_faces, list):
            person_faces = [person_faces]
        for img in person_faces:
            if p not in probe_row:
                probe_row[p] = len(faces_list)
            faces_list.append(img)
            labels.append(label_map[p])
    labels_list = np.array(labels, dtype=np.int32)

    # -- train model -------------------------------------------------------
    if model_type == "lbph":
        model = cv.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8,
        )
    elif model_type in ("eigenfaces", "fisherfaces"):
        if model_type == "eigenfaces":
            num_comp = min(n - 1, 50)
            model = cv.face.EigenFaceRecognizer_create(
                num_components=num_comp, threshold=1e9,
            )
        else:
            # Fisherfaces LDA constraint: 1 <= num_components < num_classes
            num_comp = max(1, min(n - 2, 49))
            model = cv.face.FisherFaceRecognizer_create(
                num_components=num_comp, threshold=1e9,
            )
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    model.train(faces_list, labels_list)

    # -- save & re-read feature vectors ------------------------------------
    tmp = tempfile.NamedTemporaryFile(suffix=".yml", delete=False)
    tmp.close()
    try:
        model.save(tmp.name)
        if model_type == "lbph":
            histograms, _ = _read_lbph_histograms(tmp.name)
            feat_all = np.stack(histograms, axis=0)
        elif model_type == "eigenfaces":
            projections, _ = _read_projections(
                tmp.name, "opencv_eigenfaces",
            )
            feat_all = np.asarray(projections, dtype=np.float64)
        else:  # fisherfaces
            projections, _ = _read_projections(
                tmp.name, "opencv_fisherfaces",
            )
            feat_all = np.asarray(projections, dtype=np.float64)
    finally:
        os.unlink(tmp.name)

    # Stored features are in training order; keep one probe row per identity.
    feat = feat_all[[probe_row[p] for p in identities], :]
    return feat, identities


# ---------------------------------------------------------------------------
# Distance functions
# ---------------------------------------------------------------------------

def chi_squared_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Chi-squared distance between two LBPH histograms."""
    eps = 1e-10
    diff = a - b
    denom = a + b + eps
    return float(0.5 * np.sum(diff * diff / denom))


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two feature vectors (PCA projections)."""
    return float(np.linalg.norm(a - b))


# ---------------------------------------------------------------------------
# Pairwise distance computation
# ---------------------------------------------------------------------------

def compute_pairwise_distances(
    feature_matrix: np.ndarray,
    identities: List[str],
    model_type: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> List[dict]:
    """
    Compute all N×(N-1) cross-identity distances.

    Parameters
    ----------
    feature_matrix : (N, D) array  –  one row per identity
    identities : list of str, length N
    model_type : 'lbph' → chi-squared ; otherwise → euclidean

    Returns
    -------
    list of dicts with keys:
        query_identity, query_image_path (''), candidate_identity,
        candidate_image_path (''), raw_distance, normalized_distance
    """
    n = len(identities)
    dist_fn = chi_squared_distance if model_type == "lbph" else euclidean_distance

    raw_distances: List[Tuple[int, int, float]] = []

    for i in range(n):
        fi = feature_matrix[i]
        for j in range(n):
            if i == j:
                continue
            d = dist_fn(fi, feature_matrix[j])
            raw_distances.append((i, j, d))
        if progress_callback is not None:
            progress_callback(i + 1, n)

    # -- normalise to 0‑100 ------------------------------------------------
    raw_vals = np.array([d for (_, _, d) in raw_distances], dtype=np.float64)
    dmax = float(np.max(raw_vals)) if len(raw_vals) > 0 else 0.0
    if dmax > 0:
        norm_vals = 100.0 * raw_vals / dmax
    else:
        norm_vals = np.zeros_like(raw_vals)

    records = []
    for (i, j, raw_d), norm_d in zip(raw_distances, norm_vals):
        records.append({
            "query_identity": identities[i],
            "query_image_path": "",
            "candidate_identity": identities[j],
            "candidate_image_path": "",
            "raw_distance": raw_d,
            "normalized_distance": float(norm_d),
        })

    return records


def aggregate_pairwise_results(
    all_runs_records: List[List[dict]],
) -> List[dict]:
    """
    Aggregate results from multiple runs by computing the mean distance for each pair.

    Parameters
    ----------
    all_runs_records : list of list of dicts
        Each inner list contains records from one run.

    Returns
    -------
    aggregated_records : list of dicts
        Records with 'raw_distance' and 'normalized_distance' as means.
    """
    if not all_runs_records:
        return []

    # Map (query, candidate) -> list of distances
    raw_dist_map = defaultdict(list)
    
    # We assume all runs have the same pairs (identities)
    # Extract identity info from the first run
    first_run = all_runs_records[0]
    pair_info = {} # (query, candidate) -> {query_path, cand_path}
    
    for run in all_runs_records:
        for record in run:
            key = (record["query_identity"], record["candidate_identity"])
            raw_dist_map[key].append(record["raw_distance"])
            if key not in pair_info:
                pair_info[key] = {
                    "query_image_path": record.get("query_image_path", ""),
                    "candidate_image_path": record.get("candidate_image_path", ""),
                }

    aggregated = []
    for key, distances in raw_dist_map.items():
        mean_raw = float(np.mean(distances))
        aggregated.append({
            "query_identity": key[0],
            "query_image_path": pair_info[key]["query_image_path"],
            "candidate_identity": key[1],
            "candidate_image_path": pair_info[key]["candidate_image_path"],
            "raw_distance": mean_raw,
        })

    # Re-normalize the aggregated raw distances to 0-100
    return normalize_distances_0_100(aggregated)


# ---------------------------------------------------------------------------
# Rank-based threshold determination (spec methodology)
# ---------------------------------------------------------------------------

def error_pair_threshold(records: List[dict], k: int) -> dict | None:
    """Threshold = feature distance of the k-th nearest impostor pair.

    All records here are cross-identity (impostor) comparisons. Sorting them by
    distance ascending, the k-th smallest distance is the "k-th error pair":
    setting the match threshold there yields exactly k false accepts, so the
    realized false-alarm rate is ``k / N``. This is the project-spec method
    (La Salle DB1 = 8th error pair ~ 10,000 ppm; LFW DB1 = 331st ~ 10 ppm),
    replacing the older percentile heuristic.
    """
    n = len(records)
    if n == 0:
        return None
    k = max(1, min(int(k), n))
    ordered = sorted(records, key=lambda r: r["raw_distance"])
    pair = ordered[k - 1]
    return {
        "error_pair_rank": k,
        "comparisons": n,
        "raw_threshold": float(pair["raw_distance"]),
        "normalized_threshold": float(pair.get("normalized_distance", 0.0)),
        "realized_far_ppm": 1.0e6 * k / n,
        "realized_far_percent": 100.0 * k / n,
        "query_identity": pair.get("query_identity", ""),
        "candidate_identity": pair.get("candidate_identity", ""),
    }


def _default_curve_ranks(n: int) -> List[int]:
    ranks: List[int] = []
    k = 1
    while k < n:
        ranks.append(k)
        k *= 2
    return sorted(set(ranks))


def error_pair_report(
    records: List[dict],
    *,
    target_far_ppm: float = 10000.0,
    explicit_rank: int | None = None,
    ranks: List[int] | None = None,
) -> dict:
    """Rank-based threshold report at a target false-alarm rate.

    The spec operating point's rank is ``round(target_far * N)`` (or an explicit
    rank if given). Also returns a FAR-vs-threshold curve over a range of ranks
    so the tradeoff is visible. La Salle's 756 comparisons cannot resolve finer
    than ~1,300 ppm (k=1), which the realized FAR makes explicit.
    """
    n = len(records)
    if n == 0:
        return {"comparisons": 0, "spec": None, "curve": []}

    if explicit_rank is not None:
        spec_k = max(1, min(int(explicit_rank), n))
    else:
        # ceil reproduces both spec anchors exactly: ceil(756 * 10000 ppm) = 8
        # (La Salle DB1) and ceil(33,045,252 * 10 ppm) = 331 (LFW DB1).
        spec_k = max(1, min(math.ceil(target_far_ppm / 1.0e6 * n), n))

    spec = error_pair_threshold(records, spec_k)
    if spec is not None:
        spec["target_far_ppm"] = (
            float(target_far_ppm) if explicit_rank is None else spec["realized_far_ppm"]
        )

    if ranks is None:
        ranks = _default_curve_ranks(n)
        if spec_k not in ranks:
            ranks = sorted(set(ranks + [spec_k]))
    curve = [error_pair_threshold(records, k) for k in ranks if 1 <= k <= n]
    return {"comparisons": n, "spec": spec, "curve": curve}


def error_pair_report_from_topk(
    *,
    top_unique_distances: "np.ndarray",
    top_unique_pairs: List[Tuple[str, str]],
    total_ordered_comparisons: int,
    max_distance: float,
    target_far_ppm: float = 10.0,
    explicit_rank: int | None = None,
    ranks: List[int] | None = None,
) -> dict:
    """Rank-based threshold report from a streamed top-K of UNIQUE pair distances.

    For the full-LFW path the N x (N-1) ordered comparison list (33M records)
    cannot be materialized. Because all distance functions here are symmetric,
    every unordered pair appears exactly twice in the ordered list, so the k-th
    ordered error pair is the ceil(k/2)-th smallest unique pair. This builds the
    same report shape as :func:`error_pair_report` from just the smallest unique
    distances (ascending) and the total ordered comparison count.
    """
    n = int(total_ordered_comparisons)
    if n == 0 or len(top_unique_distances) == 0:
        return {"comparisons": 0, "spec": None, "curve": []}

    def entry(ordered_rank: int) -> dict | None:
        unique_idx = math.ceil(ordered_rank / 2) - 1
        if unique_idx >= len(top_unique_distances):
            return None
        raw = float(top_unique_distances[unique_idx])
        q, c = top_unique_pairs[unique_idx]
        return {
            "error_pair_rank": ordered_rank,
            "comparisons": n,
            "raw_threshold": raw,
            "normalized_threshold": (100.0 * raw / max_distance) if max_distance > 0 else 0.0,
            "realized_far_ppm": 1.0e6 * ordered_rank / n,
            "realized_far_percent": 100.0 * ordered_rank / n,
            "query_identity": q,
            "candidate_identity": c,
        }

    if explicit_rank is not None:
        spec_k = max(1, min(int(explicit_rank), n))
    else:
        spec_k = max(1, min(math.ceil(target_far_ppm / 1.0e6 * n), n))

    spec = entry(spec_k)
    if spec is not None:
        spec["target_far_ppm"] = (
            float(target_far_ppm) if explicit_rank is None else spec["realized_far_ppm"]
        )

    if ranks is None:
        max_covered = 2 * len(top_unique_distances)
        ranks = [k for k in _default_curve_ranks(n) if k <= max_covered]
        if spec_k not in ranks:
            ranks = sorted(set(ranks + [spec_k]))
    curve = [e for e in (entry(k) for k in ranks if 1 <= k <= n) if e is not None]
    return {"comparisons": n, "spec": spec, "curve": curve}


def format_error_pair_report(report: dict) -> str:
    """Pretty console block for an ``error_pair_report`` result."""
    n = report.get("comparisons", 0)
    spec = report.get("spec")
    lines = [f"[RANK-BASED THRESHOLD - k-th error pair, N={n} comparisons]"]
    if spec:
        lines.append(
            f"  SPEC operating point: rank={spec['error_pair_rank']} "
            f"FAR={spec['realized_far_ppm']:.1f} ppm ({spec['realized_far_percent']:.3f}%)"
        )
        lines.append(
            f"    threshold raw={spec['raw_threshold']:.4f} "
            f"normalized(0-100)={spec['normalized_threshold']:.4f}"
        )
        lines.append(
            f"    boundary impostor pair: {spec['query_identity']} vs {spec['candidate_identity']}"
        )
    if report.get("curve"):
        lines.append("  FAR curve (rank -> threshold):")
        for e in report["curve"]:
            lines.append(
                f"    k={e['error_pair_rank']:<4} FAR={e['realized_far_ppm']:9.1f} ppm  "
                f"raw={e['raw_threshold']:10.4f}  norm={e['normalized_threshold']:8.4f}"
            )
    return "\n".join(lines)


def normalize_distances_0_100(
    records: List[dict],
) -> List[dict]:
    """
    Re‑normalise an existing list of records with 'raw_distance' keys to 0‑100.
    Used when records already exist but need rescaling.
    """
    raw_vals = np.array([r["raw_distance"] for r in records], dtype=np.float64)
    if len(raw_vals) == 0:
        return records
    dmax = float(np.max(raw_vals))
    if dmax > 0:
        for r, v in zip(records, 100.0 * raw_vals / dmax):
            r["normalized_distance"] = float(v)
    else:
        for r in records:
            r["normalized_distance"] = 0.0
    return records
