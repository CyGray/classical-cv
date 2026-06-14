import shlex
import subprocess
import json
import os
import re
from pathlib import Path
from dataclasses import dataclass


PROJECT_ROOT = Path(__file__).resolve().parent

GROUPED_CHOICES = [
    (
        "ArcFace",
        [
            ("setup model", "src/arcface/setup_model.py"),
            ("train enrollment", "src/arcface/trainer.py"),
            ("evaluate", "src/arcface/evaluate.py"),
            ("live detect", "src/arcface/detect.py"),
        ],
    ),
    (
        "ArcFace MobileNet INT8",
        [
            ("train enrollment", "src/arcface_mobilenet_int8/trainer.py"),
            ("evaluate", "src/arcface_mobilenet_int8/evaluate.py"),
            ("live detect", "src/arcface_mobilenet_int8/face_detect.py"),
            ("quantize model", "src/arcface_mobilenet_int8/quantize_model.py"),
        ],
    ),
    (
        "MobileFaceNet",
        [
            ("train enrollment", "src/mobilefacenet/trainer.py"),
            ("evaluate", "src/mobilefacenet/evaluate.py"),
            ("live detect", "src/mobilefacenet/detect.py"),
        ],
    ),
    (
        "EdgeFace",
        [
            ("train enrollment", "src/edgeface/trainer.py"),
            ("evaluate", "src/edgeface/evaluate.py"),
            ("live detect", "src/edgeface/face_detect.py"),
        ],
    ),
    (
        "LBPH",
        [
            ("train", "src/lbph/trainer.py"),
            ("train (light front)", "src/lbph/trainer_light_front.py"),
            ("evaluate", "src/lbph/evaluate.py"),
            ("live detect", "src/lbph/detect.py"),
            ("independence test", "src/lbph/independence_test.py"),
            ("independence test (light front)", "src/lbph/independence_test_light_front.py"),
        ],
    ),
    (
        "Eigenfaces",
        [
            ("train", "src/eigenfaces/trainer.py"),
            ("train (light front)", "src/eigenfaces/trainer_light_front.py"),
            ("evaluate", "src/eigenfaces/evaluate.py"),
            ("live detect", "src/eigenfaces/detect.py"),
            ("independence test", "src/eigenfaces/independence_test.py"),
            ("independence test (light front)", "src/eigenfaces/independence_test_light_front.py"),
        ],
    ),
    (
        "Fisherfaces",
        [
            ("train", "src/fisherfaces/trainer.py"),
            ("train (light front)", "src/fisherfaces/trainer_light_front.py"),
            ("evaluate", "src/fisherfaces/evaluate.py"),
            ("live detect", "src/fisherfaces/detect.py"),
            ("independence test", "src/fisherfaces/independence_test.py"),
            ("independence test (light front)", "src/fisherfaces/independence_test_light_front.py"),
        ],
    ),
    (
        "Benchmark",
        [
            ("run clean classical loop", "scripts/run_classical_clean_loop.py"),
            ("compare classical (spec table)", "src/benchmark/compare_classical.py"),
            ("compare detectors (haar vs yunet)", "src/benchmark/compare_detectors.py"),
            ("independence thresholds (La Salle DB1)", "scripts/run_independence_thresholds.py"),
            ("independence thresholds (LFW DB1, gated)", "scripts/run_lfw_independence.py"),
            ("TAR@FAR vs LFW impostors", "src/benchmark/tar_at_far.py"),
            ("accuracy ratio (41-mod suite)", "src/benchmark/accuracy_ratio.py"),
            ("variants: unedited vs compact/upgraded", "scripts/compare_variants.py"),
            ("config sweep (components x equalization)", "scripts/sweep_classical_configs.py"),
            ("aggregate live FPS", "src/benchmark/aggregate_live_fps.py"),
            ("aggregate evaluation reports", "src/benchmark/aggregate_evaluation_reports.py"),
        ],
    ),
]

MODEL_INFO_CONFIG = {
    "ArcFace": {
        "trained_markers": ["models/arcface_mobilenet/enrollment.json"],
        "evaluated_reports": ["reports/evaluation/arcface_eval.json"],
        "size_paths": ["models/arcface_mobilenet"],
    },
    "ArcFace MobileNet INT8": {
        "trained_markers": ["models/arcface_mobilenet_int8/enrollment.json"],
        "evaluated_reports": ["reports/evaluation/arcface_mobilenet_int8_eval.json"],
        "size_paths": ["models/arcface_mobilenet_int8"],
    },
    "MobileFaceNet": {
        "trained_markers": ["models/yunet_mobilefacenet/enrollment.json"],
        "evaluated_reports": ["reports/evaluation/yunet_mobilefacenet_eval.json"],
        "size_paths": [
            "models/yunet_mobilefacenet/mobilefacenet.onnx",
            "models/yunet_mobilefacenet/face_detection_yunet_2023mar.onnx",
            "models/yunet_mobilefacenet/enrollment.json",
        ],
    },
    "EdgeFace": {
        "trained_markers": ["models/edgeface/enrollment.json"],
        "evaluated_reports": ["reports/evaluation/edgeface_eval.json"],
        "size_paths": [
            "models/edgeface/edgeface_xs.onnx",
            "models/edgeface/enrollment.json",
            "models/yunet_mobilefacenet/face_detection_yunet_2023mar.onnx",
        ],
    },
    # Classical entries point at the CANONICAL clean-split artifacts (what the
    # benchmarks and live detect use), not the legacy folder totals - the model
    # dirs still hold multi-GB deprecated trainer_*.yml files.
    "LBPH": {
        "trained_markers": ["models/lbph/lasalle_clean.yml"],
        "evaluated_reports": ["reports/evaluation/lbph_eval.json"],
        "size_paths": ["models/lbph/lasalle_clean.yml"],
    },
    "Eigenfaces": {
        "trained_markers": ["models/eigenfaces/lasalle_clean.yml"],
        "evaluated_reports": ["reports/evaluation/eigenfaces_eval.json"],
        "size_paths": ["models/eigenfaces/lasalle_clean.yml"],
    },
    "Fisherfaces": {
        "trained_markers": ["models/fisherfaces/lasalle_clean.yml"],
        "evaluated_reports": ["reports/evaluation/fisherfaces_eval.json"],
        "size_paths": ["models/fisherfaces/lasalle_clean.yml"],
    },
    "Benchmark": {
        "trained_markers": [],
        "evaluated_reports": [],
        "size_paths": [],
    },
}

BENCHMARK_OVERVIEW_CONFIG = {
    "ArcFace": {
        "eval_report": "reports/evaluation/arcface_eval.json",
        "fps_algorithm": "arcface",
    },
    "ArcFace MobileNet INT8": {
        "eval_report": "reports/evaluation/arcface_mobilenet_int8_eval.json",
        "fps_algorithm": "arcface_int8",
    },
    "MobileFaceNet": {
        "eval_report": "reports/evaluation/yunet_mobilefacenet_eval.json",
        "fps_algorithm": "mobilefacenet",
    },
    "EdgeFace": {
        "eval_report": "reports/evaluation/edgeface_eval.json",
        "fps_algorithm": "edgeface",
    },
    "LBPH": {
        "eval_report": "reports/evaluation/lbph_eval.json",
        "fps_algorithm": "lbph",
    },
    "Eigenfaces": {
        "eval_report": "reports/evaluation/eigenfaces_eval.json",
        "fps_algorithm": "eigenfaces",
    },
    "Fisherfaces": {
        "eval_report": "reports/evaluation/fisherfaces_eval.json",
        "fps_algorithm": "fisherfaces",
    },
}

