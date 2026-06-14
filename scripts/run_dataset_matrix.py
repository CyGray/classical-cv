"""Dataset-composition matrix: train/eval every classical family on 5 training recipes.

Answers "what does the training-data composition do to each recognizer?" with a
single reproducible suite. For each family (lbph, eigenfaces, fisherfaces) it
trains five models from the SAME source DB (the leakage-free La Salle split):

  clean             split_lasalle/train as-is (280 imgs; 5 light_* + 5 dark_* per id)
  aug_light         clean + leakage-safe light tier        (280 + 560 = 840 imgs)
  aug_light_medium  clean + light + medium tiers           (280 + 560 + 560 = 1400 imgs)
  light_only        only the light_* half of clean         (140 imgs)
  dark_only         only the dark_* half of clean          (140 imgs)

and evaluates every model on three held-out probe sets:

  full   split_lasalle/test          (56 probes: 1 light_name + 1 dark_name per id)
  light  only the light_name probes  (28)
  dark   only the dark_name probes   (28)

plus a TAR@FAR / EER pass against LFW impostors (Haar-cropped ONCE, shared by
all 15 models, same protocol as src/benchmark/tar_at_far.py).

Outputs:
  reports/evaluation/dataset_matrix/<family>__<recipe>__test_<set>.json
  reports/benchmark/dataset_matrix_tar_far.{json,md}   (incremental; resumable)
  reports/benchmark/dataset_matrix.md                  (assembled numeric tables)

The canonical clean / aug_light models are reused if already trained (the
matrix stays bit-identical with SPEC_COMPARISON.md); use --force-train to rebuild.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

FAMILIES = ["lbph", "eigenfaces", "fisherfaces"]

SUBSET_ROOT = PROJECT_ROOT / "data" / "matrix_subsets"
EVAL_DIR = PROJECT_ROOT / "reports" / "evaluation" / "dataset_matrix"
TARFAR_JSON = PROJECT_ROOT / "reports" / "benchmark" / "dataset_matrix_tar_far.json"
TARFAR_MD = PROJECT_ROOT / "reports" / "benchmark" / "dataset_matrix_tar_far.md"
SUMMARY_MD = PROJECT_ROOT / "reports" / "benchmark" / "dataset_matrix.md"

AUG_ROOT_NAME = "split_augmented41mods_lasalle_clean"

# recipe -> (model stem, trainer dataset args, human description)
RECIPES: dict[str, dict] = {
    "clean": {
        "stem": "lasalle_clean",
        "train_args": [
            "--base-data-dir", "data/split_lasalle", "--raw-dir-name", "train",
            "--include-raw", "--no-include-augmented",
        ],
        "desc": "split_lasalle/train as-is (5 light_* + 5 dark_* poses per id)",
        "count_dirs": ["data/split_lasalle/train"],
    },
    "aug_light": {
        "stem": "lasalle_clean_aug_light",
        "train_args": [
            "--base-data-dir", "data", "--raw-dir-name", "split_lasalle/train",
            "--include-raw", "--augmented-dir-name", AUG_ROOT_NAME,
            "--include-augmented", "--aug-splits", "light",
        ],
        "desc": "clean + leakage-safe light augmentation tier",
        "count_dirs": ["data/split_lasalle/train", f"data/{AUG_ROOT_NAME}/light/train"],
    },
    "aug_light_medium": {
        "stem": "lasalle_clean_aug_light_medium",
        "train_args": [
            "--base-data-dir", "data", "--raw-dir-name", "split_lasalle/train",
            "--include-raw", "--augmented-dir-name", AUG_ROOT_NAME,
            "--include-augmented", "--aug-splits", "light,medium",
        ],
        "desc": "clean + light + medium augmentation tiers",
        "count_dirs": [
            "data/split_lasalle/train",
            f"data/{AUG_ROOT_NAME}/light/train",
            f"data/{AUG_ROOT_NAME}/medium/train",
        ],
    },
    "light_only": {
        "stem": "lasalle_light_only",
        "train_args": [
            "--base-data-dir", "data/matrix_subsets", "--raw-dir-name", "train_light",
            "--include-raw", "--no-include-augmented",
        ],
        "desc": "only the light_* half of the clean train split",
        "count_dirs": ["data/matrix_subsets/train_light"],
    },
    "dark_only": {
        "stem": "lasalle_dark_only",
        "train_args": [
            "--base-data-dir", "data/matrix_subsets", "--raw-dir-name", "train_dark",
            "--include-raw", "--no-include-augmented",
        ],
        "desc": "only the dark_* half of the clean train split",
        "count_dirs": ["data/matrix_subsets/train_dark"],
    },
}

# test set -> (--base-data-dir, --raw-dir-name)
TESTSETS: dict[str, tuple[str, str]] = {
    "full": ("data/split_lasalle", "test"),
    "light": ("data/matrix_subsets", "test_light"),
    "dark": ("data/matrix_subsets", "test_dark"),
}

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dataset-composition matrix for the classical recognizers.")
    parser.add_argument("--families", default=",".join(FAMILIES))
    parser.add_argument("--recipes", default=",".join(RECIPES))
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-tar-far", action="store_true")
    parser.add_argument("--force-train", action="store_true",
                        help="Retrain even when the model file already exists.")
    parser.add_argument("--tarfar-resume", action="store_true",
                        help="Skip (family, recipe) rows already present in the TAR@FAR JSON.")
    parser.add_argument("--impostor-dir", default="data/lfw-dataset")
    parser.add_argument("--impostor-max-identities", type=int, default=0)
    parser.add_argument("--impostor-max-per-id", type=int, default=0)
    return parser.parse_args()


def run(cmd: list[str], *, label: str) -> None:
    print(f"\n{'=' * 70}\n[RUN] {label}\n     {' '.join(cmd)}\n{'=' * 70}", flush=True)
    subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))


def model_paths(family: str, recipe: str) -> tuple[Path, Path]:
    stem = RECIPES[recipe]["stem"]
    return (
        PROJECT_ROOT / "models" / family / f"{stem}.yml",
        PROJECT_ROOT / "models" / family / f"labels_{stem}.json",
    )


def eval_report_path(family: str, recipe: str, testset: str) -> Path:
    return EVAL_DIR / f"{family}__{recipe}__test_{testset}.json"


def count_images(rel_dir: str) -> int:
    root = PROJECT_ROOT / rel_dir
    if not root.is_dir():
        return 0
    return sum(
        1
        for ident in root.iterdir() if ident.is_dir()
        for f in ident.iterdir() if f.suffix.lower() in IMG_EXTS
    )


def recipe_train_images(recipe: str) -> int:
    return sum(count_images(d) for d in RECIPES[recipe]["count_dirs"])


# --------------------------------------------------------------------------- #
# Stage 0: light_/dark_ subset folders (idempotent copies from split_lasalle)
# --------------------------------------------------------------------------- #
def build_subsets() -> None:
    jobs = [
        ("train", "light_", "train_light"),
        ("train", "dark_", "train_dark"),
        ("test", "light_", "test_light"),
        ("test", "dark_", "test_dark"),
    ]
    copied = 0
    for split, prefix, out_name in jobs:
        src_root = PROJECT_ROOT / "data" / "split_lasalle" / split
        dst_root = SUBSET_ROOT / out_name
        for ident_dir in sorted(p for p in src_root.iterdir() if p.is_dir()):
            for img in sorted(ident_dir.iterdir()):
                if img.suffix.lower() not in IMG_EXTS or not img.name.startswith(prefix):
                    continue
                dst = dst_root / ident_dir.name / img.name
                if dst.exists():
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(img, dst)
                copied += 1
    counts = {name: count_images(f"data/matrix_subsets/{name}")
              for _, _, name in jobs}
    print(f"[SUBSETS] copied {copied} new files | counts: {counts}", flush=True)


# --------------------------------------------------------------------------- #
# Stage 1+2: train and evaluate via the family CLIs (same wiring as clean loop)
# --------------------------------------------------------------------------- #
def train(py: str, family: str, recipe: str, force: bool) -> None:
    model, labels = model_paths(family, recipe)
    if model.exists() and labels.exists() and not force:
        print(f"[SKIP] {family}/{recipe}: model exists ({model.name})", flush=True)
        return
    cmd = [py, "-m", f"src.{family}.trainer"]
    cmd += RECIPES[recipe]["train_args"]
    cmd += [
        "--assume-cropped",
        "--model-output", str(model),
        "--labels-output", str(labels),
        "--max-images-per-person", "0",
    ]
    run(cmd, label=f"{family}: train {recipe}")


def evaluate(py: str, family: str, recipe: str, testset: str) -> None:
    model, labels = model_paths(family, recipe)
    base, raw = TESTSETS[testset]
    report = eval_report_path(family, recipe, testset)
    report.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        py, "-m", f"src.{family}.evaluate",
        "--base-data-dir", base,
        "--raw-dir-name", raw,
        "--include-raw",
        "--assume-cropped",
        "--model-path", str(model),
        "--labels-path", str(labels),
        "--run-tag", f"matrix_{recipe}_test_{testset}",
        "--report-json", str(report),
    ]
    run(cmd, label=f"{family}: evaluate {recipe} on test_{testset}")


# --------------------------------------------------------------------------- #
# Stage 3: TAR@FAR vs LFW impostors for every (family, recipe) model
# --------------------------------------------------------------------------- #
def run_tar_far(args: argparse.Namespace, families: list[str], recipes: list[str]) -> None:
    import cv2 as cv

    from src.benchmark.tar_at_far import (
        equal_error_rate,
        load_genuine_grays,
        load_impostor_rois,
        operating_point,
        root_path,
    )
    from src.classical_faces.pipeline import SPECS, load_label_map, load_recognizer
    from src.classical_faces.preprocess import IMG_SIZE, normalize_face

    target_fars = [1.058, 1.0, 0.1, 0.01]

    existing_rows: list[dict] = []
    if args.tarfar_resume and TARFAR_JSON.exists():
        existing_rows = json.loads(TARFAR_JSON.read_text(encoding="utf-8")).get("rows", [])
    done = {(r["family"], r["recipe"]) for r in existing_rows}

    todo = [
        (family, recipe)
        for family in families
        for recipe in recipes
        if (family, recipe) not in done and model_paths(family, recipe)[0].exists()
    ]
    if not todo:
        print("[TARFAR] nothing to score (all rows present or no models).", flush=True)
        return

    cascade = cv.CascadeClassifier(root_path("haar", "haarcascade_frontalface_default.xml"))
    if cascade.empty():
        raise FileNotFoundError("Could not load Haar cascade")

    print("[TARFAR] loading genuine tiles ...", flush=True)
    genuine_grays = load_genuine_grays(str(PROJECT_ROOT / "data" / "split_lasalle" / "test"))

    _, _, known_names = load_label_map(str(model_paths(families[0], "clean")[1]))
    print(f"[TARFAR] Haar-cropping impostors once ({args.impostor_dir}) ...", flush=True)
    impostor_rois, imp_skipped = load_impostor_rois(
        str(PROJECT_ROOT / args.impostor_dir),
        face_cascade=cascade,
        known_names=known_names,
        min_face_size=40,
        max_ids=args.impostor_max_identities,
        max_per_id=args.impostor_max_per_id,
    )
    print(f"[TARFAR] genuine={len(genuine_grays)} impostors={len(impostor_rois)} "
          f"(skipped {imp_skipped}) | models to score: {len(todo)}", flush=True)

    rows = list(existing_rows)

    def write_outputs() -> None:
        TARFAR_JSON.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "config": {
                "genuine_dir": "data/split_lasalle/test",
                "impostor_dir": args.impostor_dir,
                "n_impostors": len(impostor_rois),
                "target_far_percent": target_fars,
            },
            "rows": rows,
        }
        TARFAR_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        lines = [
            "# Dataset matrix - TAR @ FAR / FRR vs LFW impostors",
            "",
            f"Genuine: `data/split_lasalle/test` (56 held-out probes) | "
            f"Impostors: `{args.impostor_dir}` ({len(impostor_rois)} Haar-cropped faces).",
            "",
            "| Family | Recipe | Gallery imgs | TAR@1.058% | TAR@100ppm | Thr@100ppm | EER | Impostor scoring s |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for r in rows:
            ops = {op["target_far_percent"]: op for op in r["operating_points"]}
            op_ind = ops.get(1.058, {})
            op_spec = ops.get(0.01, {})
            eer = r.get("eer") or {}
            lines.append(
                f"| {r['family']} | {r['recipe']} | {r.get('gallery_images', '?')} | "
                f"{op_ind.get('tar_percent', float('nan')):.2f}% | "
                f"{op_spec.get('tar_percent', float('nan')):.2f}% | "
                f"{op_spec.get('threshold_predict_scale', float('nan')):.2f} | "
                f"{eer.get('eer_percent', float('nan')):.2f}% | "
                f"{r.get('impostor_seconds', 0.0):.0f} |"
            )
        lines.append("")
        TARFAR_MD.write_text("\n".join(lines), encoding="utf-8")

    for family, recipe in todo:
        spec = SPECS[family]
        model, labels = model_paths(family, recipe)
        _, id_to_name, _ = load_label_map(str(labels))
        recognizer = load_recognizer(spec, str(model))
        equalization = spec.default_equalization

        print(f"\n[TARFAR] {family}/{recipe}: scoring genuine (eq={equalization}) ...", flush=True)
        genuine = []
        for person, gray in genuine_grays:
            pred_id, dist = recognizer.predict(normalize_face(gray, IMG_SIZE, equalization))
            genuine.append((float(dist), id_to_name.get(pred_id) == person))

        n_imp = len(impostor_rois)
        print(f"[TARFAR] {family}/{recipe}: scoring {n_imp} impostors ...", flush=True)
        t0 = time.time()
        dists = []
        for i, roi in enumerate(impostor_rois, 1):
            dists.append(float(recognizer.predict(normalize_face(roi, IMG_SIZE, equalization))[1]))
            if i % 2000 == 0 or i == n_imp:
                rate = i / max(time.time() - t0, 1e-6)
                eta = (n_imp - i) / max(rate, 1e-6)
                print(f"  [score] {family}/{recipe} impostors {i}/{n_imp} "
                      f"| {rate:.0f}/s | eta {eta:.0f}s", flush=True)
        impostor_sorted = sorted(dists)
        imp_seconds = time.time() - t0

        ops = [operating_point(genuine, impostor_sorted, t) for t in target_fars]
        eer = equal_error_rate(genuine, impostor_sorted)
        rows.append({
            "family": family,
            "recipe": recipe,
            "model_file": str(model.relative_to(PROJECT_ROOT)),
            "gallery_images": recipe_train_images(recipe),
            "equalization": equalization,
            "n_genuine": len(genuine),
            "n_impostor": n_imp,
            "operating_points": ops,
            "eer": eer,
            "impostor_seconds": imp_seconds,
        })
        write_outputs()  # incremental: a crash keeps every finished row
        for op in ops:
            print(f"  FAR~{op['target_far_percent']:.3f}% -> thr={op['threshold_predict_scale']:.2f} "
                  f"actualFAR={op['actual_far_percent']:.4f}% TAR={op['tar_percent']:.2f}%", flush=True)

    print(f"\n[TARFAR] done. Wrote {TARFAR_JSON} and {TARFAR_MD}", flush=True)


# --------------------------------------------------------------------------- #
# Stage 4: assemble the numeric summary report
# --------------------------------------------------------------------------- #
def load_eval(family: str, recipe: str, testset: str) -> dict | None:
    p = eval_report_path(family, recipe, testset)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def fmt_pct(value) -> str:
    return f"{value:.2f}%" if isinstance(value, (int, float)) else "-"


def build_summary(families: list[str], recipes: list[str]) -> None:
    tarfar_rows: dict[tuple[str, str], dict] = {}
    if TARFAR_JSON.exists():
        for r in json.loads(TARFAR_JSON.read_text(encoding="utf-8")).get("rows", []):
            tarfar_rows[(r["family"], r["recipe"])] = r

    lines = [
        "# Dataset-composition matrix - classical recognizers",
        "",
        "All models trained from the same DB (leakage-free La Salle split); evaluated on the",
        "held-out test probes (56 = 1 light + 1 dark per identity) and LFW impostors.",
        "",
    ]

    # ---- intra-model: one table per family, rows = recipes -------------------
    lines.append("## Intra-model: effect of training recipe (per family)")
    for family in families:
        lines += ["", f"### {family}", "",
                  "| Recipe | Train imgs | Model MB | Rank-1 full | Rank-1 light | Rank-1 dark | "
                  "Hit@deployed | Best sweep | TAR@100ppm | EER |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for recipe in recipes:
            full = load_eval(family, recipe, "full")
            light = load_eval(family, recipe, "light")
            dark = load_eval(family, recipe, "dark")
            tf = tarfar_rows.get((family, recipe))
            model, _ = model_paths(family, recipe)
            size_mb = model.stat().st_size / 1e6 if model.exists() else None

            def rank1(ev):
                return fmt_pct((ev or {}).get("rank1", {}).get("accuracy_percent"))

            hit = fmt_pct((full or {}).get("overall", {}).get("hit_rate_percent"))
            thr = (full or {}).get("config", {}).get("unknown_threshold")
            sweep = (full or {}).get("best_sweep", {})
            sweep_txt = (f"{sweep.get('overall_accuracy_percent', 0):.2f}% @ {sweep.get('threshold', 0):g}"
                         if sweep else "-")
            tar100 = "-"
            eer_txt = "-"
            if tf:
                ops = {op["target_far_percent"]: op for op in tf["operating_points"]}
                tar100 = fmt_pct(ops.get(0.01, {}).get("tar_percent"))
                eer_txt = fmt_pct((tf.get("eer") or {}).get("eer_percent"))
            lines.append(
                f"| {recipe} | {recipe_train_images(recipe)} | "
                f"{(f'{size_mb:.1f}' if size_mb is not None else '-')} | "
                f"{rank1(full)} | {rank1(light)} | {rank1(dark)} | "
                f"{hit}{f' @ {thr:g}' if isinstance(thr, (int, float)) else ''} | "
                f"{sweep_txt} | {tar100} | {eer_txt} |"
            )

    # ---- inter-model: one table per recipe, rows = families ------------------
    lines += ["", "## Inter-model: families compared at fixed recipe"]
    for recipe in recipes:
        lines += ["", f"### {recipe} ({RECIPES[recipe]['desc']})", "",
                  "| Family | Rank-1 full | Rank-1 light | Rank-1 dark | TAR@1.058% | TAR@100ppm | EER |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for family in families:
            full = load_eval(family, recipe, "full")
            light = load_eval(family, recipe, "light")
            dark = load_eval(family, recipe, "dark")
            tf = tarfar_rows.get((family, recipe))
            tar_ind = tar100 = eer_txt = "-"
            if tf:
                ops = {op["target_far_percent"]: op for op in tf["operating_points"]}
                tar_ind = fmt_pct(ops.get(1.058, {}).get("tar_percent"))
                tar100 = fmt_pct(ops.get(0.01, {}).get("tar_percent"))
                eer_txt = fmt_pct((tf.get("eer") or {}).get("eer_percent"))

            def rank1(ev):
                return fmt_pct((ev or {}).get("rank1", {}).get("accuracy_percent"))

            lines.append(f"| {family} | {rank1(full)} | {rank1(light)} | {rank1(dark)} | "
                         f"{tar_ind} | {tar100} | {eer_txt} |")

    lines.append("")
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[SUMMARY] wrote {SUMMARY_MD}", flush=True)


def main() -> None:
    args = parse_args()
    py = sys.executable
    families = [f.strip().lower() for f in args.families.split(",") if f.strip()]
    recipes = [r.strip().lower() for r in args.recipes.split(",") if r.strip()]
    bad = [f for f in families if f not in FAMILIES] + [r for r in recipes if r not in RECIPES]
    if bad:
        raise SystemExit(f"Unknown families/recipes: {bad}")

    build_subsets()

    if not args.skip_train:
        for family in families:
            for recipe in recipes:
                train(py, family, recipe, args.force_train)

    if not args.skip_eval:
        for family in families:
            for recipe in recipes:
                for testset in TESTSETS:
                    evaluate(py, family, recipe, testset)

    if not args.skip_tar_far:
        run_tar_far(args, families, recipes)

    build_summary(families, recipes)
    print("\n[DONE] Dataset matrix complete.", flush=True)


if __name__ == "__main__":
    main()
