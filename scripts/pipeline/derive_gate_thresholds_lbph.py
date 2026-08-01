#!/usr/bin/env python3
"""Derive the cascade gate's LBPH thresholds (``tau_accept``, ``tau_reject``)
from the gallery/probe-disjoint LFW identification protocol.

Why this exists
---------------
``tau_reject`` is currently carried in ``src/hybrid/thresholds.json`` as an
*impostor* quantile - "the LBPH distance at ~1% FAR", taken off the same
independence sweep that produced ``tau_accept`` at ~10 ppm. That derivation is
methodologically wrong for what ``tau_reject`` actually does.

Read ``src/hybrid/gate.py``: the two thresholds sit on opposite sides of a
different question.

* ``d1 <= tau_accept`` -> **accept on LBPH alone, SFace is never consulted.**
  The risk here is letting an impostor in, so this threshold is correctly
  driven by the *impostor* distribution at a FAR target.
* ``d1 >= tau_reject`` -> **reject as Unknown, SFace is never consulted.**
  The risk here is throwing away a genuine user that SFace would have
  recognised. Nothing about the impostor distribution bounds that risk. A 1%-FAR
  impostor quantile answers "how far out do impostors sit", when the question is
  "how far out do *my own enrolled users* sit before I stop asking the
  accelerator".

So ``tau_reject`` is a **genuine-side / escalation-budget** threshold, and the
only honest way to set it is to measure where mated probes actually land and
trade pre-gate false rejects against SFace invocation cost. That is a curve, and
this script emits it.

Protocol
--------
The gallery/probe-disjoint split (``data/splits/lfw_ident_split_seed42.json``,
``docs/audits/STATE-08-01.md``): 5,749 identities enrolled from one image each,
1,680 probes that are *different photographs of enrolled people*. Every probe is
mated, which is what makes the false-reject side measurable at all - the
one-image-per-identity independence sweeps have no genuine pairs by
construction and therefore cannot say anything about ``tau_reject``.

This is also the *deployment* comparison shape - probe against an enrolled
gallery - rather than the probe-vs-probe shape of the independence tests.

Distance scale
--------------
Native ``cv.face.LBPHFaceRecognizer::predict_collect()`` throughout, via
``LBPHAdapter.score()`` - the same code path the deployed recognizer runs, so
these numbers are directly comparable to ``thresholds.json``. This is **not**
the ``src/independence_common.py`` hand-rolled chi-square scale (~4x apart; see
``.claude/skills/cv-repo-map`` §2).

Crop family (``--crop-mode``) matters and is recorded in every output:

* ``frame`` (default) - ``assume_cropped=True``: LBPH normalises the whole LFW
  tile. This matches how ``models/lfw2/`` was **enrolled**
  (``run_lfw2_robustness.py::ensure_lfw2_enrollment``) and how
  ``accuracy_ratio_hybrid.py`` probes, so gallery and probe agree. It is the
  family the currently deployed 77.7693 / 88.4927 pair belongs to.
* ``box`` - ``assume_cropped=False``: LBPH normalises the YuNet face box, the
  crop-matched family of the standalone LBPH artifact
  (``reports/independence/lbph_lfw1/native_predict_scale_yunet.json``, 67.0333).
  **Requires a gallery enrolled the same way** - pass ``--enroll`` (this script
  builds and caches one) or the gallery and probe crop families silently
  disagree and every number below is meaningless.

Never mix a ``tau_accept`` from one family with a ``tau_reject`` from the other.

Outputs
-------
``<output-dir>/``
  ``records.npz``          full probe x gallery distance matrix + labels, so
                           every threshold below can be re-derived offline with
                           ``--from-records`` (seconds, no rescoring).
  ``gate_thresholds.json`` derived thresholds, realized rates, trade-off curves.
  ``gate_thresholds.md``   the same, readable.
  ``*.png``                distributions and the tau_reject trade-off curve.

Nothing here writes to ``src/hybrid/thresholds.json``. These are *candidates*;
promoting one is a separate, deliberate act that must also move
``gate.py::_FALLBACK_GATE_DEFAULTS``, ``calibrate.py``, and a dated
``docs/audits/STATE-*.md`` entry (see ``docs/READ THIS/FROZEN_THRESHOLDS.md``).

Usage::

    # score + derive (~5 min: 1,680 probes against a 5,749-class model)
    python scripts/pipeline/derive_gate_thresholds_lbph.py \
        --split-manifest data/splits/lfw_ident_split_seed42.json \
        --lbph-model models/lfw2/lbph_seed42_manifest2ef84e167992.yml \
        --lbph-labels models/lfw2/lbph_labels_seed42_manifest2ef84e167992.json

    # re-derive at a different budget, no rescoring
    python scripts/pipeline/derive_gate_thresholds_lbph.py \
        --from-records reports/independence/lbph_gate_disjoint/records.npz \
        --frr-target 0.005 --escalation-budget 0.30
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark.accuracy_ratio_hybrid import tile_sample  # noqa: E402
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import IMG_SIZE, normalize_face  # noqa: E402
from src.hybrid.gate import GateThresholds  # noqa: E402
from src.hybrid.recognizer import (  # noqa: E402
    DEFAULT_LBPH_LABELS,
    DEFAULT_LBPH_MODEL,
    DEFAULT_THRESHOLDS_PATH,
    LBPHAdapter,
    detect_sample,
    load_thresholds,
)
from src.independence_plots import save_distance_histogram  # noqa: E402

# The standalone LBPH-alone independence threshold, reported alongside the
# derived values as a cross-check. Immutable run record (not config), so it is
# safe to cite: reports/independence/lbph_lfw1/native_predict_scale_yunet.json,
# rank 165 / 9.986 ppm, YuNet, box-cropped, native predict_collect scale.
STANDALONE_LBPH_TAU_ACCEPT = 67.03325520645528
STANDALONE_ARTIFACT = "reports/independence/lbph_lfw1/native_predict_scale_yunet.json"


def _abs(path_value: str) -> str:
    p = Path(path_value)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


# --------------------------------------------------------------------------- #
# Scoring pass
# --------------------------------------------------------------------------- #
def load_manifest(path: str) -> dict:
    """Read an ``lsface-lfw-ident-split-v1`` manifest.

    Inlined rather than imported from ``accuracy_ratio_hybrid`` so this script
    keeps working against checkouts where that module's split-manifest support
    is not present.
    """
    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    if "identities" not in manifest:
        raise ValueError(f"{path}: not a split manifest (no 'identities' key)")
    return manifest


def to_bgr_gray(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Normalize a freshly-read image into the (bgr, gray) pair adapters want."""
    if image.ndim == 2:
        return cv.cvtColor(image, cv.COLOR_GRAY2BGR), image
    return image, cv.cvtColor(image, cv.COLOR_BGR2GRAY)