MODEL_FAMILY_ALIASES: dict[str, set[str]] = {
    "ArcFace": {"arcface_buffalo_s"},
    "ArcFace MobileNet INT8": {"arcface_mobilenet_int8", "arcface_buffalo_s_int8"},
    "MobileFaceNet": {"yunet_mobilefacenet"},
    "EdgeFace": {"edgeface"},
    "LBPH": {"lbph"},
    "Eigenfaces": {"eigenfaces"},
    "Fisherfaces": {"fisherfaces"},
}


def resolve_path(rel_path: str) -> Path:
    return PROJECT_ROOT / rel_path


INT8_MODEL_DIR = resolve_path("models/arcface_mobilenet_int8")
INT8_REQUIRED_MODELS = [
    resolve_path("models/arcface_mobilenet_int8/w600k_mbf.onnx"),
    resolve_path("models/arcface_mobilenet_int8/models/buffalo_s/w600k_mbf.onnx"),
]


def path_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for file_path in path.rglob("*"):
        if file_path.is_file():
            total += file_path.stat().st_size
    return total


def format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    unit_idx = 0
    while value >= 1024.0 and unit_idx < len(units) - 1:
        value /= 1024.0
        unit_idx += 1
    return f"{value:.2f} {units[unit_idx]}"


def load_json_if_exists(path: Path) -> dict | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def extract_hit_rate_percent(report_payload: dict | None) -> float | None:
    if not report_payload:
        return None
    overall = report_payload.get("overall", {})
    # Classical closed-set reports carry rank-1 (nearest-neighbour, no threshold).
    # Prefer it so an uncalibrated unknown-threshold cannot make a recognizer look
    # like 0%. DL reports lack this key and fall through to hit_rate_percent.
    if isinstance(overall, dict) and "closed_set_rank1_percent" in overall:
        try:
            return float(overall["closed_set_rank1_percent"])
        except Exception:
            pass
    if "hit_rate_percent" in overall:
        try:
            return float(overall["hit_rate_percent"])
        except Exception:
            pass
    if "correct" in overall and "evaluated_images" in overall:
        try:
            correct = float(overall["correct"])
            evaluated = float(overall["evaluated_images"])
            if evaluated > 0:
                return 100.0 * correct / evaluated
        except Exception:
            pass
    threshold_sweep = report_payload.get("threshold_sweep", [])
    if isinstance(threshold_sweep, list) and threshold_sweep:
        best = None
        for row in threshold_sweep:
            try:
                value = float(row.get("overall_hit_rate_percent", -1.0))
            except Exception:
                continue
            if best is None or value > best:
                best = value
        if best is not None and best >= 0:
            return best
    return None


