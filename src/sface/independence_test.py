"""Parity check: reproduce the DL track's SFace LFW independence number.

The DL repo's ``dnn.py`` ran the N x (N-1) impostor sweep over 5,685 LFW
identities and reported the headline **FP = 0.07% at TP 100%**
(``results-lfw.json``: n_fp=24,128 / 32,313,540 comparisons). If this CV-repo
wrapper does not match that number on the same embeddings, the port is wrong.

The genuine rule is ``cosine >= 0.363`` AND ``l2 <= 1.128``. For SFace's
normalised features ``l2 = sqrt(2 - 2*cosine)``, so the two clauses are
equivalent by construction; this script verifies that equivalence against
``cv.FaceRecognizerSF.match`` on a sample of pairs, then counts the full sweep
vectorised (32M Python ``match`` calls would otherwise take hours).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from src.sface.recognizer import (
    COSINE_GENUINE_THRESHOLD,
    L2_GENUINE_THRESHOLD,
    SFaceRecognizer,
    _load_feature_matrix,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DL_REFERENCE_FP_PERCENT = 0.07  # face-detection-g3-dl/results-lfw.json
DEFAULT_IMPOSTORS = str(PROJECT_ROOT / "models" / "sface" / "impostors-lfw.npy")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SFace LFW independence parity check.")
    p.add_argument("--impostors-npy", default=DEFAULT_IMPOSTORS)
    p.add_argument(
        "--tolerance-abs",
        type=float,
        default=0.05,
        help="Max absolute FP%% difference vs the DL reference to count as parity.",
    )
    p.add_argument(
        "--report-json",
        default=str(PROJECT_ROOT / "reports" / "independence" / "sface_lfw_parity.json"),
    )
    return p.parse_args()


def _verify_l2_equivalence(feats: np.ndarray, n: int = 200) -> float:
    """Confirm the matrix ``l2 = sqrt(2-2cos)`` matches ``cv.match`` (max abs err)."""
    rec = SFaceRecognizer()
    rng = np.random.default_rng(0)
    max_err = 0.0
    for _ in range(n):
        i, j = rng.integers(0, feats.shape[0], size=2)
        a = feats[i].reshape(1, -1).astype(np.float32)
        b = feats[j].reshape(1, -1).astype(np.float32)
        cos, l2 = rec.match(a, b)
        l2_pred = float(np.sqrt(max(0.0, 2.0 - 2.0 * cos)))
        max_err = max(max_err, abs(l2 - l2_pred))
    return max_err


def main() -> int:
    args = parse_args()
    if not Path(args.impostors_npy).exists():
        raise FileNotFoundError(
            f"Impostor embeddings not found: {args.impostors_npy}. Vendor the DL "
            "features-lfw.npy into models/sface/impostors-lfw.npy (Phase 2.3)."
        )

    feats = _load_feature_matrix(args.impostors_npy).astype(np.float32)
    n = feats.shape[0]
    print(f"[INFO] Loaded {n} LFW identities ({feats.shape[1]}-D embeddings).")

    l2_err = _verify_l2_equivalence(feats)
    print(f"[CHECK] vectorised L2 vs cv.match max abs error: {l2_err:.2e}")

    norm = feats / (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-9)
    sim = (norm @ norm.T).astype(np.float32)
    l2 = np.sqrt(np.clip(2.0 - 2.0 * sim, 0.0, None))

    genuine = (sim >= COSINE_GENUINE_THRESHOLD) & (l2 <= L2_GENUINE_THRESHOLD)
    np.fill_diagonal(genuine, False)  # i == j is the same identity, not an impostor

    n_comparisons = n * (n - 1)  # ordered pairs, matching dnn.py
    n_fp = int(genuine.sum())  # genuine is symmetric => already counts both orders
    fp_percent = 100.0 * n_fp / n_comparisons if n_comparisons else 0.0

    diff = abs(fp_percent - DL_REFERENCE_FP_PERCENT)
    passed = diff <= args.tolerance_abs

    print("\n" + "=" * 48)
    print(f"[SFACE] LFW independence (CV-repo wrapper)")
    print(f"  identities      : {n}")
    print(f"  comparisons     : {n_comparisons:,}")
    print(f"  false positives : {n_fp:,}")
    print(f"  FP%             : {fp_percent:.4f}%")
    print(f"  DL reference FP%: {DL_REFERENCE_FP_PERCENT:.2f}%  (results-lfw.json)")
    print(f"  parity          : {'PASS' if passed else 'FAIL'} (|diff|={diff:.4f} <= {args.tolerance_abs})")
    print("=" * 48)

    report = {
        "db": "LFW",
        "source": "cv-repo src/sface wrapper",
        "identities": n,
        "comparisons": n_comparisons,
        "false_positives": n_fp,
        "fp_percent": round(fp_percent, 4),
        "dl_reference_fp_percent": DL_REFERENCE_FP_PERCENT,
        "abs_diff": round(diff, 4),
        "tolerance_abs": args.tolerance_abs,
        "parity_pass": passed,
        "l2_vs_match_max_abs_err": l2_err,
        "cosine_genuine_threshold": COSINE_GENUINE_THRESHOLD,
        "l2_genuine_threshold": L2_GENUINE_THRESHOLD,
    }
    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[INFO] Report: {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
