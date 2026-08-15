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
import csv
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
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "utils"))  # setup_datasets.py lives here, not scripts/pipeline
from main import build_subprocess_env, describe_hardware_profile, load_or_build_hardware_profile  # noqa: E402
from setup_datasets import setup_lfw  # noqa: E402
from src.independence_common import (  # noqa: E402
    create_lbph_recognizer_for_config,
    lbph_config_metadata,
    resolve_lbph_config,
)


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
        "--lbph-config",
        default=None,
        help="LBPH descriptor config ID/alias (default: active deployed config; "
             "e.g. r3_n8_g6x6 or selected). Included in enrollment cache keys "
             "and segment-resume validation.",
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
    parser.add_argument(
        "--split-manifest",
        default=None,
        help="Path to an lsface-lfw-ident-split-v1 manifest (see "
             "scripts/utils/make_lfw_identification_split.py). When given, enrollment "
             "uses the manifest's GALLERY images (one per identity, including "
             "singletons) and probes are the manifest's disjoint PROBE images - the "
             "fixed gallery/probe-disjoint protocol (docs/audits/STATE-08-01.md). "
             "When omitted, falls back to the original same-image "
             "select_originals(...) path (reported as transform_sensitivity, not "
             "Accuracy Ratio) for backward compatibility with old report reruns.",
    )
    parser.add_argument(
        "--mod-set",
        choices=["legacy", "dl41"],
        default="dl41",
        help="Forwarded to accuracy_ratio_hybrid --mod-set (default dl41).",
    )
    parser.add_argument(
        "--headline-scope",
        choices=["all41", "exclude-canonical"],
        default="all41",
        help="Forwarded to accuracy_ratio_hybrid --headline-scope. all41 (default): "
             "the headline mean covers all 41 dl41 variants, comparable to the DL "
             "team's ar-table.py. exclude-canonical: drop rot_90/180/270 and flip_lr "
             "from the headline mean (they are broken out separately either way).",
    )
    parser.add_argument(
        "--limit-identities",
        type=int,
        default=0,
        help="Debug/smoke-test only: forwarded to accuracy_ratio_hybrid --limit-identities "
             "(0 = all). Also caps enrollment to the same identities.",
    )
    parser.add_argument(
        "--no-face-policy",
        choices=["fallback", "strict"],
        default=None,
        help="Forwarded to accuracy_ratio_hybrid --no-face-policy. Default: "
             "accuracy_ratio_hybrid's own default (fallback). Recommended 'strict' "
             "for headline --mod-set dl41 runs (detection failure is a genuine "
             "system failure under that taxonomy).",
    )
    parser.add_argument(
        "--lbph-assume-cropped",
        choices=["true", "false"],
        default="false",
        help="Forwarded to accuracy_ratio_hybrid --lbph-assume-cropped, and also "
             "controls enrollment (ensure_lfw2_enrollment). 'true': pre-cropped tile "
             "datasets (e.g. data/lasalle_db1_processed) need true. 'false' "
             "(default): raw LFW frames need false, so LBPH uses the detected YuNet "
             "face box instead of the whole 250x250 frame.",
    )
    return parser.parse_args()


def _sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def enrollment_cache_paths(
    seed: int,
    split_manifest_sha: str | None,
    assume_cropped: bool,
    lbph_config=None,
) -> tuple[dict[str, Path], Path, dict]:
    """Return config-keyed enrollment paths and the expected descriptor metadata."""
    descriptor_metadata = lbph_config_metadata(lbph_config)
    manifest_suffix = (
        f"_manifest{split_manifest_sha[:12]}" if split_manifest_sha else ""
    )
    crop_token = "_fullframe" if assume_cropped else "_boxcrop"
    config_token = f"_cfg-{descriptor_metadata['id']}"
    suffix = f"{config_token}_seed{seed}{manifest_suffix}{crop_token}"
    paths = {
        "lbph_model": ENROLL_DIR / f"lbph_{suffix}.yml",
        "lbph_labels": ENROLL_DIR / f"lbph_labels_{suffix}.json",
        "sface_gallery": ENROLL_DIR / f"sface_gallery_{suffix}.npy",
        "sface_labels": ENROLL_DIR / f"sface_labels_{suffix}.json",
    }
    manifest_path = ENROLL_DIR / f"manifest_{suffix}.json"
    return paths, manifest_path, descriptor_metadata


def segment_outputs_match(seg_json: Path, seg_csv: Path, descriptor_id: str) -> bool:
    """Validate a segment pair before resume; legacy outputs lack this proof."""
    try:
        payload = json.loads(seg_json.read_text(encoding="utf-8"))
        payload_config = payload.get("lbph_config") or {}
        if payload_config.get("id") != descriptor_id:
            return False
        with seg_csv.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if "lbph_config_id" not in (reader.fieldnames or []):
                return False
            return all(row.get("lbph_config_id") == descriptor_id for row in reader)
    except (json.JSONDecodeError, OSError, UnicodeError):
        return False


