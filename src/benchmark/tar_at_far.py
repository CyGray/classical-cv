"""End-to-end TAR @ FAR / FRR for the classical recognizers.

The independence test fixes a target false-alarm rate but on its own
feature-distance scale. This tool measures the operating point on each
recognizer's NATIVE ``predict()`` scale by running an impostor-inclusive
recognition pass:

* **Genuine** probes = the held-out La Salle test split (enrolled identities,
  pre-cropped tiles -> ``assume_cropped``).
* **Impostor** probes = LFW identities (none enrolled), Haar-detected and cropped
  so their framing matches the genuine tiles. Defaults to the FULL LFW set
  (13,233 images): with ~12k usable impostors the FAR axis resolves down to the
  spec's 0.01% (100 ppm) instead of the ~0.17% floor a 605-probe sample had.

For each probe we take the recognizer distance to its nearest gallery identity.
A probe is *accepted* when that distance <= threshold T. Then:

    FAR(T) = accepted impostors / impostors
    TAR(T) = correctly-accepted genuine / genuine     (right identity AND accepted)
    FRR(T) = 100 - TAR(T)

Impostor faces are cropped ONCE and shared across the three families (the crop
does not depend on the recognizer); per-family equalization comes from the
family ``RecognizerSpec`` so this stays in lock-step with training. We sweep T
at full resolution, report the deployable threshold at each target FAR (incl.
the independence operating point ~1.058% for La Salle DB1 and the spec's 0.1% /
0.01%), and the EER, and write ``reports/benchmark/tar_at_far.{json,md}``.
"""

import argparse
import json
import math
import os
import time
from pathlib import Path

import cv2 as cv
import numpy as np

