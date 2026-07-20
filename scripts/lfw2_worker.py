#!/usr/bin/env python3
"""Member-side batch-campaign worker (docs/BATCH_WORK/DESIGN.md sec 6.1,
docs/SYSTEMATIC_INDEPENDENCE_TEST.md sec 6). One command per member:

    python scripts/lfw2_worker.py --member <your_name>

Reads the assigned (variant, segment) work units from an assignments JSON
(default docs/BATCH_WORK/assignments.json), runs preflight/dataset/canary
checks once, then runs each unit through
``python -m src.hybrid.independence_test`` and packages the results into
zips under ``<results-dir>/uploads/`` ready to send to the coordinator.

Every phase is idempotent via a stamp file under
``<results-dir>/.worker_state/`` - a crashed/interrupted run resumes where
it stopped; a completed phase prints ``[SKIP]`` instead of recomputing.

Audit rule (no silently divergent inputs): preflight hard-fails on any
python/numpy/opencv version mismatch against the pinned
``batch_pins.json``, any artifact SHA-256 mismatch, or a real (non
placeholder) commit mismatch. Selection integrity for the actual sweep is
enforced downstream by ``--selection-manifest`` inside
``src.hybrid.independence_test`` itself.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMIT_PLACEHOLDER = "TBD_AT_CAMPAIGN_START"
LFW_DEFAULT_DIR = PROJECT_ROOT / "data" / "lfw-dataset"
DEFAULT_ASSIGNMENTS = PROJECT_ROOT / "docs" / "BATCH_WORK" / "assignments.json"
DEFAULT_PINS = PROJECT_ROOT / "docs" / "BATCH_WORK" / "batch_pins.json"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "reports" / "batch_results"


class WorkerError(RuntimeError):
    """Hard-fail: message is already fully formatted for the console."""


def fail(message: str) -> None:
    raise WorkerError(message)


def resolve_under_root(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(root: Path) -> str:
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                          capture_output=True, text=True)
    if res.returncode != 0:
        fail(f"git rev-parse HEAD failed: {res.stderr.strip()}")
    return res.stdout.strip()


def git_dirty(root: Path) -> bool:
    res = subprocess.run(["git", "status", "--porcelain"], cwd=str(root),
                          capture_output=True, text=True)
    if res.returncode != 0:
        fail(f"git status failed: {res.stderr.strip()}")
    return bool(res.stdout.strip())


def call_setup_lfw(project_root: Path) -> None:
    """Import scripts/setup_datasets.py by path and call its setup_lfw()
    (not the whole main(), which also does La Salle LFS + augmentation work
    this worker doesn't need)."""
    module_path = project_root / "scripts" / "setup_datasets.py"
    spec = importlib.util.spec_from_file_location("setup_datasets_mod", module_path)
    if spec is None or spec.loader is None:
        fail(f"Could not load {module_path} for setup_lfw()")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.setup_lfw()


# --------------------------------------------------------------------------- #
# Stamp files (idempotency)
# --------------------------------------------------------------------------- #
def state_dir(results_dir: Path) -> Path:
    d = results_dir / ".worker_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_stamp(path: Path) -> dict | None:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def write_stamp(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --------------------------------------------------------------------------- #
# Phase 1: PREFLIGHT
# --------------------------------------------------------------------------- #
def phase_preflight(results_dir: Path, pins_path: Path) -> dict:
    stamp_path = state_dir(results_dir) / "preflight.json"
    cached = read_stamp(stamp_path)
    if cached is not None:
        print("[SKIP] PREFLIGHT already done")
        return cached

    print("[PHASE] PREFLIGHT")

    if sys.version_info < (3, 10):
        fail(f"Python >= 3.10 required, found {sys.version.split()[0]}")

    if not pins_path.is_file():
        fail(f"Pins file not found: {pins_path}")
    with open(pins_path, "r", encoding="utf-8") as f:
        pins = json.load(f)
    if pins.get("schema") != "lsface-batch-pins-v1":
        fail(f"Unsupported pins schema in {pins_path}: {pins.get('schema')!r}")

    import numpy  # noqa: F401  (import-checked, version read via importlib.metadata below)
    import cv2  # noqa: F401

    # Read versions the SAME way make_batch_pins.py wrote them (pip wheel
    # version via importlib.metadata), not module.__version__: for
    # opencv-contrib-python the wheel version has 4 components
    # (e.g. 4.13.0.92) while cv2.__version__ only reports 3 (4.13.0) -
    # comparing against __version__ would false-positive-mismatch on the
    # exact machine that generated the pins.
    installed_numpy = importlib.metadata.version("numpy")
    try:
        installed_opencv = importlib.metadata.version("opencv-contrib-python")
    except importlib.metadata.PackageNotFoundError:
        installed_opencv = importlib.metadata.version("opencv-python")
    if installed_numpy != pins["numpy"]:
        fail(
            f"numpy version mismatch: installed {installed_numpy!r} "
            f"!= pinned {pins['numpy']!r} ({pins_path})"
        )
    if installed_opencv != pins["opencv"]:
        fail(
            f"opencv version mismatch: installed {installed_opencv!r} "
            f"!= pinned {pins['opencv']!r} ({pins_path})"
        )
    print(f"  [OK] python={sys.version.split()[0]} numpy={installed_numpy} opencv={installed_opencv}")

    bad: list[str] = []
    for relpath, expected_sha in pins.get("artifacts", {}).items():
        abspath = PROJECT_ROOT / relpath
        if not abspath.is_file():
            bad.append(f"{relpath}: MISSING at {abspath}")
            continue
        actual_sha = sha256_file(abspath)
        if actual_sha.lower() != str(expected_sha).lower():
            bad.append(
                f"{relpath}: sha256 mismatch (expected {expected_sha}, got {actual_sha})"
            )
    if bad:
        fail("Artifact SHA-256 verification failed against " + str(pins_path)
             + ":\n  " + "\n  ".join(bad))
    print(f"  [OK] {len(pins.get('artifacts', {}))} pinned artifact(s) SHA-256 verified")

    commit = git_head(PROJECT_ROOT)
    pins_commit = pins.get("commit")
    if pins_commit == COMMIT_PLACEHOLDER:
        print(f"  [WARN] batch_pins.json commit is the placeholder "
              f"({COMMIT_PLACEHOLDER!r}); skipping commit equality check. "
              f"HEAD={commit}")
    elif commit != pins_commit:
        fail(f"git commit mismatch: HEAD={commit} pinned={pins_commit}")
    else:
        print(f"  [OK] commit matches pins: {commit}")

    dirty = git_dirty(PROJECT_ROOT)
    if dirty:
        print("  [WARN] working tree has uncommitted changes")

    info = {
        "python": platform.python_version(),
        "numpy": installed_numpy,
        "opencv": installed_opencv,
        "commit": commit,
        "pins_commit": pins_commit,
        "dirty": dirty,
        "pins_echo": pins.get("artifacts", {}),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
    }
    write_stamp(stamp_path, info)
    print("  [SAVE] preflight stamp written")
    return info


# --------------------------------------------------------------------------- #
# Phase 2: DATASET
# --------------------------------------------------------------------------- #
def phase_dataset(results_dir: Path, dataset_dir: Path, skip_setup: bool) -> None:
    stamp_path = state_dir(results_dir) / "dataset.json"
    if read_stamp(stamp_path) is not None:
        print("[SKIP] DATASET already done")
        return

    print("[PHASE] DATASET")
    present = dataset_dir.is_dir() and any(dataset_dir.iterdir())
    if present:
        print(f"  [OK] dataset dir present: {dataset_dir}")
    else:
        if skip_setup:
            fail(f"dataset dir missing ({dataset_dir}) and --skip-setup was given; "
                 f"cannot auto-provision")
        if dataset_dir.resolve() == LFW_DEFAULT_DIR.resolve():
            print(f"  [INFO] dataset dir missing; downloading/verifying LFW "
                  f"({LFW_DEFAULT_DIR}) via setup_lfw()...")
            call_setup_lfw(PROJECT_ROOT)
            if not (dataset_dir.is_dir() and any(dataset_dir.iterdir())):
                fail(f"setup_lfw() completed but dataset dir is still missing/empty: {dataset_dir}")
        else:
            fail(f"dataset dir missing ({dataset_dir}) and it is not the LFW default "
                 f"path ({LFW_DEFAULT_DIR}); nothing to auto-provision - verify the "
                 f"assignments' dataset_dir or --dataset-dir override")

    write_stamp(stamp_path, {"dataset_dir": str(dataset_dir)})
    print("  [SAVE] dataset stamp written")


# --------------------------------------------------------------------------- #
# Phase 3: CANARY
# --------------------------------------------------------------------------- #
def phase_canary(results_dir: Path, dataset_dir: Path) -> dict:
    canary_dir = results_dir / "canary"
    stamp_path = state_dir(results_dir) / "canary.json"
    cached = read_stamp(stamp_path)
    if cached is not None:
        print("[SKIP] CANARY already done")
        return cached

    print("[PHASE] CANARY")
    cmd = [
        sys.executable, "-m", "src.hybrid.independence_test",
        "--dataset-dir", str(dataset_dir),
        "--output-dir", str(canary_dir),
        "--max-identities", "64",
        "--iterations", "1",
    ]
    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    elapsed = time.time() - t0
    if res.returncode != 0:
        fail(f"canary sweep failed (exit {res.returncode}): {' '.join(cmd)}")

    info = {"canary_seconds": elapsed, "output_dir": str(canary_dir)}
    write_stamp(stamp_path, info)
    print(f"  [SAVE] canary stamp written ({elapsed:.1f}s)")
    return info


# --------------------------------------------------------------------------- #
# Phase 4: UNITS
# --------------------------------------------------------------------------- #
def unit_key(variant_spec: str, segment_index: int, segment_count: int) -> str:
    return f"{variant_spec.replace(':', '_')}_seg{segment_index}of{segment_count}"


def run_unit(
    results_dir: Path, dataset_dir: Path, selection_manifest: Path,
    iterations: int, segment_count: int, variant_spec: str, segment_index: int,
) -> tuple[dict, Path]:
    variant_us = variant_spec.replace(":", "_")
    out_base = results_dir / variant_us
    final_dir = (
        Path(str(out_base) + f"_seg{segment_index}of{segment_count}")
        if segment_count > 1 else out_base
    )
    key = unit_key(variant_spec, segment_index, segment_count)
    stamp_path = state_dir(results_dir) / "units" / f"{key}.json"
    cached = read_stamp(stamp_path)
    if cached is not None:
        print(f"[SKIP] UNIT {variant_spec} seg {segment_index}/{segment_count} already done")
        return cached, Path(cached["output_dir"])

    print(f"[PHASE] UNIT {variant_spec} seg {segment_index}/{segment_count}")
    cmd = [
        sys.executable, "-m", "src.hybrid.independence_test",
        "--dataset-dir", str(dataset_dir),
        "--selection-manifest", str(selection_manifest),
        "--iterations", str(iterations),
        "--modification", variant_spec,
        "--segment-count", str(segment_count),
        "--segment-index", str(segment_index),
        "--output-dir", str(out_base),
    ]
    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    elapsed = time.time() - t0
    if res.returncode != 0:
        fail(f"unit {variant_spec} seg {segment_index}/{segment_count} failed "
             f"(exit {res.returncode}): {' '.join(cmd)}")

    info = {
        "unit_seconds": elapsed,
        "output_dir": str(final_dir),
        "variant": variant_spec,
        "segment_index": segment_index,
        "segment_count": segment_count,
        "iterations": iterations,
    }
    write_stamp(stamp_path, info)
    print(f"  [SAVE] unit stamp written ({elapsed:.1f}s) -> {final_dir}")
    return info, final_dir


# --------------------------------------------------------------------------- #
# Phase 5: PACKAGE
# --------------------------------------------------------------------------- #
def package_unit(
    results_dir: Path, campaign: str, member: str, preflight_info: dict,
    canary_info: dict, unit_info: dict, final_dir: Path,
) -> Path:
    variant_spec = unit_info["variant"]
    variant_us = variant_spec.replace(":", "_")
    segment_index = unit_info["segment_index"]
    segment_count = unit_info["segment_count"]

    uploads_dir = results_dir / "uploads"
    zip_name = f"{campaign}_{variant_us}_seg{segment_index}of{segment_count}_{member}.zip"
    zip_path = uploads_dir / zip_name
    if zip_path.exists():
        print(f"[SKIP] PACKAGE {zip_name} already exists")
        return zip_path

    print(f"[PHASE] PACKAGE {zip_name}")
    csv_path = final_dir / "comparisons.csv"
    summary_path = final_dir / "summary.json"
    if not csv_path.is_file():
        fail(f"Cannot package unit: missing {csv_path}")
    if not summary_path.is_file():
        fail(f"Cannot package unit: missing {summary_path}")

    csv_sha256 = sha256_file(csv_path)
    summary_sha256 = sha256_file(summary_path)

    manifest = {
        "campaign": campaign,
        "member": member,
        "variant": variant_spec,
        "segment_index": segment_index,
        "segment_count": segment_count,
        "iterations": unit_info["iterations"],
        "commit": preflight_info["commit"],
        "dirty": preflight_info["dirty"],
        "python": preflight_info["python"],
        "numpy": preflight_info["numpy"],
        "opencv": preflight_info["opencv"],
        "hostname": preflight_info["hostname"],
        "platform": preflight_info["platform"],
        "canary_seconds": canary_info["canary_seconds"],
        "unit_seconds": unit_info["unit_seconds"],
        "comparisons_csv_sha256": csv_sha256,
        "summary_sha256": summary_sha256,
        "pins_echo": preflight_info["pins_echo"],
    }

    uploads_dir.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "rb") as f:
        csv_bytes = f.read()
    gz_bytes = gzip.compress(csv_bytes)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("comparisons.csv.gz", gz_bytes)
        zf.write(summary_path, "summary.json")
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    print(f"  [SAVE] {zip_path}")
    return zip_path