def ensure_crop_matched_gallery(
    manifest: dict, manifest_path: str, crop_mode: str, enroll_dir: Path
) -> tuple[str, str]:
    """Enrol an LBPH gallery whose crop family matches how probes will be scored.

    ``models/lfw2/`` is enrolled with ``assume_cropped=True`` only, so scoring
    probes at ``--crop-mode box`` against it would put gallery and probe on two
    different crop families - the exact silent mismatch
    ``.claude/skills/cv-workspace-map`` §3.2 documents. This builds the missing
    half so a box-family ``tau_accept``/``tau_reject`` pair can be derived on the
    same footing as the frame-family one.

    Mirrors ``run_lfw2_robustness.py::ensure_lfw2_enrollment`` (same detector,
    same ``tan-triggs`` equalization, same LBPH params) except for the crop mode
    and that no SFace gallery is built - this derivation is LBPH-only. Cached on
    the manifest hash plus the crop mode, so the two families can never collide.
    """
    import hashlib

    sha12 = hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()[:12]
    enroll_dir.mkdir(parents=True, exist_ok=True)
    model_path = enroll_dir / f"lbph_manifest{sha12}_crop-{crop_mode}.yml"
    labels_path = enroll_dir / f"lbph_labels_manifest{sha12}_crop-{crop_mode}.json"
    if model_path.exists() and labels_path.exists():
        print(f"[ENROLL] Reusing crop-matched gallery {model_path.name}", flush=True)
        return str(model_path), str(labels_path)

    root = Path(manifest["dataset_root"])
    assume_cropped = crop_mode == "frame"
    detector = create_face_detector("yunet")
    equalization = SPECS["lbph"].default_equalization

    selection = [
        (person, entry["gallery"])
        for person, entry in sorted(manifest["identities"].items())
        if entry.get("gallery")
    ]
    print(
        f"[ENROLL] Building crop-matched gallery: {len(selection)} identities, "
        f"crop-mode={crop_mode}, equalization={equalization}",
        flush=True,
    )

    faces: list[np.ndarray] = []
    labels: list[int] = []
    label_map: dict[str, int] = {}
    misses = 0
    for i, (person, rel) in enumerate(selection, 1):
        img = cv.imread(str(root / rel))
        if img is None:
            continue
        image_bgr, image_gray = to_bgr_gray(img)
        sample = detect_sample(
            detector,
            image_bgr=image_bgr,
            image_gray=image_gray,
            assume_cropped=assume_cropped,
        )
        if sample is None:
            face_gray = image_gray
            misses += 1
        else:
            face_gray = sample.face_gray
        label_map[person] = len(label_map)
        faces.append(normalize_face(face_gray, img_size=IMG_SIZE, equalization=equalization))
        labels.append(label_map[person])
        if i % 500 == 0:
            print(f"[ENROLL] {i}/{len(selection)} enrolled...", flush=True)

    if len(faces) < 2:
        raise RuntimeError("Not enough enrollable gallery images.")
    print(f"[ENROLL] Training LBPH on {len(faces)} faces ({misses} YuNet misses)...", flush=True)
    recognizer = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(faces, np.array(labels, dtype=np.int32))
    recognizer.save(str(model_path))
    labels_path.write_text(json.dumps(label_map, indent=2), encoding="utf-8")
    print(f"[ENROLL] Saved {model_path}", flush=True)
    return str(model_path), str(labels_path)


