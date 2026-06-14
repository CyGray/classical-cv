"""DB2-style Accuracy Ratio (AR = K / M) for the classical recognizers.

Implements the project-spec recognition measurement (BRIEFING.md S9): every
original image gets a *modified* version per (modification, level); the
recognizer must still match the modified probe to its identity at the
FAR-controlled operating threshold. Then::

    AR(modification, level) = K / M
        M = modified probes for that (modification, level)
        K = probes accepted as the CORRECT identity (distance <= threshold)

    AR(modification) = mean over its levels
    overall AR       = mean over modifications

The threshold is the deployable ``--unknown-threshold`` at the independence
false-alarm rate, read from ``reports/benchmark/tar_at_far.json`` (run
``src/benchmark/tar_at_far.py`` first) - i.e. "AR at a pre-determined
false-positive rate set by the independence threshold", exactly as specced.

The modification suite is **41 deterministic (modification, level) variants**
across 12 modification types (brightness up/down, contrast up/down, gamma
up/down, gaussian noise, gaussian blur, motion blur, rotation, zoom,
occlusion), generated in-memory from the original tiles - no augmented folder
is needed and the suite is reproducible (seeded per image+mod+level).
NOTE: the official 41-modification list from the team spec sheet should be
confirmed; this suite is the documented stand-in (the counts match: 41
variants/original, La Salle DB2 = 280 x 41 = 11,480 when --include-train).

Originals default to the held-out ``data/split_lasalle/test`` (56 originals ->
2,296 modified probes/family) so the number stays leakage-free for the
identification gallery. ``--include-train`` adds the 280 train originals to
reproduce the literal DB2 scheme - flagged in the report, since the gallery
has seen those unmodified originals (optimistic for identification).

Writes ``reports/benchmark/accuracy_ratio.{json,md}``.
"""

import argparse
import json
import math
import os
import zlib
from pathlib import Path

import cv2 as cv
import numpy as np

from src.classical_faces.datasets import list_image_files
from src.classical_faces.pipeline import SPECS, load_label_map, load_recognizer
from src.classical_faces.preprocess import IMG_SIZE, normalize_face

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FAMILIES = ["lbph", "eigenfaces", "fisherfaces"]


# --------------------------------------------------------------------------- #
# Deterministic modification suite (12 types, 41 (type, level) variants)
# --------------------------------------------------------------------------- #
def _u8(image: np.ndarray) -> np.ndarray:
    return np.clip(image, 0, 255).astype(np.uint8)


def _brightness(img: np.ndarray, offset: float, _rng) -> np.ndarray:
    return _u8(img.astype(np.float32) + offset)


def _contrast(img: np.ndarray, factor: float, _rng) -> np.ndarray:
    return _u8((img.astype(np.float32) - 128.0) * factor + 128.0)


def _gamma(img: np.ndarray, gamma: float, _rng) -> np.ndarray:
    table = _u8(((np.arange(256, dtype=np.float32) / 255.0) ** (1.0 / max(gamma, 1e-6))) * 255.0)
    return cv.LUT(img, table)


