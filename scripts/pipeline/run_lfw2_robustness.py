#!/usr/bin/env python3
"""Run the 41-modification hybrid robustness benchmark on LFW2 across parallel worker segments.

Usage:
    python scripts/pipeline/run_lfw2_robustness.py \\
        --lfw-root data/lfw-dataset \\
        --num-workers 4 \\
        --output-dir reports/benchmark/lfw2_robustness
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENROLL_DIR = PROJECT_ROOT / "models" / "lfw2"
DEFAULT_LFW_ROOT = PROJECT_ROOT / "data" / "lfw-dataset"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from main import build_subprocess_env, describe_hardware_profile, load_or_build_hardware_profile  # noqa: E402
from setup_datasets import setup_lfw  # noqa: E402


def ensure_dependencies() -> None:
    """Standalone entrypoint: pip-install requirements.txt if numpy/cv2 aren't
    importable yet, instead of dying halfway through enrollment with ModuleNotFoundError."""
    if importlib.util.find_spec("numpy") and importlib.util.find_spec("cv2"):
        return
    req_file = PROJECT_ROOT / "requirements.txt"
    print(f"[INFO] numpy/cv2 not found; installing dependencies from {req_file}...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)], check=True)
    importlib.invalidate_caches()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parallel multi-worker harness for LFW2 41-modification robustness testing."
    )
    parser.add_argument(
        "--lfw-root",
        default="data/lfw-dataset",
        help="Path to unaugmented LFW dataset directory (5,749 identity folders).",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=None,
        help="Max parallel worker processes. Each worker loads the full LBPH model "
             "(~1 GB .yml for all-LFW enrollment), so cap this by RAM, not cores. "
             "Default: auto from the detected hardware profile (see main.py hw menu).",
    )
    parser.add_argument(
        "--num-segments",
        type=int,
        default=0,
        help="Total probe segments (0 = auto: max(16, num-workers)). Finished segment "
             "outputs are skipped on re-launch, so more segments = finer resume "
             "granularity after an interrupt. Delete a segment's files to redo it.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/benchmark/lfw2_robustness",
        help="Directory to store segment JSONs and merged output.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for single image per person selection and modification probes.",
    )
    parser.add_argument(
        "--modes",
        default=None,
        help="Comma list forwarded to accuracy_ratio_hybrid (e.g. dl_only,cascade). "
             "Default: benchmark's own default (all three modes).",
    )
    parser.add_argument(
        "--lbph-model",
        default=None,
        help="LBPH model .yml forwarded to accuracy_ratio_hybrid. Default: auto-enrolled "
             "LFW2 model cached under models/lfw2/.",
    )
    parser.add_argument(
        "--lbph-labels",
        default=None,
        help="LBPH labels .json forwarded to accuracy_ratio_hybrid (pair of --lbph-model).",
    )
    parser.add_argument(
        "--sface-gallery",
        default=None,
        help="SFace gallery .npy forwarded to accuracy_ratio_hybrid. Default: auto-enrolled "
             "LFW2 gallery cached under models/lfw2/.",
    )
    parser.add_argument(
        "--thresholds-json",
        default=None,
        help="Thresholds JSON forwarded to accuracy_ratio_hybrid (default: frozen hybrid thresholds).",
    )
    return parser.parse_args()


def ensure_lfw2_enrollment(lfw_root: Path, seed: int) -> dict[str, str]:
    """Train/enroll LBPH + SFace on LFW2 (one clean image per identity, the same
    seeded selection the benchmark probes use) and cache the artifacts under
    models/lfw2/. A matching cache is reused; delete the files to force re-enroll."""
    paths = {
        "lbph_model": ENROLL_DIR / f"lbph_seed{seed}.yml",
        "lbph_labels": ENROLL_DIR / f"lbph_labels_seed{seed}.json",
        "sface_gallery": ENROLL_DIR / f"sface_gallery_seed{seed}.npy",
        "sface_labels": ENROLL_DIR / f"sface_labels_seed{seed}.json",
    }
    manifest_path = ENROLL_DIR / f"manifest_seed{seed}.json"
    if manifest_path.exists() and all(p.exists() for p in paths.values()):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("lfw_root") == str(lfw_root) and manifest.get("seed") == seed:
            print(f"[ENROLL] Reusing cached LFW2 enrollment "
                  f"({manifest['identities']} identities) in {ENROLL_DIR}")
            return {k: str(v) for k, v in paths.items()}
        print("[ENROLL] Cached manifest does not match this root/seed; re-enrolling.")

    sys.path.insert(0, str(PROJECT_ROOT))
    import cv2 as cv
    import numpy as np
    from src.benchmark.accuracy_ratio_hybrid import select_originals
    from src.classical_faces.detection import create_face_detector
    from src.classical_faces.pipeline import SPECS
    from src.classical_faces.preprocess import IMG_SIZE, normalize_face
    from src.hybrid.recognizer import detect_sample
    from src.sface.recognizer import SFaceGallery, SFaceRecognizer, default_sface_model_path

    selection = select_originals(str(lfw_root), select_one_per_person=True, seed=seed)
    if not selection:
        raise RuntimeError(f"No identity folders with images under {lfw_root}")
    print(f"[ENROLL] Enrolling {len(selection)} identities (one clean image each, seed={seed})...")

    detector = create_face_detector("yunet")
    sface = SFaceRecognizer(default_sface_model_path())
    equalization = SPECS["lbph"].default_equalization

    faces: list[np.ndarray] = []
    labels: list[int] = []
    label_map: dict[str, int] = {}
    embeddings: dict[str, list[np.ndarray]] = {}
    yunet_misses = 0
    for i, (person, path) in enumerate(selection, 1):
        img = cv.imread(path)
        if img is None:
            continue
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        # Mirror the benchmark probe path exactly: assume_cropped=True means LBPH
        # sees the whole tile normalized; SFace align-crops via YuNet landmarks.
        sample = detect_sample(detector, image_bgr=img, image_gray=gray, assume_cropped=True)
        if sample is None:
            face_gray = gray
            feature = sface.feature_from_crop(img)
            yunet_misses += 1
        else:
            face_gray = sample.face_gray
            feature = (
                sface.feature_from_row(sample.image_bgr, sample.yunet_row)
                if sample.yunet_row is not None
                else sface.feature_from_crop(sample.image_bgr)
            )
        label_map[person] = len(label_map)
        faces.append(normalize_face(face_gray, img_size=IMG_SIZE, equalization=equalization))
        labels.append(label_map[person])
        embeddings[person] = [feature]
        if i % 500 == 0:
            print(f"[ENROLL] {i}/{len(selection)} identities embedded...")

    if len(faces) < 2:
        raise RuntimeError("Not enough valid LFW2 images to enroll.")

    print(f"[ENROLL] Training LBPH on {len(faces)} faces (this writes a large .yml)...")
    recognizer = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(faces, np.array(labels, dtype=np.int32))

    ENROLL_DIR.mkdir(parents=True, exist_ok=True)
    recognizer.save(str(paths["lbph_model"]))
    paths["lbph_labels"].write_text(json.dumps(label_map, indent=2), encoding="utf-8")
    SFaceGallery.from_samples(sface, embeddings).save(
        str(paths["sface_gallery"]), str(paths["sface_labels"])
    )
    manifest_path.write_text(json.dumps({
        "lfw_root": str(lfw_root),
        "seed": seed,
        "identities": len(label_map),
        "selection": "one image per person, same seeded pick as the benchmark probes",
        "equalization": equalization,
        "yunet_misses_whole_tile_fallback": yunet_misses,
        "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2), encoding="utf-8")
    print(f"[ENROLL] Done. Cached in {ENROLL_DIR} (YuNet misses: {yunet_misses})")
    return {k: str(v) for k, v in paths.items()}


def run_segment(
    segment_index: int,
    num_segments: int,
    lfw_root: str,
    output_dir: Path,
    seed: int,
    passthrough: list[str],
    env: dict[str, str],
) -> tuple[int, Path, Path]:
    seg_json = output_dir / f"accuracy_ratio_hybrid_seg{segment_index}of{num_segments}.json"
    seg_md = output_dir / f"accuracy_ratio_hybrid_seg{segment_index}of{num_segments}.md"
    seg_csv = output_dir / f"accuracy_ratio_hybrid_seg{segment_index}of{num_segments}_probes.csv"

    # Resume: a finished segment left a valid JSON + CSV pair; skip re-running it.
    if seg_json.exists() and seg_csv.exists():
        try:
            json.loads(seg_json.read_text(encoding="utf-8"))
            print(f"[WORKER {segment_index}/{num_segments}] Already complete - skipping (resume).")
            return segment_index, seg_json, seg_csv
        except (json.JSONDecodeError, OSError):
            print(f"[WORKER {segment_index}/{num_segments}] Stale/corrupt output - re-running.")

    cmd = [
        sys.executable,
        "-m",
        "src.benchmark.accuracy_ratio_hybrid",
        "--originals-dir",
        lfw_root,
        "--select-one-per-person",
        "--seed",
        str(seed),
        "--segment-count",
        str(num_segments),
        "--segment-index",
        str(segment_index),
        "--output-json",
        str(seg_json),
        "--output-md",
        str(seg_md),
        "--battery-csv",
        str(seg_csv),
        *passthrough,
    ]

    print(f"[WORKER {segment_index}/{num_segments}] Launching segment {segment_index}...")
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, env=env)
    if res.returncode != 0:
        print(f"[ERROR Worker {segment_index}] Standard Error:\n{res.stderr}")
        raise RuntimeError(f"Worker {segment_index} failed with code {res.returncode}")

    print(f"[WORKER {segment_index}/{num_segments}] Finished segment {segment_index}.")
    return segment_index, seg_json, seg_csv


def main() -> int:
    ensure_dependencies()
    args = parse_args()
    lfw_path = PROJECT_ROOT / args.lfw_root if not Path(args.lfw_root).is_absolute() else Path(args.lfw_root)
    if lfw_path.resolve() == DEFAULT_LFW_ROOT.resolve():
        # Downloads + extracts data/lfw-dataset (5,749 identities) if missing or incomplete.
        setup_lfw()
    if not lfw_path.exists():
        raise RuntimeError(f"LFW root dataset path does not exist: {lfw_path}")

    out_dir = PROJECT_ROOT / args.output_dir if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Same CPU/RAM-tiered profile main.py uses for every other run: caps BLAS/OpenMP
    # threads per process so num_workers x unrestricted BLAS threads can't oversubscribe
    # the machine, and sizes num_workers itself when not explicitly overridden.
    hardware_profile = load_or_build_hardware_profile()
    print(f"[INFO] Detected {describe_hardware_profile(hardware_profile)}")
    env = build_subprocess_env(hardware_profile)
    os.environ.update({k: v for k, v in env.items() if k not in os.environ})

    requested_workers = args.num_workers if args.num_workers is not None else hardware_profile["workers"]
    num_segments = args.num_segments or max(16, requested_workers)
    num_workers = min(requested_workers, num_segments)

    print(f"=== LFW2 41-Modification Hybrid Robustness Harness ===")
    print(f"Dataset Root: {lfw_path}")
    print(f"Workers: {num_workers} | Segments: {num_segments} (finished segments are skipped on re-launch)")
    print(f"Output Dir: {out_dir}")
    print(f"Seed: {args.seed}")

    # LFW2 needs LFW2-enrolled models (the benchmark defaults are La Salle-enrolled,
    # which scores all zeroes here). Auto-enroll + cache unless explicitly overridden.
    if args.lbph_model is None or args.sface_gallery is None:
        enrolled = ensure_lfw2_enrollment(lfw_path, args.seed)
        if args.lbph_model is None:
            args.lbph_model = enrolled["lbph_model"]
            if args.lbph_labels is None:
                args.lbph_labels = enrolled["lbph_labels"]
        if args.sface_gallery is None:
            args.sface_gallery = enrolled["sface_gallery"]

    passthrough: list[str] = []
    for flag, value in (
        ("--modes", args.modes),
        ("--lbph-model", args.lbph_model),
        ("--lbph-labels", args.lbph_labels),
        ("--sface-gallery", args.sface_gallery),
        ("--thresholds-json", args.thresholds_json),
    ):
        if value is not None:
            passthrough.extend([flag, value])
    # AR/battery run, not a latency run: share engine scores across modes (~3x less work).
    passthrough.append("--reuse-engine-scores")

    seg_jsons: list[Path] = []
    seg_csvs: list[Path] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(
                run_segment,
                seg_idx,
                num_segments,
                str(lfw_path),
                out_dir,
                args.seed,
                passthrough,
                env,
            )
            for seg_idx in range(1, num_segments + 1)
        ]

        for future in concurrent.futures.as_completed(futures):
            seg_idx, seg_json, seg_csv = future.result()
            seg_jsons.append(seg_json)
            seg_csvs.append(seg_csv)

    print("\n[INFO] All segments completed. Merging segment results...")
    merged_json = out_dir / "accuracy_ratio_hybrid.json"
    merged_md = out_dir / "accuracy_ratio_hybrid.md"

    merge_cmd = [
        sys.executable,
        "scripts/utils/merge_robustness_segments.py",
        "--segment-jsons",
        *[str(p) for p in sorted(seg_jsons)],
        "--battery-csvs",
        *[str(p) for p in sorted(seg_csvs)],
        "--output-json",
        str(merged_json),
        "--output-md",
        str(merged_md),
        "--output-battery-csv",
        str(out_dir / "accuracy_ratio_hybrid_probes.csv"),
    ]

    res = subprocess.run(merge_cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, env=env)
    if res.returncode != 0:
        print(f"[ERROR Merge] Standard Error:\n{res.stderr}")
        raise RuntimeError(f"Merge step failed with code {res.returncode}")

    print(f"[SUCCESS] Harness complete! Unified report created at:")
    print(f"  - {merged_json}")
    print(f"  - {merged_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