def infer_variant_from_report_file(
    *,
    report_path: Path,
    model_family: str,
    fallback: str,
) -> str:
    stem = report_path.stem.strip().lower()
    if not stem:
        return fallback

    # Trim generic report suffixes first.
    for suffix in ("_evaluation", "_eval", "_report"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    family_tokens = {
        model_family.strip().lower(),
        *MODEL_FAMILY_ALIASES.get(model_family, set()),
    }
    normalized_tokens = {
        re.sub(r"[^a-z0-9]+", "_", token).strip("_")
        for token in family_tokens
        if token
    }

    for token in sorted(normalized_tokens, key=len, reverse=True):
        if not token:
            continue
        if stem == token:
            return fallback
        if stem.startswith(token + "_"):
            suffix = stem[len(token) + 1 :].strip("_")
            return suffix or fallback

    return stem or fallback


def extract_accuracy_percent(report_payload: dict | None) -> float | None:
    if not report_payload:
        return None
    threshold_sweep = report_payload.get("threshold_sweep", [])
    if isinstance(threshold_sweep, list) and threshold_sweep:
        best = None
        for row in threshold_sweep:
            try:
                value = float(row.get("overall_hit_rate_percent", -1.0))
            except Exception:
                continue
            if best is None or value > best:
                best = value
        if best is not None and best >= 0:
            return best
    return extract_hit_rate_percent(report_payload)


def collect_fps_summary() -> dict[str, float]:
    aggregate_path = resolve_path("reports/benchmark/live_fps/aggregate_summary.json")
    aggregate_payload = load_json_if_exists(aggregate_path)
    if aggregate_payload:
        out: dict[str, float] = {}
        for row in aggregate_payload.get("algorithms", []):
            algo = str(row.get("algorithm", "")).strip().lower()
            if not algo:
                continue
            try:
                out[algo] = float(row.get("average_fps", 0.0))
            except Exception:
                continue
        if out:
            return out

    runs_dir = resolve_path("reports/benchmark/live_fps/runs")
    if not runs_dir.exists():
        return {}

    grouped: dict[str, dict[str, float]] = {}
    for run_file in runs_dir.glob("*.json"):
        payload = load_json_if_exists(run_file)
        if not payload:
            continue
        algo = str(payload.get("algorithm", "")).strip().lower()
        if not algo:
            continue
        frames = float(payload.get("frames", 0.0))
        duration = float(payload.get("duration_seconds", 0.0))
        avg_fps = float(payload.get("average_fps", 0.0))
        group = grouped.setdefault(algo, {"frames": 0.0, "duration": 0.0, "sum_fps": 0.0, "runs": 0.0})
        group["frames"] += max(0.0, frames)
        group["duration"] += max(0.0, duration)
        group["sum_fps"] += max(0.0, avg_fps)
        group["runs"] += 1.0

    out: dict[str, float] = {}
    for algo, row in grouped.items():
        if row["duration"] > 0 and row["frames"] > 0:
            out[algo] = row["frames"] / row["duration"]
        elif row["runs"] > 0:
            out[algo] = row["sum_fps"] / row["runs"]
    return out


def collect_evaluation_entities() -> list[dict]:
    reports_dir = resolve_path("reports/evaluation")
    if not reports_dir.exists():
        return []

    rows: list[dict] = []
    for report_path in sorted(reports_dir.glob("*.json")):
        payload = load_json_if_exists(report_path)
        if not payload:
            continue
        model_family = str(payload.get("model_family", "")).strip()
        if not model_family:
            continue

        hit_rate = extract_hit_rate_percent(payload)
        accuracy = extract_accuracy_percent(payload)
        overall = payload.get("overall", {}) if isinstance(payload.get("overall"), dict) else {}
        evaluated_images = int(overall.get("evaluated_images", 0)) if overall else 0
        dataset_profile = payload.get("dataset_profile", {})
        dataset_label = "unknown"
        if isinstance(dataset_profile, dict):
            dataset_label = str(dataset_profile.get("label", "unknown"))

        run_tag = str(payload.get("run_tag", "")).strip()
        model_variant_raw = str(payload.get("model_variant", "")).strip()
        if run_tag:
            model_variant = run_tag
        elif model_variant_raw and model_variant_raw.lower() != "default":
            model_variant = model_variant_raw
        else:
            model_variant = infer_variant_from_report_file(
                report_path=report_path,
                model_family=model_family,
                fallback=model_variant_raw or "default",
            )

        rows.append(
            {
                "model_family": model_family,
                "model_variant": model_variant,
                "entity_key": str(payload.get("entity_key", report_path.stem)),
                "dataset_label": dataset_label,
                "hit_rate": hit_rate,
                "accuracy": accuracy,
                "evaluated_images": evaluated_images,
            }
        )

    rows.sort(
        key=lambda row: (
            row["hit_rate"] if row["hit_rate"] is not None else float("-inf"),
            row["evaluated_images"],
        ),
        reverse=True,
    )
    return rows


def entity_matches_model_name(model_name: str, row: dict) -> bool:
    model_family = str(row.get("model_family", "")).strip().lower()
    model_variant = str(row.get("model_variant", "")).strip().lower()
    aliases = {value.lower() for value in MODEL_FAMILY_ALIASES.get(model_name, set())}
    if model_family not in aliases:
        return False

    # ArcFace and ArcFace INT8 can share family tags in reports; split by variant signal.
    if model_name == "ArcFace MobileNet INT8":
        return "int8" in model_variant or model_family.endswith("_int8")
    if model_name == "ArcFace":
        return "int8" not in model_variant and not model_family.endswith("_int8")
    return True


def entities_for_menu_model(model_name: str) -> list[dict]:
    if model_name not in MODEL_FAMILY_ALIASES:
        return []
    rows = collect_evaluation_entities()
    return [row for row in rows if entity_matches_model_name(model_name, row)]


def get_arg_value(args: list[str], flag: str, default: str) -> str:
    for idx, arg in enumerate(args):
        if arg == flag and idx + 1 < len(args):
            return args[idx + 1]
        if arg.startswith(f"{flag}="):
            return arg.split("=", 1)[1]
    return default


def bool_flag(args: list[str], name: str, default: bool) -> bool:
    positive = f"--{name}"
    negative = f"--no-{name}"
    if any(arg == negative or arg.startswith(f"{negative}=") for arg in args):
        return False
    if any(arg == positive or arg.startswith(f"{positive}=") for arg in args):
        return True
    return default


def infer_split_name(raw_dir_name: str, processed_dir_name: str) -> str:
    raw_base = Path(raw_dir_name).name.lower()
    processed_base = Path(processed_dir_name).name.lower()
    for candidate in (processed_base, raw_base):
        if candidate in {"train", "test"}:
            return candidate
    return ""


def build_dataset_label_from_args(
    args: list[str],
    *,
    is_training: bool,
    is_evaluation: bool,
) -> str:
    raw_dir_name = get_arg_value(args, "--raw-dir-name", "lasalle_db1")
    processed_dir_name = get_arg_value(args, "--processed-dir-name", "lasalle_db1_processed")
    augmented_dir_name = get_arg_value(args, "--augmented-dir-name", "split_augmented41mods")
    aug_splits_raw = get_arg_value(args, "--aug-splits", "__disabled__")

    include_raw = bool_flag(args, "include-raw", raw_dir_name != "__disabled__")
    include_processed = bool_flag(args, "include-processed", False)
    include_augmented_default = True if is_training and not is_evaluation else False
    include_augmented = bool_flag(args, "include-augmented", include_augmented_default)

    if raw_dir_name == "__disabled__":
        include_raw = False
    if aug_splits_raw.strip() == "__disabled__":
        include_augmented = False

    aug_splits = [
        value.strip().lower()
        for value in aug_splits_raw.split(",")
        if value.strip() and value.strip() != "__disabled__"
    ]
    joined_aug = ",".join(sorted(set(aug_splits))) if aug_splits else "all"

    tokens: list[str] = []
    if include_raw:
        tokens.append(f"raw={raw_dir_name}")
    if include_processed:
        tokens.append(f"processed={processed_dir_name}")
    if include_augmented:
        tokens.append(f"aug={augmented_dir_name}[{joined_aug}]")

    split_name = infer_split_name(raw_dir_name=raw_dir_name, processed_dir_name=processed_dir_name)
    if split_name:
        tokens.append(f"split={split_name}")

    return " | ".join(tokens) if tokens else "no_dataset_selected"


def combo_slug_for_args(
    args: list[str],
    *,
    is_training: bool,
    is_evaluation: bool,
) -> str:
    raw_dir_name = get_arg_value(args, "--raw-dir-name", "lasalle_db1")
    processed_dir_name = get_arg_value(args, "--processed-dir-name", "lasalle_db1_processed")
    aug_splits_raw = get_arg_value(args, "--aug-splits", "__disabled__")

    include_raw = bool_flag(args, "include-raw", raw_dir_name != "__disabled__")
    include_processed = bool_flag(args, "include-processed", False)
    include_augmented_default = True if is_training and not is_evaluation else False
    include_augmented = bool_flag(args, "include-augmented", include_augmented_default)

    if raw_dir_name == "__disabled__":
        include_raw = False
    if aug_splits_raw.strip() == "__disabled__":
        include_augmented = False

    raw_key = Path(raw_dir_name).name.lower()
    processed_key = Path(processed_dir_name).name.lower()
    raw_is_lasalle = "lasalle" in raw_key
    processed_is_lfw = "lfw" in processed_key

    base_data_dir = get_arg_value(args, "--base-data-dir", "data").replace("\\", "/").lower()
    raw_dir_lower = raw_dir_name.replace("\\", "/").lower()
    is_clean_split = "split_lasalle" in base_data_dir or "split_lasalle" in raw_dir_lower

    if is_clean_split:
        family = "lasalleclean"
    elif include_raw and raw_is_lasalle:
        family = "lasalle"
    elif include_processed and processed_is_lfw:
        family = "lfw"
    elif include_raw and include_processed:
        family = "hybrid"
    elif include_raw:
        family = "raw"
    elif include_processed:
        family = "processed"
    else:
        family = "dataset"

    options: list[str] = []
    include_r_flag = include_raw and family not in {"lasalle", "lasalleclean", "hybrid"}
    include_p_flag = include_processed and family not in {"lfw", "hybrid"}

    if include_r_flag:
        options.append("r")
    if include_p_flag:
        options.append("p")

    if include_augmented:
        aug_splits = {
            value.strip().lower()
            for value in aug_splits_raw.split(",")
            if value.strip() and value.strip() != "__disabled__"
        }
        if "light" in aug_splits:
            options.append("l")
        if "medium" in aug_splits:
            options.append("m")

    if not options:
        return family
    return f"{family}-" + "".join(options)


def classical_artifact_paths(family_dir: str, slug: str) -> tuple[str, str]:
    """Model + labels paths for a classical dataset-combo slug.

    The clean La Salle split maps to the CANONICAL clean artifacts that the
    clean loop, the benchmarks (TAR@FAR, accuracy ratio, comparison) and the
    live ``detect.py`` defaults all share - not the legacy ``trainer_<slug>``
    naming, so the menu loop and the benchmark loop can never diverge again.
    """
    if slug == "lasalleclean":
        return (
            f"models/{family_dir}/lasalle_clean.yml",
            f"models/{family_dir}/labels_lasalle_clean.json",
        )
    if slug.startswith("lasalleclean-"):
        flags = slug.split("-", 1)[1]
        aug = {"l": "aug_light", "m": "aug_medium", "lm": "aug_light_medium"}.get(
            flags, f"aug_{flags}"
        )
        return (
            f"models/{family_dir}/lasalle_clean_{aug}.yml",
            f"models/{family_dir}/labels_lasalle_clean_{aug}.json",
        )
    return (
        f"models/{family_dir}/trainer_{slug}.yml",
        f"models/{family_dir}/labels_{slug}.json",
    )


CLASSICAL_MODEL_DIRS = {
    "LBPH": "lbph",
    "Eigenfaces": "eigenfaces",
    "Fisherfaces": "fisherfaces",
}


def auto_artifact_args_for_action(
    *,
    model_name: str,
    rel_script: str,
    base_args: list[str],
    is_training: bool,
    is_evaluation: bool,
) -> list[str]:
    # Respect explicit user-provided artifact paths.
    if model_name in CLASSICAL_MODEL_DIRS:
        family_dir = CLASSICAL_MODEL_DIRS[model_name]
        if is_training:
            if has_flag(base_args, "--model-output") or has_flag(base_args, "--labels-output"):
                return []
            slug = combo_slug_for_args(base_args, is_training=True, is_evaluation=False)
            model_path, labels_path = classical_artifact_paths(family_dir, slug)
            return ["--model-output", model_path, "--labels-output", labels_path]
        if is_evaluation:
            if has_flag(base_args, "--model-path") or has_flag(base_args, "--labels-path"):
                return []
            slug = combo_slug_for_args(base_args, is_training=False, is_evaluation=True)
            model_path, labels_path = classical_artifact_paths(family_dir, slug)
            return ["--model-path", model_path, "--labels-path", labels_path]

    if model_name in {"ArcFace", "ArcFace MobileNet INT8"}:
        if is_training and not has_flag(base_args, "--enrollment-output"):
            slug = combo_slug_for_args(base_args, is_training=True, is_evaluation=False)
            return [
                "--enrollment-output",
                f"models/arcface_mobilenet/enrollment_{slug}.json",
            ]
        if is_evaluation and not has_flag(base_args, "--enrollment-path"):
            slug = combo_slug_for_args(base_args, is_training=False, is_evaluation=True)
            return [
                "--enrollment-path",
                f"models/arcface_mobilenet/enrollment_{slug}.json",
            ]

    if model_name == "MobileFaceNet":
        if is_training and not has_flag(base_args, "--enrollment-output"):
            slug = combo_slug_for_args(base_args, is_training=True, is_evaluation=False)
            return [
                "--enrollment-output",
                f"models/yunet_mobilefacenet/enrollment_{slug}.json",
            ]
        if is_evaluation and not has_flag(base_args, "--enrollment-path"):
            slug = combo_slug_for_args(base_args, is_training=False, is_evaluation=True)
            return [
                "--enrollment-path",
                f"models/yunet_mobilefacenet/enrollment_{slug}.json",
            ]

    if model_name == "EdgeFace":
        if is_training and not has_flag(base_args, "--enrollment-output"):
            slug = combo_slug_for_args(base_args, is_training=True, is_evaluation=False)
            return [
                "--enrollment-output",
                f"models/edgeface/enrollment_{slug}.json",
            ]
        if is_evaluation and not has_flag(base_args, "--enrollment-path"):
            slug = combo_slug_for_args(base_args, is_training=False, is_evaluation=True)
            return [
                "--enrollment-path",
                f"models/edgeface/enrollment_{slug}.json",
            ]

    return []


def warn_if_missing_auto_artifacts(args: list[str], is_evaluation: bool) -> list[str]:
    if not is_evaluation:
        return []
    path_flags = ["--model-path", "--labels-path", "--enrollment-path"]
    checked_any = False
    missing_paths: list[str] = []
    for flag in path_flags:
        if not has_flag(args, flag):
            continue
        value = get_arg_value(args, flag, "").strip()
        if not value:
            continue
        checked_any = True
        if not resolve_path(value).exists():
            print(f"[WARN] Selected artifact does not exist yet: {value}")
            missing_paths.append(value)
    if checked_any:
        print("[INFO] If needed, override with Optional extra args.")
    return missing_paths


def maybe_confirm_existing_dataset_combo(
    *,
    model_name: str,
    final_args: list[str],
    is_training: bool,
    is_evaluation: bool,
) -> bool:
    model_entities = entities_for_menu_model(model_name)
    if not model_entities:
        return True

    selected_label = build_dataset_label_from_args(
        final_args,
        is_training=is_training,
        is_evaluation=is_evaluation,
    )
    matches = [row for row in model_entities if row.get("dataset_label", "") == selected_label]
    if not matches:
        return True

    print("\n[INFO] Existing dataset combination detected for this model:")
    print(f"  selected: {selected_label}")
    for row in matches[:5]:
        hit_rate_display = (
            f"{row['hit_rate']:.2f}%"
            if row.get("hit_rate") is not None
            else "N/A"
        )
        print(
            f"  - variant={row.get('model_variant', 'default')} "
            f"| hit={hit_rate_display} "
            f"| eval={row.get('evaluated_images', 0)} "
            f"| entity={row.get('entity_key', 'n/a')}"
        )

    answer = input("Continue anyway? (y/n, default n): ").strip().lower()
    return answer in {"y", "yes"}


def print_benchmark_overview() -> None:
    fps_by_algo = collect_fps_summary()
    entity_rows = collect_evaluation_entities()
    rows: list[dict] = []

    def compact_variant_tag(variant: str) -> str:
        value = variant.strip().lower()
        if not value:
            return "default"
        if value.startswith("trainer_") and "_labels_" in value:
            value = value.split("_labels_", 1)[0]
        if value.startswith("trainer_"):
            value = value[len("trainer_") :]
        if value.startswith("enrollment_"):
            value = value[len("enrollment_") :]
        for prefix in ("processed-", "raw-", "hybrid-", "lasalle-", "lfw-"):
            if value.startswith(prefix):
                value = value[len(prefix) :]
                break
        value = value.strip("_-")
        if value in {"", "default"}:
            return "default"
        if value == "processed":
            return "p"
        if value == "raw":
            return "r"
        value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
        return value or "default"

    for model_name, cfg in BENCHMARK_OVERVIEW_CONFIG.items():
        model_entities = [row for row in entity_rows if entity_matches_model_name(model_name, row)]

        algo_key = str(cfg["fps_algorithm"]).strip().lower()
        fps_value = fps_by_algo.get(algo_key)
        size_display = get_model_info(model_name)["size"]

        if model_entities:
            for row in model_entities:
                variant_tag = compact_variant_tag(str(row.get("model_variant", "")))
                model_entity = model_name if variant_tag == "default" else f"{model_name}-{variant_tag}"
                rows.append(
                    {
                        "model": model_entity,
                        "hit_rate": row.get("hit_rate"),
                        "accuracy": row.get("accuracy"),
                        "fps": fps_value,
                        "size": size_display,
                    }
                )
            continue

        report_path = resolve_path(cfg["eval_report"])
        report_payload = load_json_if_exists(report_path)
        rows.append(
            {
                "model": model_name,
                "hit_rate": extract_hit_rate_percent(report_payload),
                "accuracy": extract_accuracy_percent(report_payload),
                "fps": fps_value,
                "size": size_display,
            }
        )

    rows.sort(
        key=lambda row: (
            row["hit_rate"] if row["hit_rate"] is not None else float("-inf"),
            row["accuracy"] if row["accuracy"] is not None else float("-inf"),
        ),
        reverse=True,
    )

    print("\nOverview (model entities)")
    print(f"{'Model':<36} {'Hit Rate':>10} {'Accuracy':>10} {'Avg FPS':>10} {'Size':>12}")
    print(f"{'-'*36} {'-'*10} {'-'*10} {'-'*10} {'-'*12}")
    for row in rows:
        hit_rate_display = f"{row['hit_rate']:.2f}%" if row["hit_rate"] is not None else "N/A"
        accuracy_display = f"{row['accuracy']:.2f}%" if row["accuracy"] is not None else "N/A"
        fps_display = f"{row['fps']:.2f}" if row["fps"] is not None else "N/A"
        print(
            f"{row['model']:<36} {hit_rate_display:>10} {accuracy_display:>10} "
            f"{fps_display:>10} {row['size']:>12}"
        )


def get_model_info(model_name: str) -> dict:
    cfg = MODEL_INFO_CONFIG.get(model_name, {})
    evaluated_reports = [resolve_path(p) for p in cfg.get("evaluated_reports", [])]
    size_paths = [resolve_path(p) for p in cfg.get("size_paths", [])]

    evaluated = bool(evaluated_reports) and any(p.exists() for p in evaluated_reports)

    if model_name in {"LBPH", "Eigenfaces", "Fisherfaces"}:
        model_dir_rel = {
            "LBPH": "models/lbph",
            "Eigenfaces": "models/eigenfaces",
            "Fisherfaces": "models/fisherfaces",
        }[model_name]
        model_dir = resolve_path(model_dir_rel)

        def pair_suffix(stem: str, prefix: str) -> str:
            if stem == prefix:
                return ""
            if stem.startswith(prefix + "_"):
                return stem[len(prefix) + 1 :]
            if stem.startswith(prefix):
                return stem[len(prefix) :].lstrip("_-")
            return stem

        trained = False
        if model_dir.exists() and model_dir.is_dir():
            trainers = list(model_dir.glob("trainer*.yml"))
            labels = list(model_dir.glob("labels*.json"))
            label_suffixes = {pair_suffix(label.stem, "labels") for label in labels}
            trained = any(pair_suffix(trainer.stem, "trainer") in label_suffixes for trainer in trainers)

        size_bytes = path_size_bytes(model_dir)
    else:
        trained_markers = [resolve_path(p) for p in cfg.get("trained_markers", [])]
        trained = bool(trained_markers) and all(p.exists() for p in trained_markers)
        size_bytes = sum(path_size_bytes(p) for p in size_paths)

    return {
        "trained": trained,
        "evaluated": evaluated,
        "size": format_size(size_bytes),
    }


def int8_model_pack_ready() -> bool:
    if not INT8_MODEL_DIR.exists():
        return False
    return any(p.exists() for p in INT8_REQUIRED_MODELS)


def get_python_command() -> list[str]:
    # Always prefer global interpreter so menu actions are not tied to .venv.
    configured = os.environ.get("FACE_G3_PYTHON", "").strip()
    if configured:
        return shlex.split(configured)
    return ["python"]


def has_flag(args: list[str], flag: str) -> bool:
    return any(arg == flag or arg.startswith(f"{flag}=") for arg in args)


def is_training_action(action_label: str, rel_script: str) -> bool:
    return rel_script.endswith("trainer.py") and action_label.startswith("train")


def is_evaluate_action(action_label: str, rel_script: str) -> bool:
    return rel_script.endswith("evaluate.py") and action_label.startswith("evaluate")


def is_live_detect_action(action_label: str, rel_script: str) -> bool:
    script_name = Path(rel_script).name.lower()
    return action_label.startswith("live detect") and script_name in {"detect.py", "face_detect.py"}


def remove_flag_and_value(args: list[str], flag: str) -> list[str]:
    out: list[str] = []
    skip_next = False
    for idx, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == flag:
            if idx + 1 < len(args):
                skip_next = True
            continue
        if arg.startswith(f"{flag}="):
            continue
        out.append(arg)
    return out


@dataclass
class EvalArtifactOption:
    label: str
    args: list[str]
    exists: bool


def relative_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def artifact_suffix(stem: str, prefix: str) -> str:
    if stem == prefix:
        return ""
    if stem.startswith(prefix + "_"):
        return stem[len(prefix) + 1 :]
    if stem.startswith(prefix):
        return stem[len(prefix) :].lstrip("_-")
    return stem


def discover_pair_artifacts(model_dir_rel: str) -> list[EvalArtifactOption]:
    model_dir = resolve_path(model_dir_rel)
    if not model_dir.exists() or not model_dir.is_dir():
        return []

    # Canonical clean artifacts (lasalle_clean*.yml) plus legacy trainer_*.yml.
    trainers = list(model_dir.glob("*.yml"))
    labels = list(model_dir.glob("labels*.json"))
    label_by_suffix: dict[str, Path] = {}
    for label_path in labels:
        suffix = artifact_suffix(label_path.stem, "labels")
        label_by_suffix[suffix] = label_path

    def clean_priority(suffix: str) -> int:
        # Clean-split artifacts first (baseline, then aug variants), legacy last.
        if suffix == "lasalle_clean":
            return 0
        if suffix.startswith("lasalle_clean"):
            return 1
        return 2

    options: list[tuple[int, float, EvalArtifactOption]] = []
    for trainer_path in trainers:
        suffix = artifact_suffix(trainer_path.stem, "trainer")
        label_path = label_by_suffix.get(suffix)
        if label_path is None:
            continue
        trainer_rel = relative_to_project(trainer_path)
        labels_rel = relative_to_project(label_path)
        priority = clean_priority(suffix)
        display_suffix = suffix if suffix else "default"
        if priority == 0:
            display_suffix += " (CLEAN - recommended)"
        elif priority == 2:
            display_suffix += " (legacy)"
        mtime = max(trainer_path.stat().st_mtime, label_path.stat().st_mtime)
        options.append(
            (
                priority,
                -mtime,
                EvalArtifactOption(
                    label=f"{display_suffix} ({trainer_rel} + {labels_rel})",
                    args=[
                        "--model-path",
                        trainer_rel,
                        "--labels-path",
                        labels_rel,
                    ],
                    exists=True,
                ),
            )
        )

    options.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in options]