def _gaussian_noise(img: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    return _u8(img.astype(np.float32) + rng.normal(0.0, sigma, img.shape).astype(np.float32))


def _gaussian_blur(img: np.ndarray, ksize: int, _rng) -> np.ndarray:
    k = int(ksize) | 1
    return cv.GaussianBlur(img, (k, k), 0)


def _motion_blur(img: np.ndarray, ksize: int, _rng) -> np.ndarray:
    k = max(3, int(ksize) | 1)
    kernel = np.zeros((k, k), dtype=np.float32)
    kernel[k // 2, :] = 1.0 / float(k)
    return cv.filter2D(img, -1, kernel)


def _rotation(img: np.ndarray, angle_deg: float, _rng) -> np.ndarray:
    h, w = img.shape[:2]
    matrix = cv.getRotationMatrix2D(((w - 1) / 2.0, (h - 1) / 2.0), angle_deg, 1.0)
    return cv.warpAffine(img, matrix, (w, h), flags=cv.INTER_LINEAR,
                         borderMode=cv.BORDER_REFLECT_101)


def _zoom(img: np.ndarray, zoom: float, _rng) -> np.ndarray:
    h, w = img.shape[:2]
    matrix = cv.getRotationMatrix2D(((w - 1) / 2.0, (h - 1) / 2.0), 0.0, zoom)
    return cv.warpAffine(img, matrix, (w, h), flags=cv.INTER_LINEAR,
                         borderMode=cv.BORDER_REFLECT_101)


def _occlusion(img: np.ndarray, area_fraction: float, rng: np.random.Generator) -> np.ndarray:
    h, w = img.shape[:2]
    target = max(1.0, area_fraction * h * w)
    rect_h = int(max(4, round(math.sqrt(target))))
    rect_w = int(max(4, round(target / rect_h)))
    rect_h, rect_w = min(rect_h, h), min(rect_w, w)
    y0 = int(rng.integers(0, max(1, h - rect_h + 1)))
    x0 = int(rng.integers(0, max(1, w - rect_w + 1)))
    out = img.copy()
    patch = out[y0: y0 + rect_h, x0: x0 + rect_w]
    fill = int(np.median(patch)) if patch.size else 128
    out[y0: y0 + rect_h, x0: x0 + rect_w] = _u8(
        0.55 * patch.astype(np.float32) + 0.45 * fill
    )
    return out


# (modification name, transform, [levels]) -> 4+4+3+3+3+3+4+3+3+4+4+3 = 41 variants
MODIFICATIONS: list[tuple[str, object, list[float]]] = [
    ("brightness_up", _brightness, [15, 30, 45, 60]),
    ("brightness_down", _brightness, [-15, -30, -45, -60]),
    ("contrast_up", _contrast, [1.15, 1.30, 1.45]),
    ("contrast_down", _contrast, [0.85, 0.70, 0.55]),
    ("gamma_up", _gamma, [1.2, 1.4, 1.6]),
    ("gamma_down", _gamma, [0.8, 0.65, 0.5]),
    ("gaussian_noise", _gaussian_noise, [5, 10, 15, 20]),
    ("gaussian_blur", _gaussian_blur, [3, 5, 7]),
    ("motion_blur", _motion_blur, [3, 5, 7]),
    ("rotation", _rotation, [-10, -5, 5, 10]),
    ("zoom", _zoom, [0.90, 0.95, 1.05, 1.10]),
    ("occlusion", _occlusion, [0.075, 0.125, 0.175]),
]

VARIANT_COUNT = sum(len(levels) for _, _, levels in MODIFICATIONS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Accuracy Ratio (AR = K/M) over the 41-modification suite."
    )
    parser.add_argument("--families", default=",".join(FAMILIES))
    parser.add_argument("--originals-dir", default="data/split_lasalle/test",
                        help="Identity folders of ORIGINAL images (default: held-out test).")
    parser.add_argument("--include-train", action="store_true",
                        help="Also use data/split_lasalle/train originals (literal DB2 scheme, "
                             "280x41; optimistic for identification - gallery saw the originals).")
    parser.add_argument("--train-dir", default="data/split_lasalle/train")
    parser.add_argument("--tar-at-far-json", default="reports/benchmark/tar_at_far.json",
                        help="Source of the deployable threshold per family.")
    parser.add_argument("--at-far-percent", type=float, default=1.058,
                        help="Which TAR@FAR operating point's threshold to use (target FAR %%).")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Explicit threshold override (applies to ALL selected families).")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save-samples-dir", default="",
                        help="Optional: dump one modified example per (mod, level) here.")
    parser.add_argument("--output-json", default="reports/benchmark/accuracy_ratio.json")
    parser.add_argument("--output-md", default="reports/benchmark/accuracy_ratio.md")
    return parser.parse_args()


def _abs(path_value: str) -> str:
    p = Path(path_value)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


def load_originals(base_dir: str, bucket: str) -> list[tuple[str, str, np.ndarray, str]]:
    """(person, filename, gray, bucket) for every original tile."""
    out = []
    for person in sorted(os.listdir(base_dir)):
        pdir = os.path.join(base_dir, person)
        if not os.path.isdir(pdir):
            continue
        for fn in list_image_files(pdir):
            img = cv.imread(os.path.join(pdir, fn))
            if img is None:
                continue
            out.append((person, fn, cv.cvtColor(img, cv.COLOR_BGR2GRAY), bucket))
    return out


def deployed_threshold(tar_far_payload: dict, family: str, at_far_percent: float) -> float | None:
    for row in tar_far_payload.get("rows", []):
        if str(row.get("family", "")).lower() != family:
            continue
        ops = row.get("operating_points", [])
        if not ops:
            return None
        op = min(ops, key=lambda o: abs(float(o.get("target_far_percent", 0)) - at_far_percent))
        return float(op.get("threshold_predict_scale", 0.0))
    return None


def stable_rng(seed: int, *tokens: object) -> np.random.Generator:
    token = "/".join(str(t) for t in tokens)
    return np.random.default_rng(seed + zlib.crc32(token.encode("utf-8")))


def main() -> None:
    args = parse_args()
    families = [f.strip().lower() for f in args.families.split(",") if f.strip()]

    originals = load_originals(_abs(args.originals_dir), "test")
    if args.include_train:
        originals += load_originals(_abs(args.train_dir), "train")
    if not originals:
        raise RuntimeError(f"No original images found under {args.originals_dir}")
    print(f"[INFO] originals={len(originals)} -> modified probes per family = "
          f"{len(originals)} x {VARIANT_COUNT} = {len(originals) * VARIANT_COUNT}")

    tar_far_payload = {}
    tar_far_path = Path(_abs(args.tar_at_far_json))
    if tar_far_path.exists():
        tar_far_payload = json.loads(tar_far_path.read_text(encoding="utf-8"))

    samples_dir = _abs(args.save_samples_dir) if args.save_samples_dir else ""
    if samples_dir:
        Path(samples_dir).mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for family in families:
        spec = SPECS[family]
        model = _abs(f"models/{family}/lasalle_clean.yml")
        labels = _abs(f"models/{family}/labels_lasalle_clean.json")
        if not (os.path.exists(model) and os.path.exists(labels)):
            print(f"[WARN] {family}: missing clean model/labels, skipping.")
            continue
        threshold = args.threshold
        if threshold is None:
            threshold = deployed_threshold(tar_far_payload, family, args.at_far_percent)
        if threshold is None:
            print(f"[WARN] {family}: no threshold available (run tar_at_far.py first); skipping.")
            continue

        _, id_to_name, _ = load_label_map(labels)
        recognizer = load_recognizer(spec, model)
        equalization = spec.default_equalization

        def predict_match(gray: np.ndarray, person: str) -> bool:
            pred_id, dist = recognizer.predict(normalize_face(gray, IMG_SIZE, equalization))
            return id_to_name.get(pred_id) == person and float(dist) <= threshold

        # Clean (unmodified) acceptance at the same threshold, for reference.
        clean_matches = sum(predict_match(gray, person) for person, _, gray, _ in originals)

        print(f"[INFO] {family}: threshold={threshold:.2f} (predict scale, FAR~{args.at_far_percent}%), "
              f"eq={equalization}")
        per_mod: list[dict] = []
        for mod_name, fn, levels in MODIFICATIONS:
            level_rows = []
            for level in levels:
                matched = 0
                for person, fname, gray, _bucket in originals:
                    rng = stable_rng(args.seed, person, fname, mod_name, level)
                    modified = fn(gray, level, rng)
                    if samples_dir and (person, fname) == (originals[0][0], originals[0][1]):
                        cv.imwrite(os.path.join(
                            samples_dir, f"{mod_name}_{level}.png"), modified)
                    matched += predict_match(modified, person)
                level_rows.append({
                    "level": level,
                    "modified_total": len(originals),
                    "matched": matched,
                    "ar_percent": 100.0 * matched / len(originals),
                })
            mod_ar = sum(r["ar_percent"] for r in level_rows) / len(level_rows)
            per_mod.append({"modification": mod_name, "ar_percent": mod_ar, "levels": level_rows})
            level_summary = ", ".join(
                "{}:{:.1f}%".format(r["level"], r["ar_percent"]) for r in level_rows
            )
            print(f"  {mod_name:<16} AR={mod_ar:6.2f}%  ({level_summary})")

        overall = sum(m["ar_percent"] for m in per_mod) / len(per_mod)
        results.append({
            "family": family,
            "threshold_predict_scale": float(threshold),
            "at_far_percent": args.at_far_percent,
            "equalization": equalization,
            "originals": len(originals),
            "include_train_originals": bool(args.include_train),
            "variants_per_original": VARIANT_COUNT,
            "modified_probes": len(originals) * VARIANT_COUNT,
            "clean_acceptance_percent": 100.0 * clean_matches / len(originals),
            "overall_ar_percent": overall,
            "modifications": per_mod,
        })
        print(f"[RESULT] {family}: overall AR = {overall:.2f}% "
              f"(clean acceptance {100.0 * clean_matches / len(originals):.2f}%)")

    if not results:
        raise RuntimeError("No families scored. Train clean models + run tar_at_far.py first.")

    out_json = _abs(args.output_json)
    out_md = _abs(args.output_md)
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "originals_dir": args.originals_dir,
        "include_train": bool(args.include_train),
        "variant_count": VARIANT_COUNT,
        "seed": args.seed,
        "rows": results,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(to_markdown(payload))
    print(f"\n[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")


def to_markdown(payload: dict) -> str:
    rows = payload["rows"]
    lines = [
        "# Accuracy Ratio (AR = K/M) - 41-modification suite",
        "",
        f"Originals: `{payload['originals_dir']}`"
        + (" + train originals (literal DB2 scheme)" if payload["include_train"] else
           " (held-out only, leakage-free)")
        + f" | {payload['variant_count']} deterministic (modification, level) variants per original.",
        "",
        "A modified probe **matches** when the recognizer predicts the correct identity AND the "
        "distance is within the deployable threshold (set at the independence FAR via "
        "`tar_at_far.py`). AR per modification = mean over its levels; overall = mean over "
        "modifications (spec S9 scheme).",
        "",
        "| Model | Threshold | Originals | Probes | Clean accept | Overall AR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['family']} | {r['threshold_predict_scale']:.2f} | {r['originals']} | "
            f"{r['modified_probes']} | {r['clean_acceptance_percent']:.2f}% | "
            f"**{r['overall_ar_percent']:.2f}%** |"
        )
    lines.append("")

    for r in rows:
        lines += [f"## {r['family']} - per modification", "",
                  "| Modification | AR % | Per level |", "|---|---:|---|"]
        for m in sorted(r["modifications"], key=lambda x: x["ar_percent"]):
            per_level = ", ".join(
                f"{lv['level']}: {lv['ar_percent']:.1f}%" for lv in m["levels"])
            lines.append(f"| {m['modification']} | {m['ar_percent']:.2f} | {per_level} |")
        lines.append("")

    lines += [
        "## Notes",
        "",
        "- The 12-type/41-variant suite is a documented stand-in for the official 41-modification "
        "list (confirm with the team spec sheet); counts match the DB2 scheme "
        "(280 x 41 = 11,480 with `--include-train`, held-out = 56 x 41 = 2,296).",
        "- Modifications are applied to the raw tile BEFORE contrast normalization, like a real "
        "capture corruption; noise/occlusion are seeded per (image, modification, level) so runs "
        "are reproducible.",
        "- `Clean accept` is the unmodified acceptance rate at the same threshold (the TAR@FAR "
        "baseline); per-modification AR below it quantifies robustness loss.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