def score_probes(args: argparse.Namespace) -> dict:
    """Score every manifest probe against the enrolled gallery.

    Returns the arrays that every downstream threshold is a pure function of:
    the full ``[n_probes, n_gallery]`` distance matrix plus the column index of
    each probe's own (mated) identity.
    """
    manifest = load_manifest(_abs(args.split_manifest))
    root = Path(manifest["dataset_root"])

    if args.enroll:
        model_path, labels_path = ensure_crop_matched_gallery(
            manifest, _abs(args.split_manifest), args.crop_mode, Path(_abs(args.enroll_dir))
        )
    else:
        model_path, labels_path = _abs(args.lbph_model), _abs(args.lbph_labels)
    lbph = LBPHAdapter(model_path=model_path, labels_path=labels_path)
    gallery_names = [lbph.id_to_name[i] for i in sorted(lbph.id_to_name)]
    name_to_col = {name: i for i, name in enumerate(gallery_names)}
    n_gallery = len(gallery_names)

    detector = create_face_detector("yunet")
    assume_cropped = args.crop_mode == "frame"

    probe_rows = [
        (person, entry["probe"])
        for person, entry in sorted(manifest["identities"].items())
        if entry.get("probe")
    ]
    if args.limit_probes:
        probe_rows = probe_rows[: args.limit_probes]

    n_probes = len(probe_rows)
    print(
        f"[INFO] {n_probes} probes vs {n_gallery} enrolled identities "
        f"(crop-mode={args.crop_mode}, assume_cropped={assume_cropped})",
        flush=True,
    )

    dist = np.full((n_probes, n_gallery), np.inf, dtype=np.float32)
    genuine_col = np.full(n_probes, -1, dtype=np.int32)
    margins = np.zeros(n_probes, dtype=np.float32)
    kept: list[str] = []
    n_no_face = 0
    n_unreadable = 0
    n_unenrolled = 0

    t0 = time.time()
    row = 0
    for person, rel in probe_rows:
        img = cv.imread(str(root / rel))
        if img is None:
            n_unreadable += 1
            continue
        if person not in name_to_col:
            # A probe whose identity was never enrolled has no genuine column,
            # so it cannot contribute to either side of the derivation.
            n_unenrolled += 1
            continue

        image_bgr, image_gray = to_bgr_gray(img)
        sample = detect_sample(
            detector,
            image_bgr=image_bgr,
            image_gray=image_gray,
            assume_cropped=assume_cropped,
        )
        if sample is None:
            # Same fallback the benchmark uses: treat the whole tile as the face
            # rather than dropping the probe, so the false-reject denominator
            # stays the full probe set.
            n_no_face += 1
            sample = tile_sample(image_bgr, image_gray)

        match = lbph.score(sample)
        for name, d in match.all_distances.items():
            col = name_to_col.get(name)
            if col is not None:
                dist[row, col] = d
        genuine_col[row] = name_to_col[person]
        margins[row] = match.margin
        kept.append(person)
        row += 1

        if row % args.progress_every == 0 or row == n_probes:
            elapsed = time.time() - t0
            eta = elapsed / row * (n_probes - row)
            print(
                f"  [probe] {row}/{n_probes} elapsed {elapsed / 60:.1f}m eta {eta / 60:.1f}m",
                flush=True,
            )

    dist = dist[:row]
    genuine_col = genuine_col[:row]
    margins = margins[:row]

    print(
        f"[INFO] scored {row} probes "
        f"(no-face fallback {n_no_face}, unreadable {n_unreadable}, unenrolled {n_unenrolled})",
        flush=True,
    )
    return {
        "dist": dist,
        "genuine_col": genuine_col,
        "margins": margins,
        "probe_names": np.array(kept),
        "gallery_names": np.array(gallery_names),
        "meta": {
            "split_manifest": args.split_manifest,
            "split_manifest_triples_sha256": manifest.get("triples_sha256"),
            "dataset_root": str(root),
            "lbph_model": model_path,
            "lbph_labels": labels_path,
            "gallery_enrolled_by_this_script": bool(args.enroll),
            "crop_mode": args.crop_mode,
            "assume_cropped": assume_cropped,
            "detector": "yunet",
            "scale": "native cv.face.LBPHFaceRecognizer.predict_collect() "
                     "(radius=1, neighbors=8, grid=8x8)",
            "n_probes_scored": row,
            "n_gallery": n_gallery,
            "n_no_face_fallback": n_no_face,
            "n_unreadable": n_unreadable,
            "n_unenrolled": n_unenrolled,
        },
    }


