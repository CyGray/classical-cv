"""One-command clean train -> evaluate -> compare loop for the classical track.

Reproduces a leakage-free benchmark for all three classical recognizers on the
held-out La Salle split and writes the spec comparison table. For each family it
produces two side-by-side variants:

* ``baseline`` - trained on ``data/split_lasalle/train`` (real cropped tiles only)
* ``aug-light`` - trained on the same tiles plus train-only light augmentation
  from ``data/split_augmented41mods_lasalle_clean``

Both variants are always evaluated on the SAME real held-out test split
(``data/split_lasalle/test``) so the headline number is honest. Nothing here ever
evaluates against augmented images.

Usage::

    python scripts/run_classical_clean_loop.py                 # full loop
    python scripts/run_classical_clean_loop.py --regenerate-aug
    python scripts/run_classical_clean_loop.py --skip-aug --families lbph
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ["lbph", "eigenfaces", "fisherfaces"]

SPLIT_BASE = "data/split_lasalle"
AUG_ROOT = "data/split_augmented41mods_lasalle_clean"


def python_exe() -> str:
    return os.environ.get("FACE_G3_PYTHON") or sys.executable


def run(cmd: list[str], *, label: str) -> None:
    print(f"\n{'=' * 70}\n[RUN] {label}\n     {' '.join(cmd)}\n{'=' * 70}")
    subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean classical train/eval/compare loop.")
    parser.add_argument(
        "--families",
        default=",".join(FAMILIES),
        help="Comma-separated subset of: lbph,eigenfaces,fisherfaces",
    )
    parser.add_argument("--skip-aug", action="store_true", help="Only train/eval the baseline variant.")
    parser.add_argument(
        "--regenerate-aug",
        action="store_true",
        help="Regenerate the leakage-safe La Salle augmentation before training.",
    )
    parser.add_argument("--skip-compare", action="store_true", help="Do not write the comparison table.")
    parser.add_argument("--skip-tar-far", action="store_true",
                        help="Skip the TAR@FAR pass (LFW impostors); leaves the verification columns empty.")
    parser.add_argument("--skip-ar", action="store_true",
                        help="Skip the 41-modification Accuracy-Ratio pass.")
    parser.add_argument("--quick-tar-far", action="store_true",
                        help="Cap TAR@FAR impostors (400 ids x 2) instead of the full LFW set; "
                             "faster but FAR only resolves to ~0.17%% instead of 100 ppm.")
    parser.add_argument("--max-images-per-person", type=int, default=0)
    return parser.parse_args()


def regenerate_aug(py: str) -> None:
    run(
        [
            py,
            "augment_split_light_medium.py",
            "--split-root",
            SPLIT_BASE,
            "--output-root",
            AUG_ROOT,
            "--overwrite",
        ],
        label="Regenerate leakage-safe La Salle augmentation",
    )


def model_paths(family: str, variant: str) -> tuple[str, str]:
    suffix = "" if variant == "baseline" else "_aug_light"
    return (
        f"models/{family}/lasalle_clean{suffix}.yml",
        f"models/{family}/labels_lasalle_clean{suffix}.json",
    )


def train_baseline(py: str, family: str, max_images: int) -> None:
    model, labels = model_paths(family, "baseline")
    run(
        [
            py, "-m", f"src.{family}.trainer",
            "--base-data-dir", SPLIT_BASE,
            "--raw-dir-name", "train",
            "--include-raw",
            "--no-include-augmented",
            "--assume-cropped",
            "--model-output", model,
            "--labels-output", labels,
            "--max-images-per-person", str(max_images),
        ],
        label=f"{family}: train baseline",
    )


def train_aug(py: str, family: str, max_images: int) -> None:
    model, labels = model_paths(family, "aug-light")
    run(
        [
            py, "-m", f"src.{family}.trainer",
            "--base-data-dir", "data",
            "--raw-dir-name", "split_lasalle/train",
            "--include-raw",
            "--augmented-dir-name", os.path.basename(AUG_ROOT),
            "--include-augmented",
            "--aug-splits", "light",
            "--assume-cropped",
            "--model-output", model,
            "--labels-output", labels,
            "--max-images-per-person", str(max_images),
        ],
        label=f"{family}: train aug-light",
    )


def evaluate(py: str, family: str, variant: str) -> None:
    model, labels = model_paths(family, variant)
    suffix = "" if variant == "baseline" else "_aug_light"
    report = f"reports/evaluation/{family}_eval{suffix}.json"
    run(
        [
            py, "-m", f"src.{family}.evaluate",
            "--base-data-dir", SPLIT_BASE,
            "--raw-dir-name", "test",
            "--include-raw",
            "--assume-cropped",
            "--model-path", model,
            "--labels-path", labels,
            "--run-tag", variant,
            "--report-json", report,
        ],
        label=f"{family}: evaluate {variant} (held-out test)",
    )


def main() -> None:
    args = parse_args()
    py = python_exe()
    families = [f.strip().lower() for f in args.families.split(",") if f.strip()]
    invalid = [f for f in families if f not in FAMILIES]
    if invalid:
        raise SystemExit(f"Unknown families: {invalid}. Choose from {FAMILIES}.")

    if args.regenerate_aug and not args.skip_aug:
        regenerate_aug(py)

    for family in families:
        train_baseline(py, family, args.max_images_per_person)
        evaluate(py, family, "baseline")
        if not args.skip_aug:
            train_aug(py, family, args.max_images_per_person)
            evaluate(py, family, "aug-light")

    if not args.skip_tar_far:
        tar_far_cmd = [py, "-m", "src.benchmark.tar_at_far"]
        if args.quick_tar_far:
            tar_far_cmd += ["--impostor-dir", "data/split_lfw/test",
                            "--impostor-max-identities", "400", "--impostor-max-per-id", "2"]
        run(tar_far_cmd,
            label="Measure TAR@FAR / FRR / EER vs LFW impostors (baseline models)")

    if not args.skip_ar:
        run([py, "-m", "src.benchmark.accuracy_ratio"],
            label="Accuracy Ratio (41-modification suite, held-out originals)")

    if not args.skip_compare:
        run([py, "-m", "src.benchmark.compare_classical"], label="Build spec comparison table")

    print("\n[DONE] Clean classical loop complete.")
    print("  - Reports:    reports/evaluation/<family>_eval[_aug_light].json")
    print("  - TAR@FAR:    reports/benchmark/tar_at_far.md")
    print("  - AR (41mod): reports/benchmark/accuracy_ratio.md")
    print("  - Comparison: reports/benchmark/classical_comparison.md")


if __name__ == "__main__":
    main()
