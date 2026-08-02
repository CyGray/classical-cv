#!/usr/bin/env python3
"""Genuine (same-identity, gallery-vs-probe) distance distribution for the
disjoint LFW identification split.

Companion to the impostor-side independence tests (`src/lbph/independence_test.py`
et al.): those measure how well the system rejects DIFFERENT people. This
measures the other half - given the FIXED gallery/probe-disjoint protocol
(`docs/audits/STATE-08-01.md`), what does the SAME person's genuine
cross-photo distance actually look like, and does it fall inside the accept
band the frozen thresholds define?

For every identity with a probe in the split manifest:

* **LBPH**: ``LBPHAdapter.score(sample).all_distances[person]`` - the raw
  distance from the probe to that identity's OWN enrolled template (not the
  best-across-gallery distance, which can differ when the argmin picks a
  different identity).
* **SFace**: cosine/L2 computed directly against ``gallery.embeddings[person]``
  (same formula ``SFaceGallery.score`` uses: ``l2 = sqrt(max(2 - 2*cos, 0))``
  on unit-normalized features) - not the "best match" L2, for the same reason.

Reuses `src/independence_plots.py::save_distance_histogram` for the actual
plotting (no new plotting code) - this is a genuine-distance sibling to the
impostor histograms that function already produces elsewhere in this repo.

Writes ``<output-dir>/lbph_genuine_distance_hist.png``,
``<output-dir>/sface_l2_genuine_distance_hist.png``, and
``<output-dir>/genuine_distance_summary.json`` (percentiles + raw arrays).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.accuracy_ratio_hybrid import load_split_manifest, to_bgr_gray, tile_sample  # noqa: E402
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.hybrid.recognizer import (  # noqa: E402
    DEFAULT_LBPH_LABELS,
    DEFAULT_LBPH_MODEL,
    DEFAULT_SFACE_GALLERY,
    DEFAULT_THRESHOLDS_PATH,
    LBPHAdapter,
    SFaceAdapter,
    detect_sample,
    load_thresholds,
)
from src.hybrid.gate import GateThresholds
from src.independence_plots import save_distance_histogram  # noqa: E402


def _abs(p: str) -> str:
    path = Path(p)
    return str(path if path.is_absolute() else PROJECT_ROOT / path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genuine (same-identity) LBPH distance / SFace L2 distribution "
                    "for the disjoint LFW split - do real cross-photo genuine "
                    "distances fall inside the frozen accept thresholds?"
    )
    parser.add_argument("--split-manifest", required=True,
                         help="lsface-lfw-ident-split-v1 manifest (probe images scored).")
    parser.add_argument("--lbph-model", default=DEFAULT_LBPH_MODEL)
    parser.add_argument("--lbph-labels", default=DEFAULT_LBPH_LABELS)
    parser.add_argument("--sface-gallery", default=DEFAULT_SFACE_GALLERY)
    parser.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--limit-identities", type=int, default=0,
                         help="Debug/smoke-test only: use at most this many probes (0 = all).")
    parser.add_argument("--output-dir", default="reports/benchmark/lfw2_robustness_disjoint/genuine_distance")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_split_manifest(_abs(args.split_manifest))
    root = manifest["dataset_root"]

    identities = sorted(manifest["identities"])
    if args.limit_identities:
        identities = identities[:args.limit_identities]

    cfg = load_thresholds(_abs(args.thresholds_json))
    gate_thresholds = GateThresholds.from_dict(cfg.get("gate"))
    tau_accept = gate_thresholds.tau_accept
    tau_reject = gate_thresholds.tau_reject
    l2_genuine = float(cfg.get("sface", {}).get("l2_genuine", 1.018))
    cosine_genuine = float(cfg.get("sface", {}).get("cosine_genuine", 0.363))

    lbph = LBPHAdapter(model_path=_abs(args.lbph_model), labels_path=_abs(args.lbph_labels))
    sface = SFaceAdapter(gallery_path=_abs(args.sface_gallery), impostors_path=None)
    detector = create_face_detector("yunet")

    lbph_genuine: list[float] = []
    sface_l2_genuine: list[float] = []
    sface_cosine_genuine: list[float] = []
    n_probes = 0
    n_no_face = 0
    n_missing_gallery_embedding = 0

    for person in identities:
        entry = manifest["identities"][person]
        rel = entry.get("probe")
        if not rel:
            continue
        n_probes += 1
        img = cv.imread(str(Path(root) / rel))
        if img is None:
            continue
        image_bgr, image_gray = to_bgr_gray(img)
        sample = detect_sample(detector, image_bgr=image_bgr, image_gray=image_gray, assume_cropped=True)
        no_face = sample is None
        if no_face:
            n_no_face += 1
            sample = tile_sample(image_bgr, image_gray)

        lbph_match = lbph.score(sample)
        d = lbph_match.all_distances.get(person)
        if d is not None:
            lbph_genuine.append(float(d))

        gallery_emb = sface.gallery.embeddings.get(person)
        if gallery_emb is None:
            n_missing_gallery_embedding += 1
        else:
            feature = sface.embed(sample)
            f = np.asarray(feature, dtype=np.float32).reshape(-1)
            g = np.asarray(gallery_emb, dtype=np.float32).reshape(-1)
            cos = float((g @ f) / (np.linalg.norm(g) * np.linalg.norm(f) + 1e-12))
            l2 = float(np.sqrt(max(2.0 - 2.0 * cos, 0.0)))
            sface_cosine_genuine.append(cos)
            sface_l2_genuine.append(l2)

    def percentiles(values: list[float]) -> dict:
        if not values:
            return {}
        arr = np.asarray(values, dtype=np.float64)
        return {
            "n": len(values),
            "min": float(arr.min()),
            "p01": float(np.percentile(arr, 1)),
            "p05": float(np.percentile(arr, 5)),
            "median": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "max": float(arr.max()),
            "mean": float(arr.mean()),
        }

    lbph_stats = percentiles(lbph_genuine)
    sface_l2_stats = percentiles(sface_l2_genuine)
    sface_cosine_stats = percentiles(sface_cosine_genuine)

    out_dir = Path(_abs(args.output_dir))
    out_dir.mkdir(parents=True, exist_ok=True)

    if lbph_genuine:
        save_distance_histogram(
            lbph_genuine, str(out_dir / "lbph_genuine_distance_hist.png"),
            threshold=tau_accept,
            title="Genuine (same-identity) LBPH distance - disjoint gallery/probe split",
            xlabel=f"LBPH distance (native predict_collect scale) - dashed line = tau_accept ({tau_accept})",
        )
        save_distance_histogram(
            lbph_genuine, str(out_dir / "lbph_genuine_distance_hist_tau_reject.png"),
            threshold=tau_reject,
            title="Genuine (same-identity) LBPH distance vs tau_reject - disjoint gallery/probe split",
            xlabel=f"LBPH distance (native predict_collect scale) - dashed line = tau_reject ({tau_reject})",
        )
    if sface_l2_genuine:
        save_distance_histogram(
            sface_l2_genuine, str(out_dir / "sface_l2_genuine_distance_hist.png"),
            threshold=l2_genuine,
            title="Genuine (same-identity) SFace L2 distance - disjoint gallery/probe split",
            xlabel=f"SFace L2 distance - dashed line = l2_genuine ({l2_genuine})",
            xlim=(0.0, 2.0),
        )

    summary = {
        "split_manifest": args.split_manifest,
        "split_manifest_triples_sha256": manifest.get("triples_sha256"),
        "n_identities_considered": len(identities),
        "n_probes": n_probes,
        "n_no_face_fallback": n_no_face,
        "n_missing_gallery_embedding": n_missing_gallery_embedding,
        "thresholds": {
            "lbph_tau_accept": tau_accept,
            "lbph_tau_reject": tau_reject,
            "sface_l2_genuine": l2_genuine,
            "sface_cosine_genuine": cosine_genuine,
        },
        "lbph_genuine_distance": lbph_stats,
        "sface_l2_genuine_distance": sface_l2_stats,
        "sface_cosine_genuine": sface_cosine_stats,
        "lbph_genuine_below_tau_accept_percent": (
            100.0 * sum(1 for d in lbph_genuine if d <= tau_accept) / len(lbph_genuine)
            if lbph_genuine else None
        ),
        "lbph_genuine_below_tau_reject_percent": (
            100.0 * sum(1 for d in lbph_genuine if d <= tau_reject) / len(lbph_genuine)
            if lbph_genuine else None
        ),
        "sface_genuine_passes_dual_rule_percent": (
            100.0 * sum(
                1 for c, l2 in zip(sface_cosine_genuine, sface_l2_genuine)
                if c >= cosine_genuine and l2 <= l2_genuine
            ) / len(sface_l2_genuine)
            if sface_l2_genuine else None
        ),
    }
    (out_dir / "genuine_distance_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("\n[SUMMARY]")
    print(f"  probes considered      : {n_probes} (no-face fallback: {n_no_face})")
    print(f"  LBPH genuine distance  : {lbph_stats}")
    print(f"    <= tau_accept ({tau_accept}): {summary['lbph_genuine_below_tau_accept_percent']}")
    print(f"    <= tau_reject ({tau_reject}): {summary['lbph_genuine_below_tau_reject_percent']}")
    print(f"  SFace genuine L2       : {sface_l2_stats}")
    print(f"  SFace genuine cosine   : {sface_cosine_stats}")
    print(f"    passes dual rule: {summary['sface_genuine_passes_dual_rule_percent']}")
    print(f"  Wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