from src.classical_faces.datasets import list_image_files
from src.classical_faces.pipeline import SPECS, load_label_map, load_recognizer
from src.classical_faces.preprocess import (
    IMG_SIZE,
    detect_largest_face_box,
    normalize_face,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FAMILIES = ["lbph", "eigenfaces", "fisherfaces"]


def root_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure TAR@FAR / FRR on the recognizer's native scale.")
    parser.add_argument("--families", default=",".join(FAMILIES))
    parser.add_argument("--genuine-dir", default="data/split_lasalle/test")
    parser.add_argument("--impostor-dir", default="data/lfw-dataset",
                        help="LFW root (identity sub-folders). Default = full LFW for 100 ppm resolution.")
    parser.add_argument("--impostor-max-identities", type=int, default=0,
                        help="Cap impostor identities (0 = all). Use e.g. 400 for a quick pass.")
    parser.add_argument("--impostor-max-per-id", type=int, default=0,
                        help="Cap images per impostor identity (0 = all).")
    parser.add_argument("--min-face-size", type=int, default=40)
    parser.add_argument("--target-far-percent", default="1.058,1.0,0.1,0.01",
                        help="Comma-separated target FARs (%%). 1.058 = La Salle independence operating "
                             "point; 0.01 = the spec's 100 ppm.")
    parser.add_argument("--equalization", default="",
                        help="Override contrast normalization for ALL families "
                             "(default: each family's RecognizerSpec default).")
    parser.add_argument("--cascade-path", default=root_path("haar", "haarcascade_frontalface_default.xml"))
    parser.add_argument("--output-json", default="reports/benchmark/tar_at_far.json")
    parser.add_argument("--output-md", default="reports/benchmark/tar_at_far.md")
    return parser.parse_args()


def _abs(path_value: str) -> str:
    p = Path(path_value)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


def load_genuine_grays(base_dir: str) -> list[tuple[str, np.ndarray]]:
    """(person, grayscale tile) for the pre-cropped held-out genuine probes."""
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Missing data dir: {base_dir}")
    out: list[tuple[str, np.ndarray]] = []
    for person in sorted(os.listdir(base_dir)):
        pdir = os.path.join(base_dir, person)
        if not os.path.isdir(pdir):
            continue
        for fn in list_image_files(pdir):
            img = cv.imread(os.path.join(pdir, fn))
            if img is None:
                continue
            out.append((person, cv.cvtColor(img, cv.COLOR_BGR2GRAY)))
    return out


def load_impostor_rois(
    base_dir: str,
    *,
    face_cascade: cv.CascadeClassifier,
    known_names: set,
    min_face_size: int,
    max_ids: int,
    max_per_id: int,
) -> tuple[list[np.ndarray], int]:
    """Haar-detect impostor faces ONCE (shared across families). Returns (rois, skipped)."""
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Missing data dir: {base_dir}")
    persons = [p for p in sorted(os.listdir(base_dir))
               if os.path.isdir(os.path.join(base_dir, p)) and p not in known_names]
    if max_ids > 0:
        persons = persons[:max_ids]

    rois: list[np.ndarray] = []
    skipped = 0
    start = time.time()
    total_persons = len(persons)
    for i, person in enumerate(persons, 1):
        pdir = os.path.join(base_dir, person)
        files = list_image_files(pdir)
        if max_per_id > 0:
            files = files[:max_per_id]
        for fn in files:
            img = cv.imread(os.path.join(pdir, fn))
            if img is None:
                skipped += 1
                continue
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            box = detect_largest_face_box(
                image_gray=gray, face_cascade=face_cascade,
                min_face_size=min_face_size, scale_factor=1.1, min_neighbors=5,
            )
            if box is None:
                skipped += 1
                continue
            x, y, w, h = box
            rois.append(gray[y: y + h, x: x + w])
        if i % 500 == 0 or i == total_persons:
            rate = i / max(time.time() - start, 1e-6)
            print(f"  [crop] {i}/{total_persons} identities | {len(rois)} faces | "
                  f"{rate:.1f} ids/s", flush=True)
    return rois, skipped


def far_at(impostor_dists_sorted: list[float], threshold: float, n_imp: int) -> float:
    if n_imp == 0:
        return 0.0
    # impostor accepted when dist <= threshold; list is sorted ascending
    import bisect
    return 100.0 * bisect.bisect_right(impostor_dists_sorted, threshold) / n_imp


def tar_at(genuine: list, threshold: float) -> float:
    n = len(genuine)
    if n == 0:
        return 0.0
    correct = sum(1 for d, ok in genuine if ok and d <= threshold)
    return 100.0 * correct / n


def operating_point(genuine: list, impostor_sorted: list[float], target_far_pct: float) -> dict:
    n_imp = len(impostor_sorted)
    # Largest threshold whose FAR <= target: allow k false accepts, T = k-th smallest impostor distance.
    k = int(math.floor(target_far_pct / 100.0 * n_imp))
    if k < 1:
        # target finer than the impostor sample can resolve; strictest useful T is just below min impostor
        threshold = (impostor_sorted[0] - 1e-9) if n_imp else 0.0
        resolvable = False
    else:
        threshold = impostor_sorted[k - 1]
        resolvable = True
    far = far_at(impostor_sorted, threshold, n_imp)
    tar = tar_at(genuine, threshold)
    return {
        "target_far_percent": target_far_pct,
        "threshold_predict_scale": float(threshold),
        "actual_far_percent": far,
        "tar_percent": tar,
        "frr_percent": 100.0 - tar,
        "resolvable": resolvable,
    }


def equal_error_rate(genuine: list, impostor_sorted: list[float]) -> dict:
    # Candidate thresholds = genuine + impostor distances; find where FAR ~= FRR.
    n_imp = len(impostor_sorted)
    cands = sorted({d for d, _ in genuine} | set(impostor_sorted))
    best = None
    for t in cands:
        far = far_at(impostor_sorted, t, n_imp)
        frr = 100.0 - tar_at(genuine, t)
        gap = abs(far - frr)
        if best is None or gap < best["gap"]:
            best = {"gap": gap, "threshold_predict_scale": float(t),
                    "eer_far_percent": far, "eer_frr_percent": frr}
    if best:
        best["eer_percent"] = 0.5 * (best["eer_far_percent"] + best["eer_frr_percent"])
        best.pop("gap", None)
    return best or {}


def _far_cell(value_percent: float) -> str:
    ppm = value_percent * 1e4
    if value_percent < 0.1:
        return f"{value_percent:.4f}% ({ppm:.0f} ppm)"
    return f"{value_percent:.3f}%"


def to_markdown(rows: list[dict], cfg: dict) -> str:
    lines = ["# Classical Recognizers - TAR @ FAR / FRR (recognizer native scale)", ""]
    lines.append(f"Genuine: `{cfg['genuine_dir']}` (held-out La Salle) | "
                 f"Impostors: `{cfg['impostor_dir']}` (LFW, Haar-cropped).")
    lines.append("")
    lines.append("Threshold is the recognizer's `--unknown-threshold` (predict-distance scale): "
                 "accept when distance <= threshold. Lower threshold = stricter.")
    lines.append("")
    lines.append("| Model | Genuine | Impostors | Operating FAR (target) | Threshold | Actual FAR | TAR | FRR |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        for op in r["operating_points"]:
            tgt = _far_cell(op["target_far_percent"]) + ("" if op["resolvable"] else "*")
            lines.append(
                f"| {r['family']} | {r['n_genuine']} | {r['n_impostor']} | {tgt} | "
                f"{op['threshold_predict_scale']:.2f} | {_far_cell(op['actual_far_percent'])} | "
                f"{op['tar_percent']:.2f}% | {op['frr_percent']:.2f}% |"
            )
    lines += ["", "## Equal Error Rate (EER)", "",
              "| Model | EER | Threshold | FAR@EER | FRR@EER |", "|---|---:|---:|---:|---:|"]
    for r in rows:
        e = r.get("eer") or {}
        if e:
            lines.append(f"| {r['family']} | {e['eer_percent']:.2f}% | {e['threshold_predict_scale']:.2f} | "
                         f"{e['eer_far_percent']:.2f}% | {e['eer_frr_percent']:.2f}% |")
    lines += [
        "",
        "## Notes",
        "",
        "- **TAR** = genuine probes accepted *as the correct identity*; **FRR = 100 - TAR** "
        "(a genuine probe that is rejected OR misidentified is a false rejection).",
        "- **FAR** = impostor (LFW) probes accepted as any enrolled identity.",
        "- `*` on a target FAR means the impostor sample is too small to resolve it; the row uses "
        "the strictest resolvable threshold (actual FAR shown).",
        "- The **1.058%** target is the La Salle DB1 independence operating point (8th error pair); "
        "**0.01% (100 ppm)** is the project spec's FAR budget. "
        "The `Threshold` column is the deployable `--unknown-threshold` at that FAR.",
        "- Genuine is only the held-out La Salle test (56 probes), so TAR has ~2% granularity; "
        "the 41-modification Accuracy-Ratio benchmark (`src/benchmark/accuracy_ratio.py`) is the "
        "higher-resolution genuine-side follow-up.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    families = [f.strip().lower() for f in args.families.split(",") if f.strip()]
    target_fars = [float(x) for x in args.target_far_percent.split(",") if x.strip()]
    cascade_path = _abs(args.cascade_path)
    face_cascade = cv.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        raise FileNotFoundError(f"Could not load cascade: {cascade_path}")

    genuine_dir = _abs(args.genuine_dir)
    impostor_dir = _abs(args.impostor_dir)

    # The enrolled identity names are the same across the three clean models;
    # use the first available labels file for the impostor-identity filter.
    known_names: set = set()
    for family in families:
        labels = _abs(f"models/{family}/labels_lasalle_clean.json")
        if os.path.exists(labels):
            _, _, known_names = load_label_map(labels)
            break

    print(f"[INFO] Loading genuine tiles ({genuine_dir}) ...")
    genuine_grays = load_genuine_grays(genuine_dir)
    print(f"[INFO] genuine={len(genuine_grays)}")
    print(f"[INFO] Haar-cropping impostors once ({impostor_dir}) ...")
    impostor_rois, imp_skipped = load_impostor_rois(
        impostor_dir,
        face_cascade=face_cascade,
        known_names=known_names,
        min_face_size=args.min_face_size,
        max_ids=args.impostor_max_identities,
        max_per_id=args.impostor_max_per_id,
    )
    print(f"[INFO] impostors={len(impostor_rois)} (skipped {imp_skipped})")

    rows: list[dict] = []
    for family in families:
        spec = SPECS[family]
        model = _abs(f"models/{family}/lasalle_clean.yml")
        labels = _abs(f"models/{family}/labels_lasalle_clean.json")
        if not (os.path.exists(model) and os.path.exists(labels)):
            print(f"[WARN] {family}: missing clean model/labels, skipping. Run the clean loop first.")
            continue
        _, id_to_name, family_known = load_label_map(labels)
        recognizer = load_recognizer(spec, model)
        equalization = args.equalization or spec.default_equalization

        print(f"[INFO] {family}: scoring genuine (eq={equalization}) ...")
        genuine: list[tuple[float, bool]] = []
        for person, gray in genuine_grays:
            pred_id, dist = recognizer.predict(normalize_face(gray, IMG_SIZE, equalization))
            genuine.append((float(dist), id_to_name.get(pred_id) == person))

        print(f"[INFO] {family}: scoring {len(impostor_rois)} impostors ...")
        t0 = time.time()
        impostor_sorted = sorted(
            float(recognizer.predict(normalize_face(roi, IMG_SIZE, equalization))[1])
            for roi in impostor_rois
        )
        print(f"[INFO] {family}: impostor scoring took {time.time() - t0:.1f}s")

        ops = [operating_point(genuine, impostor_sorted, t) for t in target_fars]
        eer = equal_error_rate(genuine, impostor_sorted)
        rows.append({
            "family": family,
            "equalization": equalization,
            "n_genuine": len(genuine),
            "n_impostor": len(impostor_sorted),
            "impostor_skipped": imp_skipped,
            "operating_points": ops,
            "eer": eer,
        })
        for op in ops:
            print(f"  FAR~{op['target_far_percent']:.3f}% -> thr={op['threshold_predict_scale']:.2f} "
                  f"actualFAR={op['actual_far_percent']:.4f}% TAR={op['tar_percent']:.2f}% "
                  f"FRR={op['frr_percent']:.2f}%")

    if not rows:
        raise RuntimeError("No models scored. Train the clean models first (run_classical_clean_loop.py).")

    cfg = {"genuine_dir": args.genuine_dir, "impostor_dir": args.impostor_dir}
    out_json = _abs(args.output_json)
    out_md = _abs(args.output_md)
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "target_far_percent": target_fars, "rows": rows}, f, indent=2)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(to_markdown(rows, cfg))
    print(f"\n[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")


if __name__ == "__main__":
    main()
