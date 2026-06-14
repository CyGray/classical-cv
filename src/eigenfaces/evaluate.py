"""Thin Eigenfaces evaluation wrapper over the shared classical pipeline.

The evaluation loop, metrics, threshold sweep, and report schema live in
:mod:`src.classical_faces.pipeline`. Unlike the old evaluator this one does NOT
skip unseen identities and does NOT fall back to the full image: it shares the
exact open-set loop used by LBPH and Fisherfaces.
"""

import argparse

from src.classical_faces.datasets import gather_dataset_entries, resolve_path, root_path
from src.classical_faces.pipeline import (
    SPECS,
    add_dataset_args,
    add_preprocess_args,
    build_detectors,
    build_preprocess_config,
    dataset_profile_from_args,
    load_label_map,
    load_recognizer,
    parse_threshold_sweep,
    print_eval_summary,
    run_evaluation,
    selected_aug_splits,
)
from src.reporting.identity import derive_model_variant

FAMILY = "eigenfaces"


def _default_sweep_str(spec) -> str:
    return ",".join(
        str(int(t)) if float(t).is_integer() else str(t) for t in spec.default_threshold_sweep
    )


def parse_args() -> argparse.Namespace:
    spec = SPECS[FAMILY]
    parser = argparse.ArgumentParser(
        description="Evaluate an Eigenfaces model on the clean held-out La Salle test split by default."
    )
    add_dataset_args(
        parser,
        default_base=root_path("data", "split_lasalle"),
        default_raw="test",
        default_include_raw=True,
        default_aug_splits="light",
    )
    add_preprocess_args(
        parser,
        default_assume_cropped=True,
        default_equalization=spec.default_equalization,
    )
    parser.add_argument("--model-path", default=root_path("models", FAMILY, "lasalle_clean.yml"))
    parser.add_argument("--labels-path", default=root_path("models", FAMILY, "labels_lasalle_clean.json"))
    parser.add_argument("--unknown-threshold", type=float, default=spec.default_unknown_threshold)
    parser.add_argument("--threshold-sweep", default=_default_sweep_str(spec))
    parser.add_argument("--report-json", default=root_path("reports", "evaluation", f"{FAMILY}_eval.json"))
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--max-images-per-person", type=int, default=0)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--show-misclassified", type=int, default=15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.base_data_dir = resolve_path(args.base_data_dir)
    args.model_path = resolve_path(args.model_path)
    args.labels_path = resolve_path(args.labels_path)
    args.cascade_path = resolve_path(args.cascade_path)
    args.report_json = resolve_path(args.report_json) if args.report_json else ""

    spec = SPECS[FAMILY]
    preprocess = build_preprocess_config(args)
    detector, eye_cascade = build_detectors(
        face_cascade_path=args.cascade_path,
        eye_cascade_path=args.eye_cascade_path,
        preprocess=preprocess,
    )

    label_map, id_to_name, known_names = load_label_map(args.labels_path)
    recognizer = load_recognizer(spec, args.model_path)

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
        raise RuntimeError("No dataset folders found to evaluate.")

    dataset_profile = dataset_profile_from_args(args)
    model_variant = derive_model_variant(args.model_path, args.labels_path, fallback=FAMILY)
    sweep = parse_threshold_sweep(args.threshold_sweep, spec.default_threshold_sweep)

    report = run_evaluation(
        spec,
        entries=entries,
        recognizer=recognizer,
        known_names=known_names,
        id_to_name=id_to_name,
        preprocess=preprocess,
        detector=detector,
        eye_cascade=eye_cascade,
        unknown_threshold=args.unknown_threshold,
        threshold_sweep=sweep,
        max_images_per_person=args.max_images_per_person,
        random_seed=args.random_seed,
        model_path=args.model_path,
        labels_path=args.labels_path,
        dataset_profile=dataset_profile,
        model_variant=model_variant,
        run_tag=args.run_tag,
        report_json=args.report_json or None,
        show_misclassified=args.show_misclassified,
    )

    print_eval_summary(spec, report)
    if args.report_json:
        print(f"[OK] Wrote JSON report to: {args.report_json}")


if __name__ == "__main__":
    main()