def ensure_lfw2_enrollment(
    lfw_root: Path,
    seed: int,
    split_manifest_path: str | None = None,
    limit_identities: int = 0,
    assume_cropped: bool = False,
    lbph_config=None,
) -> dict[str, str]:
    """Train/enroll LBPH + SFace on LFW2 and cache the artifacts under
    models/lfw2/. A matching cache is reused; delete the files to force re-enroll.

    Two enrollment sources:

    * ``split_manifest_path`` given: enroll from the manifest's GALLERY images
      (``scripts/utils/make_lfw_identification_split.py`` output) - disjoint
      from the probes the benchmark will score (docs/audits/STATE-08-01.md).
      The cache key includes the manifest's own ``triples_sha256`` (not just
      lfw_root/seed) so a stale ``manifest_seed{seed}.json`` cache can never be
      silently reused against a DIFFERENT split manifest that happens to share
      the same seed.
    * omitted: the original same-image ``select_originals(..., seed=seed)``
      path (backward compatible with old transform_sensitivity reruns).

    ``assume_cropped`` must mirror the benchmark's own ``--lbph-assume-cropped``
    (accuracy_ratio_hybrid.py): it controls whether LBPH enrolls on the whole
    frame or the detected YuNet face box, and is baked into the cache filenames
    (``_fullframe`` / ``_boxcrop``) AND the cached-manifest match check below,
    so the two crop modes never silently reuse each other's LBPH model.
    """
    descriptor_config = resolve_lbph_config(lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)
    split_manifest_sha = None
    if split_manifest_path is not None:
        split_manifest_sha = _sha256_file(Path(split_manifest_path))
    paths, manifest_path, descriptor_metadata = enrollment_cache_paths(
        seed, split_manifest_sha, assume_cropped, descriptor_config
    )
    if manifest_path.exists() and all(p.exists() for p in paths.values()):
        cached = json.loads(manifest_path.read_text(encoding="utf-8"))
        matches = (
            cached.get("lfw_root") == str(lfw_root)
            and cached.get("seed") == seed
            and cached.get("split_manifest_sha256") == split_manifest_sha
            and cached.get("limit_identities", 0) == limit_identities
            and cached.get("assume_cropped", False) == assume_cropped
            and cached.get("lbph_config") == descriptor_metadata
        )
        if matches:
            print(f"[ENROLL] Reusing cached LFW2 enrollment "
                  f"({cached['identities']} identities) in {ENROLL_DIR}")
            return {k: str(v) for k, v in paths.items()}
        print("[ENROLL] Cached manifest does not match root/seed/split-manifest/crop-mode/descriptor; re-enrolling.")

    sys.path.insert(0, str(PROJECT_ROOT))
    import cv2 as cv
    import numpy as np
    from src.benchmark.accuracy_ratio_hybrid import (
        load_gallery_from_manifest,
        load_split_manifest,
        select_originals,
    )
    from src.classical_faces.detection import create_face_detector
    from src.classical_faces.pipeline import SPECS
    from src.classical_faces.preprocess import IMG_SIZE, normalize_face
    from src.hybrid.recognizer import detect_sample
    from src.sface.recognizer import SFaceGallery, SFaceRecognizer, default_sface_model_path

    if split_manifest_path is not None:
        split_manifest = load_split_manifest(split_manifest_path)
        selection = load_gallery_from_manifest(split_manifest)
        print(f"[ENROLL] Enrolling from split manifest {split_manifest_path} "
              f"(gallery images, disjoint from probes)...")
    else:
        selection = select_originals(str(lfw_root), select_one_per_person=True, seed=seed)
    if limit_identities:
        selection = selection[:limit_identities]
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
        # Mirror the benchmark probe path exactly: assume_cropped controls whether
        # LBPH sees the whole tile normalized (True, pre-cropped tile datasets) or
        # the detected YuNet face box (False, raw LFW frames); SFace always
        # align-crops via YuNet landmarks regardless.
        sample = detect_sample(detector, image_bgr=img, image_gray=gray, assume_cropped=assume_cropped)
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
    recognizer = create_lbph_recognizer_for_config(descriptor_config)
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
        "selection": (
            "split-manifest gallery images (disjoint from probes)"
            if split_manifest_path is not None
            else "one image per person, same seeded pick as the benchmark probes "
                 "(transform_sensitivity path - see docs/audits/STATE-08-01.md)"
        ),
        "split_manifest_path": split_manifest_path,
        "split_manifest_sha256": split_manifest_sha,
        "limit_identities": limit_identities,
        "assume_cropped": assume_cropped,
        "lbph_config": descriptor_metadata,
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
    descriptor_id: str,
) -> tuple[int, Path, Path]:
    seg_json = output_dir / f"accuracy_ratio_hybrid_seg{segment_index}of{num_segments}.json"
    seg_md = output_dir / f"accuracy_ratio_hybrid_seg{segment_index}of{num_segments}.md"
    seg_csv = output_dir / f"accuracy_ratio_hybrid_seg{segment_index}of{num_segments}_probes.csv"

    # Resume only when both outputs prove the same descriptor was used.
    if seg_json.exists() and seg_csv.exists():
        if segment_outputs_match(seg_json, seg_csv, descriptor_id):
            print(f"[WORKER {segment_index}/{num_segments}] Already complete - skipping (resume).")
            return segment_index, seg_json, seg_csv
        print(f"[WORKER {segment_index}/{num_segments}] Stale/config-mismatched output - re-running.")

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