def discover_enrollment_artifacts(model_dir_rel: str) -> list[EvalArtifactOption]:
    model_dir = resolve_path(model_dir_rel)
    if not model_dir.exists() or not model_dir.is_dir():
        return []

    files = list(model_dir.glob("enrollment*.json"))
    options: list[tuple[float, EvalArtifactOption]] = []
    for enrollment_path in files:
        enrollment_rel = relative_to_project(enrollment_path)
        suffix = artifact_suffix(enrollment_path.stem, "enrollment")
        display_suffix = suffix if suffix else "default"
        options.append(
            (
                enrollment_path.stat().st_mtime,
                EvalArtifactOption(
                    label=f"{display_suffix} ({enrollment_rel})",
                    args=["--enrollment-path", enrollment_rel],
                    exists=True,
                ),
            )
        )
    options.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in options]


def discover_eval_artifact_options(model_name: str) -> list[EvalArtifactOption]:
    if model_name == "LBPH":
        return discover_pair_artifacts("models/lbph")
    if model_name == "Eigenfaces":
        return discover_pair_artifacts("models/eigenfaces")
    if model_name == "Fisherfaces":
        return discover_pair_artifacts("models/fisherfaces")
    if model_name in {"ArcFace", "ArcFace MobileNet INT8"}:
        return discover_enrollment_artifacts("models/arcface_mobilenet")
    if model_name == "MobileFaceNet":
        return discover_enrollment_artifacts("models/yunet_mobilefacenet")
    if model_name == "EdgeFace":
        return discover_enrollment_artifacts("models/edgeface")
    return []


