"""Kyle-side generator: pin the SHA-256 of every frozen artifact a batch
campaign member must have byte-identical, plus the pinned commit and the
required python/numpy/opencv versions (docs/BATCH_WORK/DESIGN.md section
10.1: preflight refuses to run on any mismatch).

Writes docs/BATCH_WORK/batch_pins.json (schema lsface-batch-pins-v1). The
"commit" field is a placeholder until the batch-work branch is committed
(work is uncommitted as of generation time); Kyle fills it in at campaign
start. "selection_manifests" is left empty here - it is populated once the
LFW selection manifest exists (scripts/utils/make_selection_manifest.py).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Relative to PROJECT_ROOT, forward slashes for the JSON keys.
ARTIFACTS = [
    "src/hybrid/thresholds.json",
    "models/lbph/lasalle_clean.yml",
    "models/lbph/labels_lasalle_clean.json",
    "models/sface/gallery.npy",
    "models/sface/labels.json",
    "models/sface/face_recognition_sface_2021dec.onnx",
    "models/yunet/face_detection_yunet_2023mar.onnx",
]

OUTPUT_PATH = PROJECT_ROOT / "docs" / "BATCH_WORK" / "batch_pins.json"

COMMIT_PLACEHOLDER = "TBD_AT_CAMPAIGN_START"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pkg_version(name: str) -> str:
    return importlib.metadata.version(name)


def main() -> int:
    artifacts: dict[str, str] = {}
    missing: list[str] = []
    for relpath in ARTIFACTS:
        abspath = PROJECT_ROOT / relpath
        if not abspath.is_file():
            missing.append(relpath)
            continue
        artifacts[relpath] = sha256_file(abspath)

    if missing:
        print("[ERROR] Missing artifact file(s):")
        for m in missing:
            print(f"  - {m}")
        return 1

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    numpy_version = pkg_version("numpy")
    try:
        opencv_version = pkg_version("opencv-contrib-python")
    except importlib.metadata.PackageNotFoundError:
        opencv_version = pkg_version("opencv-python")

    pins = {
        "schema": "lsface-batch-pins-v1",
        "commit": COMMIT_PLACEHOLDER,
        "python": python_version,
        "numpy": numpy_version,
        "opencv": opencv_version,
        "artifacts": artifacts,
        "selection_manifests": {},
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pins, f, indent=2)

    print(f"[INFO] Platform: {platform.platform()}")
    print(f"[INFO] Python: {python_version}  numpy: {numpy_version}  opencv: {opencv_version}")
    print(f"[INFO] commit pinned as placeholder: {COMMIT_PLACEHOLDER} (fill in at campaign start)")
    print("\n[SUMMARY]")
    print(f"  artifacts pinned: {len(artifacts)}")
    for relpath, digest in artifacts.items():
        print(f"    {relpath}: {digest}")
    print(f"  output: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