# --------------------------------------------------------------------------- #
# CLI / orchestration
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-campaign member worker: preflight -> dataset -> canary "
                    "-> assigned (variant, segment) units -> upload zips."
    )
    parser.add_argument("--member", default=None,
                        help="Member name; looks up their unit list in --assignments. "
                             "Also used to name upload zips even in --variant mode.")
    parser.add_argument("--variant", default=None,
                        help="Explicit variant 'name:level' (e.g. motion_blur:5). "
                             "Use with --segment-index to run one ad-hoc unit instead "
                             "of the --member assignment list.")
    parser.add_argument("--segment-index", type=int, default=None,
                        help="1-based segment index, required together with --variant.")
    parser.add_argument("--assignments", default=str(DEFAULT_ASSIGNMENTS),
                        help=f"Assignments JSON (default {DEFAULT_ASSIGNMENTS}).")
    parser.add_argument("--dataset-dir", default=None,
                        help="Override the assignments file's dataset_dir.")
    parser.add_argument("--skip-setup", action="store_true",
                        help="Skip the LFW auto-download step (dataset dir must already exist).")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR),
                        help=f"Output root (default {DEFAULT_RESULTS_DIR}).")
    parser.add_argument("--pins", default=str(DEFAULT_PINS),
                        help=f"batch_pins.json path (default {DEFAULT_PINS}).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        assignments_path = resolve_under_root(args.assignments)
        if not assignments_path.is_file():
            fail(f"Assignments file not found: {assignments_path}")
        with open(assignments_path, "r", encoding="utf-8") as f:
            assignments = json.load(f)

        campaign = assignments["campaign"]
        segment_count = int(assignments["segment_count"])
        iterations = int(assignments["iterations"])
        selection_manifest = resolve_under_root(assignments["selection_manifest"])

        if args.dataset_dir:
            dataset_dir = resolve_under_root(args.dataset_dir)
        else:
            dataset_dir = resolve_under_root(assignments["dataset_dir"])

        results_dir = resolve_under_root(args.results_dir)
        pins_path = resolve_under_root(args.pins)

        # -- resolve the unit list ------------------------------------------------
        if args.variant:
            if args.segment_index is None:
                fail("--variant requires --segment-index")
            member = args.member or "adhoc"
            unit_list = [(args.variant, int(args.segment_index))]
        else:
            if not args.member:
                fail("Provide --member <name> or --variant <name:level> --segment-index <i>")
            member = args.member
            units_table = assignments.get("units", {})
            known_members = sorted(k for k in units_table.keys() if not k.startswith("_"))
            if member not in units_table:
                fail(
                    f"Unknown --member {member!r}. Known members in "
                    f"{assignments_path}: {known_members}"
                )
            unit_list = [(v, int(i)) for v, i in units_table[member]]

        print(f"[INFO] Campaign: {campaign}  Member: {member}  Units: {len(unit_list)}")
        print(f"[INFO] Dataset dir: {dataset_dir}")
        print(f"[INFO] Selection manifest: {selection_manifest}")
        print(f"[INFO] Results dir: {results_dir}")

        preflight_info = phase_preflight(results_dir, pins_path)
        phase_dataset(results_dir, dataset_dir, args.skip_setup)
        canary_info = phase_canary(results_dir, dataset_dir)
        if not selection_manifest.is_file():
            fail(f"Selection manifest not found: {selection_manifest} "
                 f"(see docs/BATCH_WORK/DESIGN.md sec 6.2 / scripts/make_selection_manifest.py)")

        zips: list[Path] = []
        for variant_spec, segment_index in unit_list:
            unit_info, final_dir = run_unit(
                results_dir, dataset_dir, selection_manifest, iterations,
                segment_count, variant_spec, segment_index,
            )
            zip_path = package_unit(
                results_dir, campaign, member, preflight_info, canary_info,
                unit_info, final_dir,
            )
            zips.append(zip_path)

        print("\n[DONE] Produced upload zip(s):")
        for z in zips:
            print(f"  {z}")
        print(f"\nSend the zip(s) above to the campaign coordinator.")
        return 0
    except WorkerError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