def choose_eval_artifact_args(
    *,
    model_name: str,
    base_args: list[str],
    auto_args: list[str],
) -> list[str]:
    # Respect explicit user-provided artifact paths.
    if has_flag(base_args, "--model-path") or has_flag(base_args, "--labels-path") or has_flag(base_args, "--enrollment-path"):
        return auto_args

    auto_exists = True
    auto_label_parts: list[str] = []
    for flag in ("--model-path", "--labels-path", "--enrollment-path"):
        if not has_flag(auto_args, flag):
            continue
        value = get_arg_value(auto_args, flag, "").strip()
        if not value:
            continue
        auto_label_parts.append(f"{flag}={value}")
        if not resolve_path(value).exists():
            auto_exists = False
    if not auto_label_parts:
        return auto_args

    options: list[EvalArtifactOption] = [
        EvalArtifactOption(
            label="auto dataset-match " + " | ".join(auto_label_parts),
            args=auto_args,
            exists=auto_exists,
        )
    ]
    for row in discover_eval_artifact_options(model_name):
        if row.args != auto_args:
            options.append(row)

    if len(options) <= 1:
        return auto_args

    print("\nChoose trained artifact for evaluation:")
    for idx, option in enumerate(options, start=1):
        status = "ready" if option.exists else "missing"
        print(f" {idx:2d}. [{status}] {option.label}")
    selected = input("Enter choice (default: 1): ").strip()
    if not selected:
        return options[0].args
    if not selected.isdigit():
        print("[WARN] Invalid choice; using auto dataset-match artifact.")
        return options[0].args
    option_index = int(selected) - 1
    if option_index < 0 or option_index >= len(options):
        print("[WARN] Choice out of range; using auto dataset-match artifact.")
        return options[0].args
    return options[option_index].args