# --------------------------------------------------------------------------- #
# Derivation
# --------------------------------------------------------------------------- #
def split_genuine_impostor(dist: np.ndarray, genuine_col: np.ndarray) -> dict:
    """Decompose the distance matrix into the quantities the gate actually sees.

    ``d1`` is the top-1 distance - what ``decide_escalation`` is handed. The
    genuine and impostor arrays are what ``d1`` is made of.
    """
    n_probes, n_gallery = dist.shape
    rows = np.arange(n_probes)

    d_genuine = dist[rows, genuine_col].astype(np.float64)

    impostor = dist.astype(np.float64).copy()
    impostor[rows, genuine_col] = np.inf
    d_impostor_min = impostor.min(axis=1)
    top1_impostor_col = impostor.argmin(axis=1)

    d1 = np.minimum(d_genuine, d_impostor_min)
    rank1_correct = d_genuine <= d_impostor_min

    flat = impostor.ravel()
    impostor_pool = np.sort(flat[np.isfinite(flat)])

    return {
        "d_genuine": d_genuine,
        "d_impostor_min": d_impostor_min,
        "top1_impostor_col": top1_impostor_col,
        "d1": d1,
        "rank1_correct": rank1_correct,
        "impostor_pool": impostor_pool,
        "n_probes": n_probes,
        "n_gallery": n_gallery,
    }


def derive_tau_accept(parts: dict, far_target: float) -> dict:
    """Impostor-driven, unchanged in kind from the independence tests.

    Accepting on LBPH alone skips SFace entirely, so the bound that matters is
    how often a *wrong* identity gets under the threshold. Two rates are
    reported because they answer different questions and differ by orders of
    magnitude:

    * ``far_comparison`` - per-comparison, over all probe x non-mated-gallery
      pairs. This is the convention the independence tests use, so it is the
      one comparable to the standalone 67.0333.
    * ``fpir`` - per-probe: the fraction of probes whose *best impostor* clears
      the threshold. This is the operationally correct 1:N rate, but with only
      n_probes samples its resolution floor is 1/n_probes, far coarser than a
      10 ppm target, so it cannot be used to *set* the threshold here.
    """
    pool = parts["impostor_pool"]
    n_pairs = int(pool.size)
    k = max(1, int(np.floor(far_target * n_pairs)))
    k = min(k, n_pairs)
    tau_accept = float(pool[k - 1])

    d_imp_min = parts["d_impostor_min"]
    n_probes = parts["n_probes"]
    fpir = float(np.count_nonzero(d_imp_min <= tau_accept) / n_probes)

    return {
        "tau_accept": tau_accept,
        "far_target_ppm": far_target * 1e6,
        "rank": k,
        "n_impostor_comparisons": n_pairs,
        "realized_far_comparison_ppm": 1e6 * k / n_pairs,
        "realized_fpir": fpir,
        "fpir_resolution_ppm": 1e6 / n_probes,
        "curve": [
            {
                "rank": r,
                "tau": float(pool[r - 1]),
                "far_comparison_ppm": 1e6 * r / n_pairs,
            }
            for r in (1, 2, 4, 8, 16, 32, 64, 96, 128, 165, 256, 512, 1024, 4096)
            if r <= n_pairs
        ],
    }


