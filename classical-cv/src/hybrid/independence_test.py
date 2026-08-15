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
import hashlib
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import cv2 as cv
import numpy as np

from src.benchmark.modifications import apply_variant, parse_variant, stable_rng, variant_tier
from src.classical_faces.detection import create_face_detector
from src.classical_faces.pipeline import SPECS
from src.hybrid.gate import GateThresholds, decide_escalation
from src.hybrid.quality import QualityThresholds, compute_quality
from src.hybrid.recognizer import DEFAULT_THRESHOLDS_PATH, load_thresholds
from src.independence_common import (
    create_lbph_recognizer_for_config,
    lbph_config_metadata,
    resolve_lbph_config,
)
from src.independence_common import error_pair_report, format_error_pair_report
from src.independence_report import add_scaling_args, figure_prefix, segment_bounds
from src.independence_plots import save_distance_curve_plot, save_distance_histogram, save_far_curve
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
    parser.add_argument(
        "--lbph-config",
        default=None,
        help="LBPH descriptor config ID/alias (default: active deployed config; "
             "e.g. r3_n8_g6x6 or selected).",
    )
    parser.add_argument("--iterations", type=int, default=1,
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
    parser.add_argument("--modification", default=None,
                        help="Apply one of the 41-suite variants in-memory to every probe tile "
                             "before scoring, e.g. 'motion_blur:5' or 'contrast_down:0.55' "
                             "(parsed via src.benchmark.modifications.parse_variant; seeded via "
                             "stable_rng per (image, mod, level), same scheme as "
                             "accuracy_ratio_hybrid.py, so probes are bit-identical for the same "
                             "inputs). Default: no modification (clean probes).")
    parser.add_argument("--selection-manifest", default=None,
                        help="Path to a lsface-selection-manifest-v1 JSON (see "
                             "docs/BATCH_WORK/DESIGN.md sec 6.2). When given, skips "
                             "select_one_image_per_person entirely and loads the manifest's "
                             "per-iteration identity->relpath selections, verifying every "
                             "referenced file's SHA-256 before the sweep.")
    add_scaling_args(parser, include_max_identities=False)
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
    selected: dict[str, str] = {}
    for person, person_path in person_dirs:
        target_path = os.path.join(person_path, "light_front.jpg")
        if not os.path.exists(target_path):
            found_files = os.listdir(person_path)
            raise FileNotFoundError(f"Missing light_front.jpg for {person}. Found: {found_files}")
        selected[person] = target_path
    return selected


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_selection_manifest(manifest_path: str, dataset_dir: str, iterations: int) -> dict:
    """Load + verify a ``lsface-selection-manifest-v1`` JSON (Approach B seam,
    docs/BATCH_WORK/DESIGN.md sec 6.2 / sec 7.1 change 3). Raises ValueError
    (naming every offending relpath) on any SHA-256 mismatch, a missing
    identity dir/file, or too few iterations - the caller aborts the run."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    schema = manifest.get("schema")
    if schema != "lsface-selection-manifest-v1":
        raise ValueError(f"Unsupported selection manifest schema: {schema!r}")
    manifest_iterations = int(manifest.get("iterations", 0))
    if manifest_iterations < iterations:
        raise ValueError(
            f"Selection manifest only has {manifest_iterations} iteration(s), "
            f"but --iterations {iterations} was requested."
        )
    selections = manifest.get("selections", {})
    sha256_map = manifest.get("sha256", {})
    missing: list[str] = []
    mismatched: list[str] = []
    for it in range(iterations):
        it_key = str(it)
        it_selection = selections.get(it_key)
        if it_selection is None:
            missing.append(f"iteration {it_key}: no 'selections' entry in manifest")
            continue
        for identity, relpath in it_selection.items():
            identity_dir = os.path.join(dataset_dir, identity)
            if not os.path.isdir(identity_dir):
                missing.append(
                    f"iteration {it_key}: identity dir not found for {identity!r} ({identity_dir})"
                )
                continue
            abs_path = os.path.join(dataset_dir, *relpath.split("/"))
            if not os.path.isfile(abs_path):
                missing.append(
                    f"iteration {it_key}: file not found for {identity!r} -> {relpath!r} ({abs_path})"
                )
                continue
            expected_sha = sha256_map.get(relpath)
            if expected_sha is None:
                missing.append(f"iteration {it_key}: no sha256 entry for {relpath!r}")
                continue
            if _sha256_file(abs_path).lower() != str(expected_sha).lower():
                mismatched.append(f"iteration {it_key}: {identity!r} -> {relpath!r}")
    if missing:
        raise ValueError(
            "Selection manifest verification failed (missing entries):\n  " + "\n  ".join(missing)
        )
    if mismatched:
        raise ValueError(
            "Selection manifest SHA-256 mismatch for:\n  " + "\n  ".join(mismatched)
        )
    return manifest


def selection_from_manifest(manifest: dict, dataset_dir: str, iteration_0based: int) -> dict[str, str]:
    """iteration k (0-based, matching the seed offset ``random_seed + it`` and
    the make_selection_manifest.py key convention) -> {identity: absolute_path},
    sorted identity order."""
    it_selection = manifest["selections"][str(iteration_0based)]
    return {
        identity: os.path.join(dataset_dir, *relpath.split("/"))
        for identity, relpath in sorted(it_selection.items())
    }


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
    cache: dict[str, "ProbeData"] | None = None,
    modification: tuple[str, float] | None = None,
    mod_seed: int = 0,
) -> list[ProbeData]:
    """Build one ProbeData per identity.

    YuNet detection + SFace embedding are the per-image cost; *cache* (keyed by
    image path) lets repeated picks across iterations skip that work entirely
    (safe because *modification* is fixed for the whole process run).

    When *modification* is given (name, level), it is applied to the grayscale
    tile right after load and BEFORE any downstream processing - the modified
    gray is what both LBPH normalization and SFace embedding see, mirroring
    accuracy_ratio_hybrid.py's own "modify gray, then rebuild a 3-channel BGR
    view for detection" order so probes are bit-identical for the same
    (image, mod, level, seed) across both scripts. RNG is seeded via
    ``stable_rng(mod_seed, person, basename, mod_name, mod_level)`` - the exact
    token scheme accuracy_ratio_hybrid.py uses per (image, mod, level).
    """
    probes: list[ProbeData] = []
    for person in sorted(selected):
        path = selected[person]
        if cache is not None and path in cache:
            probes.append(cache[path])
            continue
        image_bgr = cv.imread(path)
        if image_bgr is None:
            print(f"[WARN] Unreadable image skipped: {path}")
            continue
        gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
        if modification is not None:
            mod_name, mod_level = modification
            rng = stable_rng(mod_seed, person, os.path.basename(path), mod_name, mod_level)
            gray = apply_variant(gray, mod_name, mod_level, rng)
            image_bgr = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
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

        probe = ProbeData(
            person=person,
            image_path=path,
            lbph_face=normalize_face(gray, img_size=IMG_SIZE, equalization=equalization),
            sface_feature=np.asarray(feature, dtype=np.float32).reshape(1, -1),
            quality_gray=cv.resize(gray, (100, 100), interpolation=cv.INTER_AREA),
            landmarks=landmarks,
            face_px=int(face_px),
        )
        if cache is not None:
            cache[path] = probe
        probes.append(probe)
    return probes


# --------------------------------------------------------------------------- #
# Multiprocess LBPH sweep - predict_collect() is the dominant cost (one native
# call per query row, each O(N) inside OpenCV's C++) and every row is
# independent (no shared mutable state), so it parallelizes cleanly across
# worker processes. Each worker trains its own recognizer once via the pool
# initializer (cheap, O(N)) then serves per-row predict requests for the life
# of the pool - avoids re-sending the N-image training set on every task.
# --------------------------------------------------------------------------- #
_worker_recognizer = None


def _lbph_pool_init(lbph_faces: list[np.ndarray], lbph_config_id_value: str) -> None:
    global _worker_recognizer
    rec = create_lbph_recognizer_for_config(
        resolve_lbph_config(lbph_config_id_value)
    )
    rec.train(lbph_faces, np.arange(len(lbph_faces), dtype=np.int32))
    _worker_recognizer = rec


def _lbph_pool_predict_rows(
    rows: list[tuple[int, np.ndarray]]
) -> list[tuple[int, list[tuple[int, float]]]]:
    out = []
    for row_idx, face in rows:
        collector = cv.face.StandardCollector_create()
        _worker_recognizer.predict_collect(face, collector)
        out.append((row_idx, collector.getResults(True)))
    return out


def run_sweep(
    probes: list[ProbeData],
    sface: SFaceRecognizer,
    gate_thresholds: GateThresholds,
    quality_thresholds: QualityThresholds,
    csv_path: str | None = None,
    seg_start: int = 0,
    seg_end: int | None = None,
    lbph_config=None,
) -> tuple[dict, dict]:
    """Score all ordered pairs with both engines + the cascade gate.

    Streams per-pair CSV to *csv_path* (if given) and returns
    ``(record_arrays, iteration_summary)`` where *record_arrays* is
    a dict of fixed-width numpy arrays keyed by field name, plus a
    ``"names"`` list.

    ``seg_start``/``seg_end`` restrict the sweep to query rows
    ``[seg_start, seg_end)`` for distributed sharding. Candidates always stay
    global: LBPH still trains on all N tiles and every query is gated against
    the full non-self ranking, so per-row results are identical to a full run.
    """
    n = len(probes)
    if n < 2:
        raise ValueError("Need at least 2 identities with a usable image.")
    if seg_end is None:
        seg_end = n
    seg_len = seg_end - seg_start
    if not (0 <= seg_start < seg_end <= n):
        raise ValueError(f"Bad segment bounds [{seg_start}, {seg_end}) for n={n}.")
    names = [p.person for p in probes]
    image_paths = [p.image_path for p in probes]
    descriptor_config = resolve_lbph_config(lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)

    # -- LBPH: train once (per worker), then predict_collect per query row,
    # spread across processes (each row is O(N) inside OpenCV C++ and
    # independent of every other row - this is the sweep's dominant cost).
    lbph_dist = np.full((seg_len, n), np.inf, dtype=np.float64)
    lbph_faces_all = [p.lbph_face for p in probes]
    n_workers = max(1, min(os.cpu_count() or 1, seg_len))
    if n_workers > 1:
        query_rows = [(i, lbph_faces_all[i]) for i in range(seg_start, seg_end)]
        chunk_size = max(1, -(-len(query_rows) // (n_workers * 4)))
        chunks = [query_rows[k:k + chunk_size] for k in range(0, len(query_rows), chunk_size)]
        with ProcessPoolExecutor(
            max_workers=n_workers,
            initializer=_lbph_pool_init,
            initargs=(lbph_faces_all, descriptor_metadata["id"]),
        ) as pool:
            for chunk_result in pool.map(_lbph_pool_predict_rows, chunks):
                for i, results in chunk_result:
                    row = i - seg_start
                    for label, dist in results:
                        label = int(label)
                        d = float(dist)
                        if d < lbph_dist[row, label]:
                            lbph_dist[row, label] = d
    else:
        recognizer = create_lbph_recognizer_for_config(descriptor_config)
        recognizer.train(lbph_faces_all, np.arange(n, dtype=np.int32))
        for row, i in enumerate(range(seg_start, seg_end)):
            collector = cv.face.StandardCollector_create()
            recognizer.predict_collect(probes[i].lbph_face, collector)
            for label, dist in collector.getResults(True):
                label = int(label)
                d = float(dist)
                if d < lbph_dist[row, label]:
                    lbph_dist[row, label] = d

    # -- SFace: vectorised cosine + L2 (same rule as src/sface/independence_test.py) --
    feats = np.concatenate([p.sface_feature for p in probes], axis=0).astype(np.float32)
    norm = feats / (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-9)
    # Per-row matvec, NOT one big matmul: BLAS picks different blocked kernels
    # for different operand shapes, so a sliced matmul disagrees with the full
    # one at the last float32 ulp. One matvec per query row gives bit-identical
    # cosines no matter how the rows are segmented.
    cos = np.empty((seg_len, n), dtype=np.float32)
    for row, i in enumerate(range(seg_start, seg_end)):
        cos[row] = norm @ norm[i]
        cos[row, i] = -1.0
    l2 = np.sqrt(np.clip(2.0 - 2.0 * cos, 0.0, None), dtype=np.float32)

    # -- Cascade: one gate decision per probe over the non-self ranking -------
    cascade_fp_pair: dict[int, int] = {}   # probe i -> accepted impostor j
    gate_reasons: dict[str, int] = {}
    escalated_probes = 0
    for row, i in enumerate(range(seg_start, seg_end)):
        probe = probes[i]
        others = [j for j in range(n) if j != i]
        ranked = sorted(others, key=lambda j: lbph_dist[row, j])
        d1 = lbph_dist[row, ranked[0]]
        d2 = lbph_dist[row, ranked[1]] if len(ranked) > 1 else d1 + 999.0
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
            j_dl = max(others, key=lambda j: cos[row, j])
            if cos[row, j_dl] >= COSINE_GENUINE_THRESHOLD and l2[row, j_dl] <= L2_GENUINE_THRESHOLD:
                cascade_fp_pair[i] = j_dl
        elif gate.lbph_accept:
            cascade_fp_pair[i] = ranked[0]

    # -- Per-pair records: stream to CSV, collect as compact numpy arrays -----
    comparisons = seg_len * (n - 1)
    rec_lbph = np.empty(comparisons, dtype=np.float32)
    rec_cos = np.empty(comparisons, dtype=np.float32)
    rec_l2 = np.empty(comparisons, dtype=np.float32)
    rec_fp_lbph = np.zeros(comparisons, dtype=np.int8)
    rec_fp_sface = np.zeros(comparisons, dtype=np.int8)
    rec_fp_both = np.zeros(comparisons, dtype=np.int8)
    rec_fp_cascade = np.zeros(comparisons, dtype=np.int8)
    qi_arr = np.empty(comparisons, dtype=np.int32)
    cj_arr = np.empty(comparisons, dtype=np.int32)

    fp_lbph = fp_sface = fp_both = fp_cascade = 0

    csv_file = None
    csv_writer = None
    if csv_path:
        os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
        csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            "query_identity", "candidate_identity",
            "query_image_path", "candidate_image_path",
            "lbph_distance", "sface_cosine", "sface_l2",
            "lbph_fp", "sface_fp", "both_fp", "cascade_fp",
        ])

    idx = 0
    for row, i in enumerate(range(seg_start, seg_end)):
        for j in range(n):
            if i == j:
                continue
            d = float(lbph_dist[row, j])
            c = float(cos[row, j])
            e = float(l2[row, j])
            is_lbph_fp = d <= gate_thresholds.tau_accept
            is_sface_fp = c >= COSINE_GENUINE_THRESHOLD and e <= L2_GENUINE_THRESHOLD
            is_cascade_fp = cascade_fp_pair.get(i) == j
            both = is_lbph_fp and is_sface_fp

            fp_lbph += is_lbph_fp
            fp_sface += is_sface_fp
            fp_both += both
            fp_cascade += is_cascade_fp

            rec_lbph[idx] = d
            rec_cos[idx] = c
            rec_l2[idx] = e
            rec_fp_lbph[idx] = is_lbph_fp
            rec_fp_sface[idx] = is_sface_fp
            rec_fp_both[idx] = both
            rec_fp_cascade[idx] = is_cascade_fp
            qi_arr[idx] = i
            cj_arr[idx] = j

            if csv_writer:
                csv_writer.writerow([
                    names[i], names[j],
                    image_paths[i], image_paths[j],
                    d, c, e,
                    int(is_lbph_fp), int(is_sface_fp),
                    int(both), int(is_cascade_fp),
                ])
            idx += 1

    if csv_file:
        csv_file.close()
        print(f"[SAVE] CSV: {csv_path}")

    record_arrays = {
        "lbph_distance": rec_lbph,
        "sface_cosine": rec_cos,
        "sface_l2": rec_l2,
        "lbph_fp": rec_fp_lbph,
        "sface_fp": rec_fp_sface,
        "both_fp": rec_fp_both,
        "cascade_fp": rec_fp_cascade,
        "query_idx": qi_arr,
        "candidate_idx": cj_arr,
        "names": names,
        "image_paths": image_paths,
        "n": n,
    }
    p_lbph = fp_lbph / comparisons
    p_sface = fp_sface / comparisons
    expected_both = p_lbph * p_sface * comparisons
    fp_union = fp_lbph + fp_sface - fp_both
    summary = {
        "identities": n,
        "comparisons": comparisons,
        "lbph_config": descriptor_metadata,
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
            # Denominator = query rows actually gated (== n on an unsegmented run).
            "escalation_percent": 100.0 * escalated_probes / seg_len,
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
    return record_arrays, summary


# --------------------------------------------------------------------------- #
# Aggregation + reporting
# --------------------------------------------------------------------------- #
# NOTE: per-pair sums are now accumulated incrementally inside main() (running
# accumulators) so peak RAM stays at O(comparisons) instead of
# O(iterations x comparisons); there is no longer an aggregate_iterations() that
# holds every iteration's arrays at once.
def save_aggregated_csv(aggregated: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n_comparisons = len(aggregated["mean_lbph_distance"])
    if n_comparisons == 0:
        return
    
    names = aggregated["names"]
    qi = aggregated["query_idx"]
    cj = aggregated["candidate_idx"]
    lbph_d = aggregated["mean_lbph_distance"]
    cos_d = aggregated["mean_sface_cosine"]
    l2_d = aggregated["mean_sface_l2"]
    lbph_fp = aggregated["lbph_fp_runs"]
    sface_fp = aggregated["sface_fp_runs"]
    both_fp = aggregated["both_fp_runs"]
    cas_fp = aggregated["cascade_fp_runs"]
    runs = aggregated["runs"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "query_identity", "candidate_identity", "mean_lbph_distance",
            "mean_sface_cosine", "mean_sface_l2", "lbph_fp_runs",
            "sface_fp_runs", "both_fp_runs", "cascade_fp_runs", "runs"
        ])
        for k in range(n_comparisons):
            writer.writerow([
                names[int(qi[k])], names[int(cj[k])],
                f"{lbph_d[k]:.6f}", f"{cos_d[k]:.6f}", f"{l2_d[k]:.6f}",
                int(lbph_fp[k]), int(sface_fp[k]), int(both_fp[k]),
                int(cas_fp[k]), runs
            ])
    print(f"[SAVE] CSV: {path}")


def _cos_dist_report_to_l2(report: dict) -> dict:
    """sface_rank_report's raw_threshold is on the ``1 - cosine`` scale (see
    main()'s ``sface_pairs = _top_pairs(1.0 - cosine, ...)``). L2 and cosine
    are a fixed monotonic pair for unit vectors (``l2 = sqrt(2 - 2*cos)``, so
    ``l2 = sqrt(2 * (1 - cos))``), which is what the deployed gate and
    ``l2_genuine`` actually use - convert so the L2 plots' threshold line
    lands on the right axis instead of silently plotting a cosine-distance
    number under an L2 label."""

    def conv(entry: dict | None) -> dict | None:
        if entry is None:
            return None
        out = dict(entry)
        out["raw_threshold"] = float(np.sqrt(2.0 * entry["raw_threshold"]))
        return out

    return {
        **report,
        "spec": conv(report.get("spec")),
        "curve": [conv(e) for e in report.get("curve", [])],
    }


# Histograms/KDE curves only need a representative sample, not literally
# every ordered comparison - on full LFW1 (33M) passing the raw arrays
# straight through does 2x redundant O(points * n) KDE passes per engine
# (histogram + curve plot each recompute it) and was enough to OOM. Cap at
# 2M, seeded for reproducibility; below the cap this is a no-op copy.
PLOT_SAMPLE_CAP = 2_000_000


def _plot_sample(values: np.ndarray, cap: int = PLOT_SAMPLE_CAP, seed: int = 42) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.size <= cap:
        return values
    rng = np.random.default_rng(seed)
    return rng.choice(values, size=cap, replace=False)


def _write_hybrid_plots(args, aggregated: dict, lbph_rank_report: dict, sface_rank_report: dict) -> dict:
    """Write the plots."""
    lbph_distances = _plot_sample(aggregated["mean_lbph_distance"])
    sface_distances = _plot_sample(np.asarray(aggregated["mean_sface_l2"], dtype=np.float64))
    sface_rank_report_l2 = _cos_dist_report_to_l2(sface_rank_report)

    # 2. Write the plots
    # Filenames are prefixed with "<output_dir_basename>_<engine>" so they stay
    # unique when copied into a flat folder (e.g. the Android gallery) - the
    # basename already encodes "<model>_<dataset>" by convention.
    prefix = figure_prefix(args.output_dir)

    lbph_dir = os.path.join(args.output_dir, "lbph")
    os.makedirs(lbph_dir, exist_ok=True)
    lbph_prefix = f"{prefix}_lbph"
    save_distance_histogram(
        lbph_distances,
        os.path.join(lbph_dir, f"{lbph_prefix}_distance_histogram.png"),
        threshold=lbph_rank_report["spec"]["raw_threshold"],
        title="Hybrid Test (LBPH): Inter-Identity Distance Histogram",
        xlabel="Chi-square distance (Raw)",
        far_percent=lbph_rank_report["spec"].get("realized_far_percent"),
    )
    save_distance_curve_plot(
        lbph_distances,
        os.path.join(lbph_dir, f"{lbph_prefix}_distance_curve_plot.png"),
        threshold=lbph_rank_report["spec"]["raw_threshold"],
        title="Hybrid Test (LBPH): Inter-Identity Distance Curve",
        xlabel="Chi-square distance (Raw)",
    )
    save_far_curve(
        lbph_rank_report,
        os.path.join(lbph_dir, f"{lbph_prefix}_far_curve.png"),
        model_label="Hybrid", engine_label="LBPH",
    )

    sface_dir = os.path.join(args.output_dir, "sface")
    os.makedirs(sface_dir, exist_ok=True)
    sface_prefix = f"{prefix}_sface"
    save_distance_histogram(
        sface_distances,
        os.path.join(sface_dir, f"{sface_prefix}_distance_histogram.png"),
        threshold=sface_rank_report_l2["spec"]["raw_threshold"],
        title="Hybrid Test (SFace): Inter-Identity Distance Histogram",
        xlabel="L2 distance (Raw)",
        far_percent=sface_rank_report_l2["spec"].get("realized_far_percent"),
    )
    save_distance_curve_plot(
        sface_distances,
        os.path.join(sface_dir, f"{sface_prefix}_distance_curve_plot.png"),
        threshold=sface_rank_report_l2["spec"]["raw_threshold"],
        title="Hybrid Test (SFace): Inter-Identity Distance Curve",
        xlabel="L2 distance (Raw)",
    )
    save_far_curve(
        sface_rank_report_l2,
        os.path.join(sface_dir, f"{sface_prefix}_far_curve.png"),
        model_label="Hybrid", engine_label="SFace (L2)",
    )

    return {
        "lbph_histogram": os.path.join(lbph_dir, f"{lbph_prefix}_distance_histogram.png"),
        "lbph_curve": os.path.join(lbph_dir, f"{lbph_prefix}_distance_curve_plot.png"),
        "lbph_far": os.path.join(lbph_dir, f"{lbph_prefix}_far_curve.png"),
        "sface_histogram": os.path.join(sface_dir, f"{sface_prefix}_distance_histogram.png"),
        "sface_curve": os.path.join(sface_dir, f"{sface_prefix}_distance_curve_plot.png"),
        "sface_far": os.path.join(sface_dir, f"{sface_prefix}_far_curve.png"),
    }


def main() -> int:
    args = parse_args()
    args.dataset_dir = resolve_path(args.dataset_dir)
    args.output_dir = resolve_path(args.output_dir)
    descriptor_config = resolve_lbph_config(args.lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)

    args.segment_count = max(1, int(args.segment_count))
    args.segment_index = max(1, int(args.segment_index))
    if args.segment_index > args.segment_count:
        print("[ERROR] --segment-index cannot be greater than --segment-count.")
        return 1
    segmented = args.segment_count > 1
    if segmented:
        seg_suffix = f"_seg{args.segment_index}of{args.segment_count}"
        if not args.output_dir.endswith(seg_suffix):
            args.output_dir = args.output_dir + seg_suffix

    print(f"[INFO] Hybrid Independence Test (aggregated {args.iterations}x)")
    print(f"[INFO] Dataset: {args.dataset_dir}")
    print(f"[INFO] LBPH descriptor: {descriptor_metadata['id']} "
          f"(r{descriptor_metadata['radius']}, n{descriptor_metadata['neighbors']}, "
          f"grid={descriptor_metadata['grid_x']}x{descriptor_metadata['grid_y']})")
    if segmented:
        print(f"[INFO] Segment {args.segment_index} of {args.segment_count} "
              f"(query rows only; candidates stay global)")

    mod_name = mod_level = mod_tier = None
    if args.modification:
        mod_name, mod_level = parse_variant(args.modification)
        mod_tier = variant_tier(mod_name, mod_level)
        print(f"[INFO] Modification: {mod_name}:{mod_level} (tier={mod_tier})")

    person_dirs = get_person_dirs(args.dataset_dir)
    if len(person_dirs) < 2:
        print(f"[ERROR] Need >= 2 identity folders under {args.dataset_dir}.")
        return 1

    selection_manifest = None
    selection_manifest_path = None
    selection_manifest_sha256 = None
    if args.selection_manifest:
        selection_manifest_path = resolve_path(args.selection_manifest)
        selection_manifest_sha256 = _sha256_file(selection_manifest_path)
        selection_manifest = load_selection_manifest(
            selection_manifest_path, args.dataset_dir, args.iterations)
        print(f"[INFO] Selection manifest verified: {selection_manifest_path} "
              f"(sha256={selection_manifest_sha256[:12]}...)")
    elif args.max_identities and len(person_dirs) > args.max_identities:
        subset_rng = random.Random(args.random_seed)
        person_dirs = sorted(subset_rng.sample(person_dirs, args.max_identities))
        print(f"[INFO] Seeded identity subset: {len(person_dirs)} of the available folders")

    thresholds_path = resolve_path(args.thresholds_json)
    cfg = load_thresholds(
        thresholds_path,
        expected_lbph_config=descriptor_config,
    )
    gate_thresholds = GateThresholds.from_dict(cfg.get("gate"))
    quality_thresholds = QualityThresholds.from_dict(cfg.get("quality"))
    equalization = SPECS["lbph"].default_equalization
    detector = create_face_detector("yunet")
    sface = SFaceRecognizer()

    # Aggregate per-pair sums INCREMENTALLY (running accumulators) instead of
    # hoarding every iteration's full arrays - keeps peak RAM at O(comparisons),
    # not O(iterations x comparisons).
    probe_cache: dict[str, ProbeData] = {}
    acc: dict[str, np.ndarray] | None = None
    acc_meta: dict = {}
    runs = 0
    iteration_summaries: list[dict] = []

    def _accumulate(rec: dict) -> None:
        nonlocal acc, acc_meta
        m = int(np.asarray(rec["lbph_distance"]).shape[0])
        if acc is None:
            acc = {
                "lbph": np.zeros(m, np.float64), "cos": np.zeros(m, np.float64),
                "l2": np.zeros(m, np.float64), "lbph_fp": np.zeros(m, np.int64),
                "sface_fp": np.zeros(m, np.int64), "both_fp": np.zeros(m, np.int64),
                "cascade_fp": np.zeros(m, np.int64),
            }
            acc_meta = {"query_idx": np.asarray(rec["query_idx"]),
                        "candidate_idx": np.asarray(rec["candidate_idx"]),
                        "names": list(rec["names"])}
        acc["lbph"] += rec["lbph_distance"]
        acc["cos"] += rec["sface_cosine"]
        acc["l2"] += rec["sface_l2"]
        acc["lbph_fp"] += rec["lbph_fp"]
        acc["sface_fp"] += rec["sface_fp"]
        acc["both_fp"] += rec["both_fp"]
        acc["cascade_fp"] += rec["cascade_fp"]

    for it in range(args.iterations):
        print(f"\n[ITERATION {it + 1}/{args.iterations}]")
        run_dir = os.path.join(args.output_dir, "_raw_runs", f"run_{it + 1}")
        csv_path = os.path.join(run_dir, "comparisons.csv")
        npz_path = os.path.join(run_dir, "records.npz")
        summary_path = os.path.join(run_dir, "summary.json")

        # A cached run_N/ only means "same inputs" if dataset/config match too -
        # otherwise switching --dataset-dir (or --max-identities/--thresholds-json)
        # while reusing the same --output-dir would silently resume a run from a
        # different dataset instead of recomputing for the current one.
        run_fingerprint = {
            "dataset_dir": args.dataset_dir,
            "max_identities": args.max_identities,
            "random_seed": args.random_seed + it,
            "thresholds_json": thresholds_path,
            "lbph_config_id": descriptor_metadata["id"],
        }
        # Segmented runs fingerprint their bounds so a cache from a different
        # segment (or an unsegmented run) is never silently resumed.
        if segmented:
            run_fingerprint["segment_count"] = args.segment_count
            run_fingerprint["segment_index"] = args.segment_index
        # Modification/selection-manifest fingerprint keys are only added when
        # the respective flag is set, so unsegmented/unmodified caches from
        # before these flags existed stay valid (never silently reused for a
        # different modification or selection, though).
        if mod_name is not None:
            run_fingerprint["modification"] = {"name": mod_name, "level": mod_level}
        if selection_manifest is not None:
            run_fingerprint["selection_manifest_sha256"] = selection_manifest_sha256

        cached_summary = None
        if os.path.exists(npz_path) and os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                candidate_summary = json.load(f)
            if all(candidate_summary.get(k) == v for k, v in run_fingerprint.items()):
                cached_summary = candidate_summary
            else:
                print(
                    f"  [INFO] Cached iteration {it + 1} was for a different dataset/config "
                    f"(dataset={candidate_summary.get('dataset_dir', 'unknown')}) - recomputing."
                )

        if cached_summary is not None:
            print(f"  [INFO] Resuming complete iteration {it + 1} from {run_dir}")
            summary = cached_summary
            with np.load(npz_path) as data:
                rec_arrays = {k: data[k] for k in data.files}
                rec_arrays["names"] = list(rec_arrays["names"])
        else:
            if selection_manifest is not None:
                selected = selection_from_manifest(selection_manifest, args.dataset_dir, it)
            else:
                selected = select_one_image_per_person(person_dirs, args.random_seed + it)
            modification = (mod_name, mod_level) if mod_name is not None else None
            probes = load_probes(selected, detector, sface, equalization, cache=probe_cache,
                                  modification=modification, mod_seed=args.random_seed)
            if len(probes) < 2:
                print("[WARN] Not enough usable probes; iteration skipped.")
                continue

            seg_start, seg_end = segment_bounds(
                len(probes), args.segment_count, args.segment_index)
            if seg_end <= seg_start:
                print(f"[ERROR] Segment {args.segment_index}/{args.segment_count} is empty "
                      f"for {len(probes)} probes.")
                return 1

            rec_arrays, summary = run_sweep(probes, sface, gate_thresholds, quality_thresholds,
                                            csv_path=csv_path,
                                            seg_start=seg_start, seg_end=seg_end,
                                            lbph_config=descriptor_config)
            summary.update(run_fingerprint)
            if segmented:
                summary["segment"] = {
                    "count": args.segment_count,
                    "index": args.segment_index,
                    "seg_start": seg_start,
                    "seg_end": seg_end,
                    "n_total": len(probes),
                    "query_rows": seg_end - seg_start,
                    "comparisons": summary["comparisons"],
                }
            fp = summary["false_accepts"]
            print(f"  N={summary['identities']} comparisons={summary['comparisons']} | "
                  f"FP: lbph={fp['lbph']} sface={fp['sface']} both={fp['both']} "
                  f"cascade={fp['cascade']} | escalation={summary['gate']['escalation_percent']:.1f}%")

            # Save npz and summary for resuming
            os.makedirs(run_dir, exist_ok=True)
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            np_args = {k: v for k, v in rec_arrays.items() if k != "n"}
            np.savez_compressed(npz_path, **np_args)

        _accumulate(rec_arrays)
        runs += 1
        iteration_summaries.append(summary)
        del rec_arrays  # don't hoard across iterations

    if runs == 0:
        print("[ERROR] No successful iterations.")
        return 1

    aggregated = {
        "mean_lbph_distance": acc["lbph"] / runs,
        "mean_sface_cosine": acc["cos"] / runs,
        "mean_sface_l2": acc["l2"] / runs,
        "lbph_fp_runs": acc["lbph_fp"],
        "sface_fp_runs": acc["sface_fp"],
        "both_fp_runs": acc["both_fp"],
        "cascade_fp_runs": acc["cascade_fp"],
        "query_idx": acc_meta["query_idx"],
        "candidate_idx": acc_meta["candidate_idx"],
        "names": acc_meta["names"],
        "runs": runs,
        "lbph_config": descriptor_metadata,
    }
    comparisons = iteration_summaries[0]["comparisons"]

    def _mean(path_a: str, path_b: str) -> float:
        return float(np.mean([s[path_a][path_b] for s in iteration_summaries]))

    # Rank-based threshold reports on each engine's own impostor scale, from the
    # aggregated mean distances (LBPH: predict distance; SFace: 1 - cosine).
    def _top_pairs(dists: np.ndarray, names: list[str], qi: np.ndarray, cj: np.ndarray, k_max: int) -> list[dict]:
        n_pairs = len(dists)
        k = min(n_pairs, k_max)
        if k == 0:
            return []
        idx = np.argpartition(dists, k - 1)[:k]
        idx = idx[np.argsort(dists[idx])]
        return [
            {
                "raw_distance": float(dists[i]),
                "query_identity": names[int(qi[i])],
                "candidate_identity": names[int(cj[i])],
            }
            for i in idx
        ]

    # Unidirectional: run_sweep still scores every ordered (i, j) pair (the
    # cascade gate needs each probe's full nearest-neighbor row over ALL other
    # identities, so that part can't be halved - see AGENTS.md/skill-map note).
    # But LBPH/SFace raw distances are symmetric (d(i,j) == d(j,i)), so the
    # ordered array holds each impostor pair twice. For the rank-based FAR/
    # threshold report - the thing tau_accept/tau_reject/l2_genuine come from -
    # keep only the upper triangle (query_idx < candidate_idx) so every unique
    # pair is counted once, matching the same unidirectional convention used
    # for the frozen LBPH-only tau_accept (rank-165 unidirectional unique pair).
    qi_all = aggregated["query_idx"]
    cj_all = aggregated["candidate_idx"]
    uni_mask = qi_all < cj_all
    unique_comparisons = int(uni_mask.sum())
    assert unique_comparisons == comparisons // 2, (
        f"expected exactly half of ordered pairs to survive the i<j filter "
        f"(comparisons={comparisons}, kept={unique_comparisons}) - a non-symmetric "
        f"distance would silently corrupt the unidirectional rank report"
    )
    print(f"[INFO] Unidirectional unique pairs: {unique_comparisons} "
          f"(of {comparisons} ordered)")

    top_k = min(unique_comparisons, 500000)
    lbph_pairs = _top_pairs(
        aggregated["mean_lbph_distance"][uni_mask], aggregated["names"],
        qi_all[uni_mask], cj_all[uni_mask], top_k
    )
    sface_pairs = _top_pairs(
        1.0 - aggregated["mean_sface_cosine"][uni_mask], aggregated["names"],
        qi_all[uni_mask], cj_all[uni_mask], top_k
    )

    lbph_rank_report = error_pair_report(
        lbph_pairs, target_far_ppm=args.target_far_ppm, explicit_rank=args.error_pair_rank)
    sface_rank_report = error_pair_report(
        sface_pairs, target_far_ppm=args.target_far_ppm, explicit_rank=args.error_pair_rank)
    if top_k < unique_comparisons:
        # error_pair_report's FAR%/rank math is computed against len(records) -
        # i.e. against top_k, not the true unique_comparisons - so anything
        # beyond the top-500k pool silently underreports FAR by unique_comparisons
        # / top_k. Ranks up to top_k are unaffected; flag it instead of
        # miscomputing quietly further downstream (docs/READ THIS notes this too).
        print(f"[WARN] unique_comparisons ({unique_comparisons}) exceeds the "
              f"{top_k}-pair rank-report pool - realized_far_ppm in "
              f"lbph_rank_thresholds/sface_rank_thresholds is only valid for "
              f"ranks <= {top_k}; recompute FAR = rank / {unique_comparisons} "
              f"manually for anything reported from this run.")


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
        "lbph_config": descriptor_metadata,
        "iterations": len(iteration_summaries),
        "comparisons_per_iteration": comparisons,
        "comparison": {
            "expected_comparisons": iteration_summaries[0]["identities"] * (iteration_summaries[0]["identities"] - 1),
            "actual_comparisons": comparisons,
        },
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
    if segmented:
        summary["segment"] = iteration_summaries[0].get("segment")
    if mod_name is not None:
        summary["modification"] = {"name": mod_name, "level": mod_level, "tier": mod_tier}
    if selection_manifest is not None:
        summary["selection_manifest"] = {
            "path": selection_manifest_path, "sha256": selection_manifest_sha256,
        }

    if args.plots:
        summary["plots"] = _write_hybrid_plots(args, aggregated, lbph_rank_report, sface_rank_report)

    save_aggregated_csv(aggregated, os.path.join(args.output_dir, "comparisons.csv"))
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
    plots = summary.get("plots") or {}
    if plots:
        print("[PLOTS]")
        for key, val in plots.items():
            print(f"  {key}: {val}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