def choose_live_artifact_args(
    *,
    model_name: str,
    base_args: list[str],
) -> list[str]:
    if has_flag(base_args, "--model-path") or has_flag(base_args, "--labels-path") or has_flag(base_args, "--enrollment-path"):
        return []

    options = discover_eval_artifact_options(model_name)
    if not options:
        return []
    if len(options) == 1:
        return options[0].args

    print("\nChoose trained artifact for live detect:")
    for idx, option in enumerate(options, start=1):
        status = "ready" if option.exists else "missing"
        print(f" {idx:2d}. [{status}] {option.label}")
    selected = input("Enter choice (default: 1): ").strip()
    if not selected:
        return options[0].args
    if not selected.isdigit():
        print("[WARN] Invalid choice; using most recent artifact.")
        return options[0].args
    option_index = int(selected) - 1
    if option_index < 0 or option_index >= len(options):
        print("[WARN] Choice out of range; using most recent artifact.")
        return options[0].args
    return options[option_index].args


CLASSICAL_MODEL_NAMES = {"LBPH", "Eigenfaces", "Fisherfaces"}


def prompt_detector_args(model_name: str, *, is_live: bool = False) -> list[str]:
    """Ask which face detector (Viola-Jones vs YuNet) to use for raw/live inputs.

    Returns ``["--detector", choice]`` or ``[]`` (Enter = keep the script default,
    i.e. the FACE_G3_DETECTOR env var, else Haar). Only classical recognizers run
    the toggle; the cropped clean split skips detection entirely.
    """
    if model_name not in CLASSICAL_MODEL_NAMES:
        return []
    default_backend = os.environ.get("FACE_G3_DETECTOR", "haar").strip().lower() or "haar"
    print("\nSelect face detector:")
    print("  1. Haar / Viola-Jones (classic cascade, frontal, fast)")
    print("  2. YuNet (CNN; robust to pose/lighting, adds confidence + landmarks)")
    if not is_live:
        print("  (Affects raw-photo / LFW detection only; the cropped clean split skips it.)")
    selected = input(f"Enter choice (default: {default_backend}): ").strip()
    if selected == "1":
        return ["--detector", "haar"]
    if selected == "2":
        return ["--detector", "yunet"]
    if selected:
        print(f"[INFO] Invalid choice; keeping default ({default_backend}).")
    return []


def prompt_core_dataset_args(is_training: bool, model_name: str = "") -> list[str]:
    phase_label = "training" if is_training else "evaluation"
    is_classical = model_name in CLASSICAL_MODEL_NAMES

    print(f"\nSelect base dataset source for {phase_label}:")
    print("  1. La Salle CLEAN split (held-out, recommended) -> data/split_lasalle/{train|test} [pre-cropped]")
    print("  2. La Salle raw  -> data/lasalle_db1")
    print("  3. LFW only      -> data/lfw-dataset")
    print("  4. Both          -> data/lasalle_db1 + data/lfw-dataset")
    selected = input("Enter choice (default: 1): ").strip()

    # Option 1: the clean leakage-free held-out La Salle split (pre-cropped 100x100
    # faces). Train on /train, evaluate on the held-out /test, no Haar / no fallback.
    if selected in {"", "1"}:
        raw_dir = "train" if is_training else "test"
        print(f"[INFO] Clean split selected: {'train' if is_training else 'held-out test'} "
              "(pre-cropped, leakage-free). For baseline+aug side-by-side use the "
              "Benchmark > 'run clean classical loop' action.")
        args = [
            "--base-data-dir", "data/split_lasalle",
            "--raw-dir-name", raw_dir,
            "--processed-dir-name", "lasalle_db1_processed",
            "--include-raw",
        ]
        if is_classical:
            args.append("--assume-cropped")
        return args

    include_raw = True
    include_processed = False
    processed_dir_name = "lasalle_db1_processed"
    if selected == "2":
        include_raw = True
        include_processed = False
        processed_dir_name = "lasalle_db1_processed"
    elif selected == "3":
        include_raw = False
        include_processed = True
        processed_dir_name = "lfw-dataset"
    elif selected == "4":
        include_raw = True
        include_processed = True
        processed_dir_name = "lfw-dataset"
    else:
        print("[INFO] Invalid choice; defaulting to La Salle raw.")
        processed_dir_name = "lasalle_db1_processed"

    raw_default_hint = "Y/n" if include_raw else "y/N"
    processed_default_hint = "Y/n" if include_processed else "y/N"

    include_raw_input = input(f"Include raw dataset (lasalle_db1)? ({raw_default_hint}): ").strip().lower()
    if include_raw_input in {"y", "yes"}:
        include_raw = True
    elif include_raw_input in {"n", "no"}:
        include_raw = False

    include_processed_input = input(
        f"Include processed dataset ({processed_dir_name})? ({processed_default_hint}): "
    ).strip().lower()
    if include_processed_input in {"y", "yes"}:
        include_processed = True
    elif include_processed_input in {"n", "no"}:
        include_processed = False

    args: list[str] = [
        "--base-data-dir",
        "data",
        "--raw-dir-name",
        "lasalle_db1" if include_raw else "__disabled__",
        "--processed-dir-name",
        processed_dir_name,
    ]
    # Raw photos / LFW need Haar detection; the classical recognizers default to
    # --assume-cropped (for the clean split), so turn it off for these sources.
    if is_classical:
        args.append("--no-assume-cropped")

    if is_training:
        if include_raw:
            args.append("--include-raw")
    if include_processed:
        args.append("--include-processed")

    return args


def infer_augmented_dir_from_core_args(core_args: list[str]) -> str:
    raw_dir_name = get_arg_value(core_args, "--raw-dir-name", "lasalle_db1")
    processed_dir_name = get_arg_value(core_args, "--processed-dir-name", "lasalle_db1_processed")
    include_raw = bool_flag(core_args, "include-raw", raw_dir_name != "__disabled__")
    include_processed = bool_flag(core_args, "include-processed", False)

    raw_key = Path(raw_dir_name).name.lower()
    processed_key = Path(processed_dir_name).name.lower()
    has_lasalle = (include_raw and "lasalle" in raw_key) or (include_processed and "lasalle" in processed_key)
    has_lfw = (include_raw and "lfw" in raw_key) or (include_processed and "lfw" in processed_key)

    if has_lasalle and not has_lfw:
        return "split_augmented41mods_lasalle"
    if has_lfw and not has_lasalle:
        return "split_augmented41mods_lfw"
    return "split_augmented41mods"


