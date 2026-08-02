"""Thin LBPH training wrapper over the shared classical pipeline.

All real work (preprocessing, dataset gathering, training, footprint) lives in
:mod:`src.classical_faces.pipeline`. This file only declares LBPH-specific
defaults and argument wiring.

Default loop is leakage-free: train on the pre-cropped held-out La Salle split
(``data/split_lasalle/train``) with ``--assume-cropped`` so no Haar detection /
full-image fallback is involved.
"""

import argparse

from src.classical_faces.datasets import gather_dataset_entries, resolve_path, root_path
from src.classical_faces.pipeline import (
    SPECS,
    add_dataset_args,
    add_preprocess_args,
    build_detectors,
    build_preprocess_config,
    run_training,
    selected_aug_splits,
)

FAMILY = "lbph"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train an LBPH recognizer on the clean La Salle split by default."
    )
    add_dataset_args(
        parser,
        default_base=root_path("data", "split_lasalle"),
        default_raw="train",
        default_include_raw=True,
        default_aug_splits="light",
    )
    add_preprocess_args(
        parser,
        default_assume_cropped=True,
        default_equalization=SPECS[FAMILY].default_equalization,
    )
    parser.add_argument("--model-output", default=root_path("models", FAMILY, "lasalle_clean.yml"))
    parser.add_argument("--labels-output", default=root_path("models", FAMILY, "labels_lasalle_clean.json"))
    parser.add_argument("--max-images-per-person", type=int, default=0)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--progress-interval", type=int, default=25)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.base_data_dir = resolve_path(args.base_data_dir)
    args.model_output = resolve_path(args.model_output)
    args.labels_output = resolve_path(args.labels_output)
    args.cascade_path = resolve_path(args.cascade_path)

    spec = SPECS[FAMILY]
    preprocess = build_preprocess_config(args)
    detector, eye_cascade = build_detectors(
        face_cascade_path=args.cascade_path,
        eye_cascade_path=args.eye_cascade_path,
        preprocess=preprocess,
    )

    entries = gather_dataset_entries(
        base_data_dir=args.base_data_dir,
        raw_dir=args.raw_dir_name,
        processed_dir=args.processed_dir_name,
        aug_dir=args.augmented_dir_name,
        aug_splits=selected_aug_splits(args),
        include_raw=args.include_raw,
        include_processed=args.include_processed,
        include_augmented=args.include_augmented,
    )
    if not entries:
        raise RuntimeError("No training folders found. Check base-data-dir and dataset folder names.")

    print(f"[INFO] {FAMILY}: {len(entries)} identity folders | assume_cropped={preprocess.assume_cropped} "
          f"align_eyes={preprocess.align_eyes} equalization={preprocess.equalization}")

    result = run_training(
        spec,
        entries=entries,
        preprocess=preprocess,
        detector=detector,
        eye_cascade=eye_cascade,
        max_images_per_person=args.max_images_per_person,
        random_seed=args.random_seed,
        model_output=args.model_output,
        labels_output=args.labels_output,
        progress_interval=args.progress_interval,
    )

    print(f"[OK] Model: {result['model_output']} ({result['model_file_bytes']} bytes)")
    print(f"[OK] Labels: {result['labels_output']}")
    print(f"[INFO] Identities: {result['identities']} | samples: {result['used_samples']} | "
          f"feature_vector={result['feature_vector_bytes']} bytes")
    print(f"[INFO] Skipped: no_face={result['skipped_no_face']} too_small={result['skipped_too_small']} "
          f"unreadable={result['skipped_unreadable']}")
    print(f"[TIME] Train: {result['train_time_seconds']:.2f}s | Total: {result['total_time_seconds']:.2f}s")
    print(f"[INFO] Per-bucket: {result['bucket_counts']}")


if __name__ == "__main__":
    main()
