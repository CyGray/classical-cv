"""Face-detector benchmark: Viola-Jones (Haar) vs YuNet (CNN).

Runs both detection backends over the same image sample and measures the metrics
that decide the face-detection stage (briefing milestone ~6/16): detection rate,
false-positive proxy, speed, face-size yield, confidence and model footprint.
Writes ``reports/benchmark/detector_comparison_<dataset>.{json,md}``.

Both classical evaluation datasets are single-face per image (La Salle = one
subject per photo; LFW = one labelled face per photo), so on this sample:

* **Detection rate** = images with >=1 detected face = a recall proxy (a face is
  always present, so a miss is a false negative).
* **Extra detections** = sum of ``max(0, faces - 1)`` per image = a
  false-positive proxy (any face past the first on a single-face photo).

Detection time is measured **separately from image decode** (``cv.imread`` of a
48 MP La Salle JPEG dwarfs detection), so the speed column reflects the detector,
not disk I/O. Run it twice to cover both datasets, e.g.::

    python src/benchmark/compare_detectors.py --dataset lasalle_db1
    python src/benchmark/compare_detectors.py --dataset lfw-dataset --max-images 600
"""

import argparse
import json
import random
import statistics
import time
from pathlib import Path

import cv2 as cv
import numpy as np

from src.classical_faces.detection import (
    DEFAULT_YUNET_NMS_THRESHOLD,
    DEFAULT_YUNET_SCORE_THRESHOLD,
    create_face_detector,
)
from src.classical_faces.preprocess import maybe_downscale

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
BACKENDS = ("haar", "yunet")


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def resolve_path(path_value: str) -> str:
    candidate = Path(path_value)
    return str(candidate if candidate.is_absolute() else PROJECT_ROOT / candidate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Haar vs YuNet face detection.")
    parser.add_argument(
        "--dataset",
        default="lasalle_db1",
        help="Dataset folder under data/ (or an absolute path). Default: lasalle_db1.",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="Cap the image sample (0 = all). LFW is large; 400-800 is plenty.",
    )
    parser.add_argument(
        "--downscale-max-side",
        type=int,
        default=640,
        help="Longest side fed to the detector (0 = native). La Salle raw is 6928px; "
        "640 mirrors the live loop and keeps both detectors fast and fair.",
    )
    parser.add_argument("--min-face-size", type=int, default=20)
    parser.add_argument("--scale-factor", type=float, default=1.1)
    parser.add_argument("--min-neighbors", type=int, default=5)
    parser.add_argument("--yunet-score-threshold", type=float, default=DEFAULT_YUNET_SCORE_THRESHOLD)
    parser.add_argument("--yunet-nms-threshold", type=float, default=DEFAULT_YUNET_NMS_THRESHOLD)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    return parser.parse_args()


def gather_images(dataset_dir: Path, max_images: int, seed: int) -> list[Path]:
    files = [
        p
        for p in dataset_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    files.sort()
    if max_images and len(files) > max_images:
        rng = random.Random(seed)
        files = sorted(rng.sample(files, max_images))
    return files


def model_size_bytes(backend: str, detector) -> int:
    if backend == "yunet":
        try:
            return int(Path(detector.model_path).stat().st_size)
        except OSError:
            return 0
    from src.classical_faces.detection import DEFAULT_HAAR_CASCADE_PATH

    try:
        return int(Path(DEFAULT_HAAR_CASCADE_PATH).stat().st_size)
    except OSError:
        return 0


def benchmark_backend(backend: str, images: list[Path], gray_cache: dict, bgr_cache: dict, scale_cache: dict, args) -> dict:
    # Images are pre-downscaled in main(), so the detector runs with no further
    # resize (downscale_max_side=0) and the timed region is pure detection.
    detector = create_face_detector(
        backend,
        min_face_size=args.min_face_size,
        scale_factor=args.scale_factor,
        min_neighbors=args.min_neighbors,
        downscale_max_side=0,
        yunet_score_threshold=args.yunet_score_threshold,
        yunet_nms_threshold=args.yunet_nms_threshold,
    )

    found = 0
    exactly_one = 0
    total_boxes = 0
    extra_boxes = 0
    images_with_extra = 0
    detect_ms: list[float] = []
    face_sides: list[float] = []
    scores: list[float] = []

    # Warm up so lazy kernels / first-call overhead don't skew the first sample.
    if images:
        detector.detect(gray_cache[images[0]], image_bgr=bgr_cache[images[0]])

    for path in images:
        gray = gray_cache[path]
        bgr = bgr_cache[path]
        scale = scale_cache[path]  # detector-frame px -> native px factor
        inv = (1.0 / scale) if scale not in (0.0, 1.0) else 1.0
        t0 = time.perf_counter()
        dets = detector.detect(gray, image_bgr=bgr)
        detect_ms.append((time.perf_counter() - t0) * 1000.0)

        n = len(dets)
        total_boxes += n
        if n >= 1:
            found += 1
            largest = max(dets, key=lambda d: d.area)
            face_sides.append(0.5 * (largest.box[2] + largest.box[3]) * inv)
            scores.append(float(largest.score))
        if n == 1:
            exactly_one += 1
        if n > 1:
            extra_boxes += n - 1
            images_with_extra += 1

    n_images = len(images)
    mean_ms = statistics.mean(detect_ms) if detect_ms else 0.0
    return {
        "backend": backend,
        "detector": detector.describe(),
        "images": n_images,
        "found": found,
        "detection_rate_percent": (100.0 * found / n_images) if n_images else 0.0,
        "exactly_one_face": exactly_one,
        "single_face_rate_percent": (100.0 * exactly_one / n_images) if n_images else 0.0,
        "total_boxes": total_boxes,
        "extra_detections": extra_boxes,
        "images_with_extra_detections": images_with_extra,
        "false_positive_rate_percent": (100.0 * images_with_extra / n_images) if n_images else 0.0,
        "mean_detect_ms": mean_ms,
        "median_detect_ms": statistics.median(detect_ms) if detect_ms else 0.0,
        "detect_fps": (1000.0 / mean_ms) if mean_ms > 0 else 0.0,
        "mean_face_side_px": statistics.mean(face_sides) if face_sides else 0.0,
        "mean_confidence": (statistics.mean(scores) if scores else None) if backend == "yunet" else None,
        "provides_landmarks": backend == "yunet",
        "model_file_bytes": model_size_bytes(backend, detector),
    }


def _fmt_kb(num_bytes: int) -> str:
    return f"{num_bytes / 1024.0:.0f} KB" if num_bytes else "n/a"


def to_markdown(summary: dict) -> str:
    rows = {r["backend"]: r for r in summary["rows"]}
    haar = rows.get("haar", {})
    yunet = rows.get("yunet", {})

    def cell(row: dict, key: str, fmt: str, scale: float = 1.0, suffix: str = "") -> str:
        value = row.get(key)
        if value is None:
            return "n/a"
        return f"{value * scale:{fmt}}{suffix}"

    lines: list[str] = []
    lines.append(f"# Detector Comparison - Haar (Viola-Jones) vs YuNet ({summary['dataset']})")
    lines.append("")
    lines.append(
        f"Sample: **{summary['images']} images** from `data/{summary['dataset']}` "
        f"({summary['image_note']}), detector input downscaled to a "
        f"**{summary['downscale_max_side']} px** longest side. Detection time excludes image decode."
    )
    lines.append("")
    lines.append("| Metric | Viola-Jones (Haar) | YuNet (CNN) | Better |")
    lines.append("|---|---:|---:|:--:|")

    def line(label: str, key: str, fmt: str, *, scale: float = 1.0, suffix: str = "", higher_better: bool | None) -> str:
        hv = haar.get(key)
        yv = yunet.get(key)
        better = ""
        if higher_better is not None and isinstance(hv, (int, float)) and isinstance(yv, (int, float)):
            if hv != yv:
                better = "YuNet" if (yv > hv) == higher_better else "Haar"
        return (
            f"| {label} | {cell(haar, key, fmt, scale, suffix)} | "
            f"{cell(yunet, key, fmt, scale, suffix)} | {better} |"
        )

    lines.append(line("Detection rate (recall proxy)", "detection_rate_percent", ".1f", suffix="%", higher_better=True))
    lines.append(line("Exactly-one-face rate", "single_face_rate_percent", ".1f", suffix="%", higher_better=True))
    lines.append(line("Images with extra boxes (FP proxy)", "false_positive_rate_percent", ".1f", suffix="%", higher_better=False))
    lines.append(line("Extra detections (count)", "extra_detections", ".0f", higher_better=False))
    lines.append(line("Mean detection time", "mean_detect_ms", ".1f", suffix=" ms", higher_better=False))
    lines.append(line("Throughput", "detect_fps", ".1f", suffix=" fps", higher_better=True))
    lines.append(line("Mean detected face size", "mean_face_side_px", ".0f", suffix=" px", higher_better=None))
    conf = yunet.get("mean_confidence")
    conf_cell = f"{conf:.3f}" if isinstance(conf, (int, float)) else "n/a"
    lines.append(f"| Mean confidence | n/a (no score) | {conf_cell} | - |")
    lines.append("| 5-point landmarks | no | yes | YuNet |")
    lines.append(
        f"| Model file size | {_fmt_kb(haar.get('model_file_bytes', 0))} | "
        f"{_fmt_kb(yunet.get('model_file_bytes', 0))} | - |"
    )
    lines.append("")
    lines.append("- **Detection rate / FP proxy** assume one findable face per image (true for La Salle and LFW).")
    lines.append("- **Throughput** is single-thread CPU detection only (excludes JPEG decode); higher is better.")
    lines.append("- YuNet's landmarks enable similarity-transform face alignment; Haar exposes only a box.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    dataset_key = Path(args.dataset).name
    dataset_dir = Path(resolve_path(args.dataset if Path(args.dataset).is_absolute() else f"data/{args.dataset}"))
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    images = gather_images(dataset_dir, args.max_images, args.random_seed)
    if not images:
        raise RuntimeError(f"No images found under {dataset_dir}")

    print(f"[INFO] Detector benchmark on {len(images)} images from {dataset_dir}")
    print(f"[INFO] downscale_max_side={args.downscale_max_side} min_face_size={args.min_face_size}")

    # Decode + downscale each image ONCE and reuse for both backends. Storing the
    # downscaled copy (not the 48 MP original) keeps memory sane: a 6928px La Salle
    # JPEG shrinks to <=640px before caching, so 336 images fit in a few hundred MB.
    gray_cache: dict[Path, np.ndarray] = {}
    bgr_cache: dict[Path, np.ndarray] = {}
    scale_cache: dict[Path, float] = {}
    decode_ms: list[float] = []
    native_hw = (0, 0)
    kept: list[Path] = []
    for path in images:
        t0 = time.perf_counter()
        bgr = cv.imread(str(path))
        decode_ms.append((time.perf_counter() - t0) * 1000.0)
        if bgr is None:
            continue
        if native_hw == (0, 0):
            native_hw = bgr.shape[:2]
        small, scale = maybe_downscale(bgr, args.downscale_max_side)
        bgr_cache[path] = small
        gray_cache[path] = cv.cvtColor(small, cv.COLOR_BGR2GRAY)
        scale_cache[path] = scale
        kept.append(path)
    images = kept

    rows = [benchmark_backend(b, images, gray_cache, bgr_cache, scale_cache, args) for b in BACKENDS]
    for r in rows:
        print(
            f"  {r['backend']:6s} rate={r['detection_rate_percent']:5.1f}% "
            f"extra={r['extra_detections']:4d} {r['mean_detect_ms']:6.1f} ms "
            f"({r['detect_fps']:5.1f} fps) face~{r['mean_face_side_px']:.0f}px"
        )

    img_h, img_w = native_hw
    summary = {
        "dataset": dataset_key,
        "dataset_dir": str(dataset_dir),
        "images": len(images),
        "image_note": f"native ~{img_w}x{img_h}px, one face per image",
        "downscale_max_side": args.downscale_max_side,
        "min_face_size": args.min_face_size,
        "config": {
            "scale_factor": args.scale_factor,
            "min_neighbors": args.min_neighbors,
            "yunet_score_threshold": args.yunet_score_threshold,
            "yunet_nms_threshold": args.yunet_nms_threshold,
            "random_seed": args.random_seed,
        },
        "mean_decode_ms": statistics.mean(decode_ms) if decode_ms else 0.0,
        "rows": rows,
    }

    out_json = resolve_path(args.output_json) if args.output_json else root_path(
        "reports", "benchmark", f"detector_comparison_{dataset_key}.json"
    )
    out_md = resolve_path(args.output_md) if args.output_md else root_path(
        "reports", "benchmark", f"detector_comparison_{dataset_key}.md"
    )
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(to_markdown(summary))

    print(f"[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")


if __name__ == "__main__":
    main()