def prompt_augmented_dataset_args(is_evaluation: bool, core_args: list[str]) -> list[str]:
    base_data_dir = get_arg_value(core_args, "--base-data-dir", "data").replace("\\", "/").lower()
    if "split_lasalle" in base_data_dir:
        # The clean split keeps the menu loop purely baseline; leakage-safe
        # train-only augmentation lives in the 'run clean classical loop' action.
        print("\n[INFO] Clean split: skipping augmentation here (baseline loop). Use "
              "Benchmark > 'run clean classical loop' for the leakage-safe aug variant.")
        args = ["--aug-splits", "__disabled__"]
        if is_evaluation:
            args.append("--no-include-augmented")
        return args

    augmented_dir_name = infer_augmented_dir_from_core_args(core_args)
    print("\nSelect augmented datasets (comma/space separated numbers):")
    print(f"  1. light   -> data/{augmented_dir_name}/light")
    print(f"  2. medium  -> data/{augmented_dir_name}/medium")
    selected = input("Enter choices (blank = none): ").strip()

    if not selected:
        chosen: list[str] = []
    else:
        tokens = selected.replace(",", " ").split()
        mapping = {"1": "light", "2": "medium"}
        chosen = []
        for token in tokens:
            value = mapping.get(token)
            if value is None:
                print(f"[WARN] Ignoring invalid choice: {token}")
                continue
            if value not in chosen:
                chosen.append(value)

    args: list[str] = [
        "--augmented-dir-name",
        augmented_dir_name,
    ]
    if chosen:
        args.extend(["--aug-splits", ",".join(chosen)])
        if is_evaluation:
            args.append("--include-augmented")
    else:
        args.extend(["--aug-splits", "__disabled__"])
        if is_evaluation:
            args.append("--no-include-augmented")

    return args


def prompt_light_front_independence_args(model_name: str) -> list[str]:
    print("\nSelect light-front independence dataset run:")
    print("  1. la salle db (processed)")

    if model_name in {"Eigenfaces", "Fisherfaces"}:
        for idx in range(1, 7):
            print(f"  {idx + 1}. lfw {idx} (segment {idx}/6)")
        print("  8. lfw all (complete cross-slice, segments 1..6)")
        print("Mode:")
        print("  - intra fast: within-segment only (faster, partial pair coverage)")
        print("  - complete cross-slice: full pair coverage across segments")
        selected = input("Enter choice (default: 1): ").strip()
        if selected == "8":
            return [
                "--dataset-source",
                "lfw-dataset",
                "--segment-count",
                "6",
                "--segment-index",
                "1",
                "--segment-mode",
                "complete",
                "--run-all-segments",
                "1",
            ]
        if selected in {"2", "3", "4", "5", "6", "7"}:
            seg_idx = int(selected) - 1
            mode = input("Segment mode [1=intra fast, 2=complete cross-slice] (default: 2): ").strip()
            segment_mode = "intra" if mode == "1" else "complete"
            lfw_dir = resolve_path("data/lfw-dataset")
            try:
                total_ids = sum(1 for p in lfw_dir.iterdir() if p.is_dir())
            except Exception:
                total_ids = 0
            if total_ids >= 2:
                total_pairs = (total_ids * (total_ids - 1)) // 2
                pair_start = ((seg_idx - 1) * total_pairs) // 6
                pair_end = (seg_idx * total_pairs) // 6
                seg_pairs = max(0, pair_end - pair_start)
                print(
                    "[INFO] Pre-run estimate: "
                    f"LFW identities={total_ids:,}, total unique pairs={total_pairs:,}, "
                    f"segment {seg_idx}/6 pairs={seg_pairs:,}, mode={segment_mode}"
                )
            else:
                print("[INFO] Pre-run estimate unavailable (LFW identity count not found).")
            return [
                "--dataset-source",
                "lfw-dataset",
                "--segment-count",
                "6",
                "--segment-index",
                str(seg_idx),
                "--segment-mode",
                segment_mode,
            ]
    else:
        print("  2. lfw 1 (first half)")
        print("  3. lfw 2 (second half)")
        selected = input("Enter choice (default: 1): ").strip()
        if selected == "2":
            return [
                "--dataset-source",
                "lfw-dataset",
                "--segment-count",
                "2",
                "--segment-index",
                "1",
            ]
        if selected == "3":
            return [
                "--dataset-source",
                "lfw-dataset",
                "--segment-count",
                "2",
                "--segment-index",
                "2",
            ]

    return [
        "--dataset-source",
        "lasalle_db1_processed",
    ]


def run_python_script(rel_script: str, extra_args: list[str], label: str) -> int:
    script_path = resolve_path(rel_script)
    cmd = [*get_python_command(), str(script_path), *extra_args]
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "").strip()
    project_root_str = str(PROJECT_ROOT)
    env["PYTHONPATH"] = (
        f"{project_root_str}{os.pathsep}{current_pythonpath}"
        if current_pythonpath
        else project_root_str
    )
    print(f"\n[RUN] {label}")
    print(f"[CMD] {' '.join(shlex.quote(part) for part in cmd)}\n")
    completed = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    print(f"\n[EXIT] code={completed.returncode}")
    return completed.returncode


def maybe_prepare_int8_pack() -> bool:
    if int8_model_pack_ready():
        return True

    print("\n[INFO] ArcFace INT8 model pack is missing.")
    print("Required first-time setup:")
    print("  1) Download FP32 ArcFace model")
    print("  2) Quantize to INT8 pack")
    answer = input("Run setup now? (y/n): ").strip().lower()
    if answer not in {"y", "yes"}:
        return False

    rc = run_python_script("src/arcface/setup_model.py", [], "ArcFace setup model")
    if rc != 0:
        return False

    rc = run_python_script("src/arcface_mobilenet_int8/quantize_model.py", [], "ArcFace INT8 quantize model")
    if rc != 0:
        return False

    return int8_model_pack_ready()


def print_model_menu() -> None:
    print("\nChoose a model/type:")
    for idx, (model_name, _) in enumerate(GROUPED_CHOICES, start=1):
        print(f"{idx:2d}. {model_name}")
    print(" q. Quit")


def print_model_actions_menu(model_name: str, actions: list[tuple[str, str]]) -> None:
    info = get_model_info(model_name)
    trained_state = "trained" if info["trained"] else "untrained"
    eval_state = "evaluated" if info["evaluated"] else "not evaluated"

    print(f"\n[{model_name}]")
    print(f"State: {trained_state}")
    print(f"Evaluation: {eval_state}")
    print(f"Size: {info['size']}")
    model_entities = entities_for_menu_model(model_name)
    if model_entities:
        print(f"Saved dataset combos: {len(model_entities)}")
        for row in model_entities[:3]:
            hit_rate_display = (
                f"{row['hit_rate']:.2f}%"
                if row.get("hit_rate") is not None
                else "N/A"
            )
            print(
                f"  - {row.get('dataset_label', 'unknown')} "
                f"(variant={row.get('model_variant', 'default')}, hit={hit_rate_display})"
            )
    else:
        print("Saved dataset combos: 0")
    if model_name == "Benchmark":
        print_benchmark_overview()
    print("\nChoices:")
    for idx, (action_label, _) in enumerate(actions, start=1):
        print(f"{idx:2d}. {action_label}")
    print(" b. Back")
    print(" q. Quit")