def gate_rates(d1: np.ndarray, tau_accept: float, tau_reject: float) -> dict:
    """Route every probe through the gate's band arithmetic.

    Mirrors ``decide_escalation`` clause 1 exactly (``tau_accept < d < tau_reject``
    escalates). The margin and quality clauses are deliberately excluded: they
    escalate *additional* frames regardless of the band, so band-derived
    escalation is a lower bound on real SFace load, and band-derived rejects are
    an upper bound on real pre-gate loss.
    """
    n = d1.size
    confident_accept = np.count_nonzero(d1 <= tau_accept)
    escalate = np.count_nonzero((d1 > tau_accept) & (d1 < tau_reject))
    confident_reject = np.count_nonzero(d1 >= tau_reject)
    return {
        "confident_accept_rate": confident_accept / n,
        "escalation_rate": escalate / n,
        "pre_gate_reject_rate": confident_reject / n,
        "n_confident_accept": int(confident_accept),
        "n_escalate": int(escalate),
        "n_pre_gate_reject": int(confident_reject),
    }


def derive_tau_reject(
    parts: dict,
    tau_accept: float,
    frr_target: float,
    escalation_budget: float | None,
) -> dict:
    """Genuine-side / escalation-budget driven - the point of this script.

    Every probe in this protocol is mated, so a probe with ``d1 >= tau_reject``
    is a person the system *knows*, refused, without ever asking SFace. That is
    the irrecoverable cost, and it is monotone: raising ``tau_reject`` can only
    reduce it, while raising SFace invocation load. So the derivation is

        smallest tau_reject whose pre-gate reject rate <= frr_target

    optionally capped by ``escalation_budget`` (the largest tau_reject whose
    escalation rate stays within the SFace latency/power budget). When both are
    given and they conflict, the conflict is reported rather than silently
    resolved - it means the budget cannot buy the target and one of them has to
    move.

    Note this uses ``d1``, not the genuine distance: the gate only ever sees the
    top-1 score. A probe whose top-1 is a wrong identity is still routed on that
    wrong identity's distance.
    """
    d1 = parts["d1"]
    n = int(d1.size)
    ordered = np.sort(d1)

    # Largest allowed count of pre-gate rejects, then the smallest tau that
    # admits no more than that. searchsorted gives exact tie-aware counts.
    allowed = int(np.floor(frr_target * n))
    if allowed <= 0:
        # Nothing may be rejected pre-gate: sit just above the worst probe.
        tau_frr = float(np.nextafter(ordered[-1], np.inf))
    else:
        tau_frr = float(ordered[n - allowed])

    result = {
        "frr_target": frr_target,
        "tau_reject_frr_driven": tau_frr,
        "rates_at_frr_driven": gate_rates(d1, tau_accept, tau_frr),
    }

    if escalation_budget is not None:
        # Largest tau_reject whose escalation rate stays within budget. The band
        # only grows with tau_reject, so scan the sorted d1 values above
        # tau_accept and take the last one that fits.
        candidates = ordered[ordered > tau_accept]
        best = float(np.nextafter(tau_accept, np.inf))
        for cand in candidates:
            rate = np.count_nonzero((d1 > tau_accept) & (d1 < cand)) / n
            if rate <= escalation_budget:
                best = float(cand)
            else:
                break
        result["escalation_budget"] = escalation_budget
        result["tau_reject_budget_capped"] = best
        result["rates_at_budget_capped"] = gate_rates(d1, tau_accept, best)
        result["budget_meets_frr_target"] = bool(
            result["rates_at_budget_capped"]["pre_gate_reject_rate"] <= frr_target
        )
        chosen = min(tau_frr, best) if not result["budget_meets_frr_target"] else tau_frr
        result["tau_reject"] = chosen
        result["binding_constraint"] = (
            "frr_target" if chosen == tau_frr else "escalation_budget"
        )
    else:
        result["tau_reject"] = tau_frr
        result["binding_constraint"] = "frr_target"

    result["rates_at_chosen"] = gate_rates(d1, tau_accept, result["tau_reject"])
    return result