def _manifest_probe_count(split_manifest: str | None, limit_identities: int) -> int:
    """Number of probe rows the benchmark will actually process, mirroring
    accuracy_ratio_hybrid's own manifest path (including the
    --limit-identities gallery intersection). 0 when not running the manifest
    protocol, in which case the caller leaves the segment count alone."""
    if not split_manifest:
        return 0
    path = Path(split_manifest)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return 0
    manifest = json.loads(path.read_text(encoding="utf-8"))
    identities = manifest.get("identities", {})
    people = sorted(identities)
    if limit_identities:
        enrolled = {p for p in people if identities[p].get("gallery")}
        people = [p for p in people if p in enrolled][:limit_identities]
    count = 0
    for person in people:
        entry = identities[person]
        rels = entry.get("probes")
        if rels is None:
            single = entry.get("probe")
            rels = [single] if single else []
        count += len(rels)
    return count


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
    descriptor_config = resolve_lbph_config(args.lbph_config)
    descriptor_metadata = lbph_config_metadata(descriptor_config)
    num_segments = args.num_segments or max(16, requested_workers)
    # segment_bounds() sizes every segment as ceil(n/k), so the first k-1
    # segments can already cover all n probes and leave the last one an EMPTY
    # slice - the benchmark then divides by len(originals) to build ar_percent
    # and dies with ZeroDivisionError, killing the whole run. Shrink k until
    # the tail segment has work. Bites on small --limit-identities smoke runs
    # (500 gallery identities intersect to 147 probes: ceil(147/16)*15 = 150 >
    # 147); a full 1,680-probe run is unaffected (ceil(1680/16)*15 = 1575).
    n_probes = _manifest_probe_count(args.split_manifest, args.limit_identities)
    if n_probes:
        capped = num_segments
        while capped > 1 and ((n_probes + capped - 1) // capped) * (capped - 1) >= n_probes:
            capped -= 1
        if capped != num_segments:
            print(f"[INFO] Capping segments {num_segments} -> {capped}: {n_probes} probes "
                  f"would leave the tail segment(s) empty.")
            num_segments = capped
    num_workers = min(requested_workers, num_segments)

    print(f"=== LFW2 41-Modification Hybrid Robustness Harness ===")
    print(f"Dataset Root: {lfw_path}")
    print(f"Workers: {num_workers} | Segments: {num_segments} (finished segments are skipped on re-launch)")
    print(f"Output Dir: {out_dir}")
    print(f"Seed: {args.seed}")
    print(f"LBPH descriptor: {descriptor_metadata['id']} "
          f"(r{descriptor_metadata['radius']}, n{descriptor_metadata['neighbors']}, "
          f"grid={descriptor_metadata['grid_x']}x{descriptor_metadata['grid_y']})")
    print(f"Split manifest: {args.split_manifest or '(none - legacy same-image path)'}")
    print(f"Mod set: {args.mod_set}")

    # LFW2 needs LFW2-enrolled models (the benchmark defaults are La Salle-enrolled,
    # which scores all zeroes here). Auto-enroll + cache unless explicitly overridden.
    # Cache key includes the split manifest's own sha256 (ensure_lfw2_enrollment) so a
    # stale models/lfw2/manifest_seed{seed}*.json can never be silently reused against
    # a different split manifest sharing the same seed.
    lbph_assume_cropped = args.lbph_assume_cropped == "true"
    if args.lbph_model is None or args.sface_gallery is None:
        enrolled = ensure_lfw2_enrollment(
            lfw_path, args.seed,
            split_manifest_path=args.split_manifest,
            limit_identities=args.limit_identities,
            assume_cropped=lbph_assume_cropped,
            lbph_config=descriptor_config,
        )
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
        ("--mod-set", args.mod_set),
        ("--headline-scope", args.headline_scope),
        ("--split-manifest", args.split_manifest),
        ("--no-face-policy", args.no_face_policy),
        ("--lbph-assume-cropped", args.lbph_assume_cropped),
        ("--lbph-config", descriptor_metadata["id"]),
    ):
        if value is not None:
            passthrough.extend([flag, value])
    if args.limit_identities:
        passthrough.extend(["--limit-identities", str(args.limit_identities)])
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
                descriptor_metadata["id"],
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