def run_choice(model_name: str, action_label: str, rel_script: str, extra_args: list[str]) -> int:
    if has_flag(extra_args, "--run-all-segments"):
        base_args = remove_flag_and_value(extra_args, "--run-all-segments")
        rc = 0
        for seg_idx in range(1, 7):
            seg_args = remove_flag_and_value(base_args, "--segment-index")
            seg_args.extend(["--segment-index", str(seg_idx)])
            script_path = resolve_path(rel_script)
            cmd = [*get_python_command(), str(script_path), *seg_args]
            env = os.environ.copy()
            current_pythonpath = env.get("PYTHONPATH", "").strip()
            project_root_str = str(PROJECT_ROOT)
            env["PYTHONPATH"] = (
                f"{project_root_str}{os.pathsep}{current_pythonpath}"
                if current_pythonpath
                else project_root_str
            )
            print(f"\n[RUN] {model_name}: {action_label} (segment {seg_idx}/6, complete)")
            print(f"[CMD] {' '.join(shlex.quote(part) for part in cmd)}\n")
            completed = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
            print(f"\n[EXIT] code={completed.returncode}")
            rc = completed.returncode
            if rc != 0:
                return rc
        return rc

    script_path = resolve_path(rel_script)
    cmd = [*get_python_command(), str(script_path), *extra_args]
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "").strip()
    project_root_str = str(PROJECT_ROOT)
    env["PYTHONPATH"] = (
        f"{project_root_str}{os.pathsep}{current_pythonpath}"
        if current_pythonpath
        else project_root_str
    )

    print(f"\n[RUN] {model_name}: {action_label}")
    print(f"[CMD] {' '.join(shlex.quote(part) for part in cmd)}\n")

    completed = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    print(f"\n[EXIT] code={completed.returncode}")
    return completed.returncode


def main() -> int:
    while True:
        print_model_menu()
        selected_model = input("\nEnter model number (or q): ").strip().lower()

        if selected_model in {"q", "quit", "exit"}:
            print("Exiting.")
            return 0

        if not selected_model.isdigit():
            print("Invalid input. Enter a model number or q.")
            continue

        model_index = int(selected_model) - 1
        if model_index < 0 or model_index >= len(GROUPED_CHOICES):
            print("Invalid model number.")
            continue

        model_name, actions = GROUPED_CHOICES[model_index]

        while True:
            print_model_actions_menu(model_name, actions)
            selected_action = input("\nEnter choice number (or b/q): ").strip().lower()

            if selected_action in {"q", "quit", "exit"}:
                print("Exiting.")
                return 0
            if selected_action in {"b", "back"}:
                break
            if not selected_action.isdigit():
                print("Invalid input. Enter an action number, b, or q.")
                continue

            action_index = int(selected_action) - 1
            if action_index < 0 or action_index >= len(actions):
                print("Invalid action number.")
                continue

            action_label, rel_script = actions[action_index]
            training_action = is_training_action(action_label, rel_script)
            evaluate_action = is_evaluate_action(action_label, rel_script)
            live_detect_action = is_live_detect_action(action_label, rel_script)
            if (
                model_name == "ArcFace MobileNet INT8"
                and action_label in {"train enrollment", "evaluate", "live detect"}
                and not int8_model_pack_ready()
            ):
                if not maybe_prepare_int8_pack():
                    print("[INFO] Skipping action because INT8 model pack is not ready.")
                    continue

            preset_args: list[str] = []
            if training_action or evaluate_action:
                core_dataset_args = prompt_core_dataset_args(
                    is_training=training_action, model_name=model_name
                )
                preset_args = [
                    *core_dataset_args,
                    *prompt_augmented_dataset_args(
                        is_evaluation=evaluate_action,
                        core_args=core_dataset_args,
                    ),
                ]
                # Detection only runs when inputs aren't pre-cropped; offer the
                # Haar/YuNet toggle for those classical raw/LFW runs.
                if "--assume-cropped" not in core_dataset_args:
                    preset_args += prompt_detector_args(model_name)
            elif live_detect_action:
                preset_args = prompt_detector_args(model_name, is_live=True)
            elif action_label == "independence test (light front)":
                preset_args = prompt_light_front_independence_args(model_name)

            extra = input("Optional extra args (or press Enter): ").strip()
            extra_args = shlex.split(extra) if extra else []
            if has_flag(extra_args, "--include-raw") or has_flag(extra_args, "--no-include-raw"):
                preset_args = [arg for arg in preset_args if arg != "--include-raw"]
            if has_flag(extra_args, "--include-processed") or has_flag(extra_args, "--no-include-processed"):
                preset_args = [arg for arg in preset_args if arg != "--include-processed"]
            if has_flag(extra_args, "--include-augmented") or has_flag(extra_args, "--no-include-augmented"):
                preset_args = [arg for arg in preset_args if arg not in {"--include-augmented", "--no-include-augmented"}]
            if has_flag(extra_args, "--base-data-dir"):
                preset_args = remove_flag_and_value(preset_args, "--base-data-dir")
            if has_flag(extra_args, "--raw-dir-name"):
                preset_args = remove_flag_and_value(preset_args, "--raw-dir-name")
            if has_flag(extra_args, "--processed-dir-name"):
                preset_args = remove_flag_and_value(preset_args, "--processed-dir-name")
            if has_flag(extra_args, "--augmented-dir-name"):
                preset_args = remove_flag_and_value(preset_args, "--augmented-dir-name")
            if has_flag(extra_args, "--aug-splits"):
                preset_args = remove_flag_and_value(preset_args, "--aug-splits")
            if has_flag(extra_args, "--dataset-source"):
                preset_args = remove_flag_and_value(preset_args, "--dataset-source")
            if has_flag(extra_args, "--segment-count"):
                preset_args = remove_flag_and_value(preset_args, "--segment-count")
            if has_flag(extra_args, "--segment-index"):
                preset_args = remove_flag_and_value(preset_args, "--segment-index")
            if has_flag(extra_args, "--detector"):
                preset_args = remove_flag_and_value(preset_args, "--detector")

            base_args = [*preset_args, *extra_args]
            auto_args = auto_artifact_args_for_action(
                model_name=model_name,
                rel_script=rel_script,
                base_args=base_args,
                is_training=training_action,
                is_evaluation=evaluate_action,
            )
            if evaluate_action:
                auto_args = choose_eval_artifact_args(
                    model_name=model_name,
                    base_args=base_args,
                    auto_args=auto_args,
                )
            if live_detect_action:
                auto_args = choose_live_artifact_args(
                    model_name=model_name,
                    base_args=base_args,
                )
            final_args = [*base_args, *auto_args]
            missing_eval_artifacts = warn_if_missing_auto_artifacts(
                final_args, is_evaluation=evaluate_action
            )
            if evaluate_action and missing_eval_artifacts:
                print("[ERROR] Evaluation cancelled because required artifacts are missing.")
                print("        Train this model first, or provide existing files via Optional extra args:")
                print("        - --model-path / --labels-path (LBPH/Eigenfaces/Fisherfaces)")
                print("        - --enrollment-path (ArcFace/MobileFaceNet/EdgeFace)")
                continue
            if training_action or evaluate_action:
                should_continue = maybe_confirm_existing_dataset_combo(
                    model_name=model_name,
                    final_args=final_args,
                    is_training=training_action,
                    is_evaluation=evaluate_action,
                )
                if not should_continue:
                    print("[INFO] Action cancelled. Choose another dataset combination or add custom args.")
                    continue
            run_choice(model_name, action_label, rel_script, final_args)

            again = input("\nRun another action for this model? (y/n): ").strip().lower()
            if again not in {"y", "yes"}:
                break


if __name__ == "__main__":
    raise SystemExit(main())