def tradeoff_curve(parts: dict, tau_accept: float, points: int = 60) -> list[dict]:
    """The whole trade-off, so the chosen point can be seen in context."""
    d1 = parts["d1"]
    lo = float(max(tau_accept, d1.min()))
    hi = float(d1.max())
    if hi <= lo:
        hi = lo + 1.0
    grid = np.linspace(lo, hi, points)
    rank1 = parts["rank1_correct"]
    n = d1.size
    out = []
    for tau in grid:
        rates = gate_rates(d1, tau_accept, float(tau))
        # Correct-identity probes lost pre-gate: the subset of the reject rate
        # that SFace could not have been blamed for.
        lost_correct = np.count_nonzero(rank1 & (d1 >= tau)) / n
        out.append(
            {
                "tau_reject": float(tau),
                "escalation_rate": rates["escalation_rate"],
                "pre_gate_reject_rate": rates["pre_gate_reject_rate"],
                "rank1_correct_lost_rate": float(lost_correct),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def plot_tradeoff(curve: list[dict], chosen: float, deployed: float | None, path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tau = [c["tau_reject"] for c in curve]
    esc = [100 * c["escalation_rate"] for c in curve]
    rej = [100 * c["pre_gate_reject_rate"] for c in curve]
    lost = [100 * c["rank1_correct_lost_rate"] for c in curve]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(tau, esc, label="SFace escalation rate (cost)", color="#1f77b4")
    ax.plot(tau, rej, label="pre-gate reject rate (loss)", color="#d62728")
    ax.plot(
        tau, lost, label="rank-1-correct probes lost", color="#ff7f0e", ls=":",
    )
    ax.axvline(chosen, color="green", ls="--", label=f"derived tau_reject = {chosen:.4f}")
    if deployed is not None:
        ax.axvline(
            deployed, color="grey", ls="-.", label=f"deployed tau_reject = {deployed:.4f}"
        )
    ax.set_xlabel("tau_reject (LBPH native predict_collect distance)")
    ax.set_ylabel("percent of probes")
    ax.set_title("tau_reject trade-off: SFace load vs irrecoverable false rejects")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def write_markdown(report: dict, path: Path) -> None:
    m = report["meta"]
    ta = report["tau_accept"]
    tr = report["tau_reject"]
    dep = report["deployed_comparison"]
    lines = [
        "# LBPH gate thresholds from the disjoint identification protocol",
        "",
        f"- protocol: gallery/probe-disjoint 1:N, {m['n_probes_scored']} mated probes "
        f"vs {m['n_gallery']} enrolled identities",
        f"- scale: {m['scale']}",
        f"- crop family: **{m['crop_mode']}** (assume_cropped={m['assume_cropped']}) "
        "- do not mix families across the two thresholds",
        f"- detector: {m['detector']}, split sha256 {m['split_manifest_triples_sha256']}",
        "",
        "## tau_accept (impostor-driven)",
        "",
        f"- **{ta['tau_accept']:.4f}** at rank {ta['rank']} of "
        f"{ta['n_impostor_comparisons']:,} impostor comparisons",
        f"- realized per-comparison FAR: {ta['realized_far_comparison_ppm']:.2f} ppm "
        f"(target {ta['far_target_ppm']:.2f} ppm)",
        f"- realized per-probe FPIR at that threshold: {ta['realized_fpir'] * 100:.3f}% "
        f"(resolution floor {ta['fpir_resolution_ppm']:.0f} ppm - too coarse to set a "
        "10 ppm threshold, reported only)",
        "",
        "## tau_reject (genuine-side / escalation-budget driven)",
        "",
        f"- **{tr['tau_reject']:.4f}**, binding constraint: `{tr['binding_constraint']}`",
        f"- pre-gate false-reject target: {tr['frr_target'] * 100:.2f}%",
    ]
    r = tr["rates_at_chosen"]
    lines += [
        "",
        "| routed | share of probes |",
        "|---|---|",
        f"| confident accept (`d1 <= tau_accept`) | {r['confident_accept_rate'] * 100:.2f}% "
        f"({r['n_confident_accept']}) |",
        f"| escalate to SFace | {r['escalation_rate'] * 100:.2f}% ({r['n_escalate']}) |",
        f"| pre-gate reject (`d1 >= tau_reject`) | {r['pre_gate_reject_rate'] * 100:.2f}% "
        f"({r['n_pre_gate_reject']}) |",
        "",
        "Band clause only. The margin and quality clauses escalate additional frames,",
        "so escalation here is a lower bound and pre-gate loss an upper bound.",
        "",
        "## Against what is deployed",
        "",
        f"- deployed tau_accept {dep['deployed_tau_accept']} -> per-comparison FAR "
        f"{dep['deployed_tau_accept_far_ppm']:.2f} ppm on this protocol",
        f"- deployed tau_reject {dep['deployed_tau_reject']} -> "
        f"{dep['rates_at_deployed']['pre_gate_reject_rate'] * 100:.2f}% of mated probes "
        f"rejected before SFace is asked, "
        f"{dep['rates_at_deployed']['escalation_rate'] * 100:.2f}% escalated",
        f"- standalone LBPH tau_accept {STANDALONE_LBPH_TAU_ACCEPT:.4f} "
        f"({STANDALONE_ARTIFACT}) -> per-comparison FAR "
        f"{dep['standalone_tau_accept_far_ppm']:.2f} ppm on this protocol "
        f"(**box**-cropped family; comparable only when `--crop-mode box`)",
        "",
        "## Identification sanity",
        "",
        f"- rank-1 accuracy (threshold-free): {report['rank1_accuracy'] * 100:.2f}%",
        f"- genuine distance p50 / p95 / p99: {report['genuine_percentiles']['p50']:.4f} / "
        f"{report['genuine_percentiles']['p95']:.4f} / "
        f"{report['genuine_percentiles']['p99']:.4f}",
        "",
        "Candidates only - nothing here was written to `src/hybrid/thresholds.json`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--split-manifest", default="data/splits/lfw_ident_split_seed42.json")
    p.add_argument("--lbph-model", default=DEFAULT_LBPH_MODEL)
    p.add_argument("--lbph-labels", default=DEFAULT_LBPH_LABELS)
    p.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH,
                   help="Read only, for the deployed-value comparison. Never written.")
    p.add_argument("--enroll", action="store_true",
                   help="Enrol a gallery whose crop family matches --crop-mode instead of "
                        "using --lbph-model. Required for --crop-mode box: models/lfw2/ is "
                        "frame-enrolled only, so scoring box probes against it mixes families.")
    p.add_argument("--enroll-dir", default="models/lfw2",
                   help="Where crop-matched galleries are cached (~720 MB each).")
    p.add_argument("--crop-mode", choices=("frame", "box"), default="frame",
                   help="frame: LBPH sees the whole tile (matches models/lfw2 enrolment "
                        "and the deployed 77.7693 family). box: LBPH sees the YuNet face "
                        "box (the standalone 67.0333 family) - needs a box-enrolled gallery.")
    p.add_argument("--far-target", type=float, default=1e-5,
                   help="Per-comparison impostor FAR for tau_accept (default 1e-5 = 10 ppm).")
    p.add_argument("--frr-target", type=float, default=0.01,
                   help="Max share of mated probes rejected before SFace is consulted.")
    p.add_argument("--escalation-budget", type=float, default=None,
                   help="Optional cap on the share of probes routed to SFace.")
    p.add_argument("--tau-accept", type=float, default=None,
                   help="Condition tau_reject on this tau_accept instead of the derived one.")
    p.add_argument("--from-records", default=None,
                   help="Re-derive from a previous run's records.npz (no rescoring).")
    p.add_argument("--limit-probes", type=int, default=0, help="Smoke runs only.")
    p.add_argument("--progress-every", type=int, default=100)
    p.add_argument("--output-dir", default="reports/independence/lbph_gate_disjoint")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(_abs(args.output_dir))
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.from_records:
        blob = np.load(_abs(args.from_records), allow_pickle=True)
        scored = {
            "dist": blob["dist"],
            "genuine_col": blob["genuine_col"],
            "margins": blob["margins"],
            "probe_names": blob["probe_names"],
            "gallery_names": blob["gallery_names"],
            "meta": json.loads(str(blob["meta"])),
        }
        print(f"[LOAD] {args.from_records}")
    else:
        scored = score_probes(args)
        np.savez_compressed(
            out_dir / "records.npz",
            dist=scored["dist"],
            genuine_col=scored["genuine_col"],
            margins=scored["margins"],
            probe_names=scored["probe_names"],
            gallery_names=scored["gallery_names"],
            meta=json.dumps(scored["meta"]),
        )
        print(f"[SAVE] {out_dir / 'records.npz'}")

    meta = scored["meta"]
    parts = split_genuine_impostor(scored["dist"], scored["genuine_col"])

    tau_accept_report = derive_tau_accept(parts, args.far_target)
    tau_accept = args.tau_accept if args.tau_accept is not None else tau_accept_report["tau_accept"]
    if args.tau_accept is not None:
        tau_accept_report["tau_accept_override"] = args.tau_accept

    tau_reject_report = derive_tau_reject(
        parts, tau_accept, args.frr_target, args.escalation_budget
    )
    curve = tradeoff_curve(parts, tau_accept)

    # Where the currently deployed pair lands on this protocol.
    cfg = load_thresholds(_abs(args.thresholds_json))
    deployed = GateThresholds.from_dict(cfg.get("gate"))
    pool = parts["impostor_pool"]
    n_pairs = pool.size

    def far_ppm_at(tau: float) -> float:
        return 1e6 * float(np.searchsorted(pool, tau, side="right")) / n_pairs

    deployed_comparison = {
        "thresholds_json": args.thresholds_json,
        "deployed_tau_accept": deployed.tau_accept,
        "deployed_tau_reject": deployed.tau_reject,
        "deployed_tau_accept_far_ppm": far_ppm_at(deployed.tau_accept),
        "deployed_tau_accept_fpir": float(
            np.count_nonzero(parts["d_impostor_min"] <= deployed.tau_accept) / parts["n_probes"]
        ),
        "rates_at_deployed": gate_rates(parts["d1"], deployed.tau_accept, deployed.tau_reject),
        "standalone_tau_accept": STANDALONE_LBPH_TAU_ACCEPT,
        "standalone_tau_accept_far_ppm": far_ppm_at(STANDALONE_LBPH_TAU_ACCEPT),
        "standalone_artifact": STANDALONE_ARTIFACT,
        "standalone_crop_family": "box",
        "note": "standalone_* is the box-cropped family; comparable to these numbers "
                "only when this run used --crop-mode box.",
    }

    d_gen = parts["d_genuine"]
    report = {
        "meta": meta,
        "tau_accept": tau_accept_report,
        "tau_reject": tau_reject_report,
        "tau_accept_used": tau_accept,
        "rank1_accuracy": float(np.count_nonzero(parts["rank1_correct"]) / parts["n_probes"]),
        "genuine_percentiles": {
            f"p{q}": float(np.percentile(d_gen, q)) for q in (1, 5, 25, 50, 75, 95, 99)
        },
        "genuine_min": float(d_gen.min()),
        "genuine_max": float(d_gen.max()),
        "d1_percentiles": {
            f"p{q}": float(np.percentile(parts["d1"], q)) for q in (50, 90, 95, 99)
        },
        "deployed_comparison": deployed_comparison,
        "tradeoff_curve": curve,
    }
    (out_dir / "gate_thresholds.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, out_dir / "gate_thresholds.md")

    chosen_reject = tau_reject_report["tau_reject"]
    save_distance_histogram(
        d_gen.tolist(),
        str(out_dir / "lbph_genuine_vs_tau_reject.png"),
        threshold=chosen_reject,
        title="Genuine (mated) LBPH distance vs derived tau_reject",
        xlabel=f"LBPH distance (native predict_collect) - dashed = tau_reject {chosen_reject:.4f}",
    )
    save_distance_histogram(
        parts["d1"].tolist(),
        str(out_dir / "lbph_top1_vs_tau_accept.png"),
        threshold=tau_accept,
        title="Top-1 LBPH distance over mated probes vs derived tau_accept",
        xlabel=f"LBPH top-1 distance - dashed = tau_accept {tau_accept:.4f}",
    )
    plot_tradeoff(
        curve, chosen_reject, deployed.tau_reject, str(out_dir / "tau_reject_tradeoff.png")
    )

    r = tau_reject_report["rates_at_chosen"]
    print("\n[RESULT] crop-mode=%s  probes=%d  gallery=%d" % (
        meta["crop_mode"], meta["n_probes_scored"], meta["n_gallery"]))
    print(f"  tau_accept  = {tau_accept:.4f} "
          f"({tau_accept_report['realized_far_comparison_ppm']:.2f} ppm per-comparison FAR, "
          f"rank {tau_accept_report['rank']}/{tau_accept_report['n_impostor_comparisons']:,})")
    print(f"  tau_reject  = {chosen_reject:.4f} "
          f"(binding: {tau_reject_report['binding_constraint']})")
    print(f"  routing     : accept {r['confident_accept_rate'] * 100:.2f}%  "
          f"escalate {r['escalation_rate'] * 100:.2f}%  "
          f"pre-gate reject {r['pre_gate_reject_rate'] * 100:.2f}%")
    print(f"  rank-1      : {report['rank1_accuracy'] * 100:.2f}%")
    print(f"  deployed    : tau_accept {deployed.tau_accept} "
          f"({deployed_comparison['deployed_tau_accept_far_ppm']:.2f} ppm), "
          f"tau_reject {deployed.tau_reject} -> "
          f"{deployed_comparison['rates_at_deployed']['pre_gate_reject_rate'] * 100:.2f}% "
          f"pre-gate reject")
    print(f"  Wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
