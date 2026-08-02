"""41-modification Accuracy Ratio for CV (LBPH), DL (SFace), and the hybrid cascade.

This is the complementarity benchmark: the SAME 41 deterministic (modification,
level) probes from ``src/benchmark/modifications.py`` (identical seeds, so the
probes are bit-identical to the classical ``accuracy_ratio.py`` run) are scored
by three configurations of the one hybrid system:

* ``cv_only``  - LBPH alone (accept = correct identity AND distance <= tau_accept,
  the frozen LBPH-only independence threshold; tau_reject is cascade-gate-only),
* ``dl_only``  - SFace alone (accept = correct identity AND the genuine rule
                 cosine >= 0.363 AND l2 <= 1.106796),
* ``cascade``  - the gated hybrid (LBPH fast path, SFace escalation).

For each modification the report gives AR side by side plus the cascade's
escalation rate, so the output directly answers: where does CV hold up, where
does DL hold up, and does the gate route the broken frames to the engine that
survives them. A modification is tagged ``cv_stronger`` / ``dl_stronger`` /
``tie`` and the cascade is checked against ``max(cv, dl)`` per modification.

Probes are the held-out originals (``data/split_lasalle/test`` by default), the
modification is applied to the raw gray tile BEFORE any engine-specific
normalization (like a real capture corruption), and YuNet runs on every probe
for landmarks. When YuNet misses a heavily degraded tile, ``--no-face-policy``
decides: ``fallback`` (default) scores the whole tile without landmarks (SFace
resizes the crop; measures recognizer robustness), ``strict`` counts the probe
as failed for every mode (measures the deployed system, detection included).
No-face counts are reported per modification either way.

Writes ``reports/benchmark/accuracy_ratio_hybrid.{json,md}``.

**Protocol (see docs/audits/STATE-08-01.md):** without ``--split-manifest``,
this runs the ORIGINAL same-image path - enrollment and probing draw from the
same ``select_originals(..., seed=42)`` call, so every probe is a degraded
copy of its own enrolled image and intra-class distance before damage is
always 0. That measures transform sensitivity, not recognition, so its
reporting label is ``transform_sensitivity`` everywhere in this module's
output, never "Accuracy Ratio". Pass ``--split-manifest
data/splits/lfw_ident_split_seed42.json`` (built by
``scripts/utils/make_lfw_identification_split.py``) to run the fixed,
gallery/probe-disjoint 1:N identification protocol instead - THAT path is
what may be reported as "Accuracy Ratio".

``--mod-set {legacy,dl41}`` selects the modification taxonomy: ``legacy`` is
the original 12-family/41-variant set (bit-identical to old reports).
``dl41`` (default here) is the DL team's 41-named-modification taxonomy
(``src/benchmark/modifications.py`` ``DL41_MODIFICATIONS`` /
``DL41_TIER_MAP``, mirrored from ``..\deep-learning\ar-table.py``). Under
``dl41``, ``rot_90``/``rot_180``/``rot_270``/``flip_lr`` are detector-canonical
tests (see ``DL41_DETECTOR_CANONICAL``): always reported in their own section,
and ``--headline-scope`` controls whether they are ALSO averaged into the
headline overall-AR/Rank-1 mean. Default ``all41`` includes them, so the
headline covers all 41 variants and is directly comparable to the DL team's
``ar-table.py`` (which averages every modification in ``MODIFICATION_MAPS``);
``exclude-canonical`` reproduces the 37-variant headline.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import cv2 as cv
import numpy as np

from src.benchmark.modifications import (
    DL41_DETECTOR_CANONICAL,
    DL41_TIER_MAP,
    get_modification_set,
    stable_rng,
)
from src.stats_utils import mcnemar_test, rank_auc, wilson_interval_percent
from src.classical_faces.datasets import list_image_files
from src.classical_faces.detection import create_face_detector
from src.hybrid.recognizer import (
    DEFAULT_LBPH_LABELS,
    DEFAULT_LBPH_MODEL,
    DEFAULT_SFACE_GALLERY,
    DEFAULT_SFACE_IMPOSTORS,
    DEFAULT_THRESHOLDS_PATH,
    FaceSample,
    HybridRecognizer,
    LBPHAdapter,
    SFaceAdapter,
    detect_sample,
    load_thresholds,
)
from src.hybrid.gate import GateThresholds
from src.hybrid.quality import QualityThresholds

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODES = ("cv_only", "dl_only", "cascade")
AR_TIE_TOLERANCE = 2.0  # percentage points before a modification counts as won


def _abs(path_value: str) -> str:
    p = Path(path_value)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


def _fmt_opt(value: float | None, spec: str = ".3f") -> str:
    """Format a possibly-None metric (e.g. TPR/FPR/AUC when the denominator
    is 0 - degenerate on tiny/edge-case probe sets such as smoke runs where
    LBPH is never wrong) without crashing the report writer."""
    return "n/a" if value is None else format(value, spec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Accuracy Ratio over the 41-modification suite: LBPH vs SFace vs hybrid cascade."
    )
    parser.add_argument("--originals-dir", default="data/split_lasalle/test",
                        help="Identity folders of ORIGINAL images (default: held-out test).")
    parser.add_argument("--modes", default=",".join(MODES),
                        help="Comma list from: cv_only, dl_only, cascade.")
    parser.add_argument("--lbph-model", default=DEFAULT_LBPH_MODEL)
    parser.add_argument("--lbph-labels", default=DEFAULT_LBPH_LABELS)
    parser.add_argument("--sface-gallery", default=DEFAULT_SFACE_GALLERY)
    parser.add_argument("--sface-impostors", default=DEFAULT_SFACE_IMPOSTORS,
                        help="Optional impostor embeddings for FAR annotation (may be absent).")
    parser.add_argument("--thresholds-json", default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--no-face-policy", choices=["fallback", "strict"], default="fallback",
                        help="fallback: score undetected tiles without landmarks; "
                             "strict: count them as failures (deployed-system view).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Keep at 42 to reproduce the classical accuracy_ratio.py probes.")
    parser.add_argument("--segment-count", type=int, default=1,
                        help="Number of query identity segments for parallel sharded execution.")
    parser.add_argument("--segment-index", type=int, default=1,
                        help="1-based index of this query segment (1 <= index <= segment-count).")
    parser.add_argument("--select-one-per-person", action="store_true",
                        help="Randomly pick 1 image per identity folder (deterministic via --seed).")
    parser.add_argument("--reuse-engine-scores", action="store_true",
                        help="Cache each engine's score per probe so cv_only/cascade "
                             "don't re-run identical LBPH/SFace work (up to ~3x faster on large "
                             "galleries). Reported per-mode latencies become meaningless - keep "
                             "OFF for latency-bearing runs.")
    parser.add_argument("--output-json", default="outputs/benchmark/accuracy_ratio_hybrid.json")
    parser.add_argument("--output-md", default="reports/benchmark/accuracy_ratio_hybrid.md")
    parser.add_argument("--battery-csv", default="outputs/benchmark/accuracy_ratio_hybrid_probes.csv",
                        help="Per-probe pairing rows (cv/dl correctness + gate signal) for the "
                             "complementarity battery; empty string disables.")
    parser.add_argument("--mod-set", choices=["legacy", "dl41"], default="dl41",
                        help="legacy: original 12-family/41-variant set (bit-identical to old "
                             "reports). dl41 (default): the DL team's 41-named-modification "
                             "taxonomy (see src/benchmark/modifications.py DL41_MODIFICATIONS).")
    parser.add_argument("--headline-scope", choices=["all41", "exclude-canonical"],
                        default="all41",
                        help="all41 (default): the headline overall-AR/Rank-1 mean covers ALL "
                             "41 dl41 variants, matching the DL team's ar-table.py, which "
                             "averages every modification it maps. exclude-canonical: drop the "
                             "4 detector-canonical variants (rot_90/180/270, flip_lr) from the "
                             "headline mean. Either way those 4 also get their own breakout "
                             "section - the flag only controls whether they are ALSO averaged "
                             "into the headline. No effect under --mod-set legacy.")
    parser.add_argument("--split-manifest", default=None,
                        help="Path to a lsface-lfw-ident-split-v1 manifest (see "
                             "scripts/utils/make_lfw_identification_split.py). When given, "
                             "probes are the manifest's disjoint PROBE images (gallery/probe "
                             "identification protocol; report label = 'Accuracy Ratio'). "
                             "When omitted, falls back to the original --originals-dir / "
                             "--select-one-per-person same-image path (report label = "
                             "'Transform Sensitivity' - see docs/audits/STATE-08-01.md).")
    parser.add_argument("--limit-identities", type=int, default=0,
                        help="Debug/smoke-test only: process at most this many identities "
                             "(0 = all). Applied as a stable prefix after sorting/loading, "
                             "same effect whether sourced from --originals-dir or "
                             "--split-manifest.")
    parser.add_argument("--lbph-assume-cropped", choices=["true", "false"], default="false",
                        help="Passed through to detect_sample()/make_sample() for LBPH's "
                             "face_gray. 'true': pre-cropped tile datasets (e.g. "
                             "data/lasalle_db1_processed) where the whole frame IS the face "
                             "tile. 'false' (default): raw LFW frames, where LBPH must use "
                             "the detected YuNet face box, not the whole 250x250 frame. "
                             "SFace is unaffected either way (it always uses image_bgr + "
                             "yunet_row via alignCrop).")
    return parser.parse_args()


def select_originals(base_dir: str, select_one_per_person: bool = False, seed: int = 42) -> list[tuple[str, str]]:
    """(person, image_path) selection only — the RNG sequence is the probe-set
    contract, so enrollment (scripts/pipeline/run_lfw2_robustness.py) reuses this exact
    function to enroll the same clean images the benchmark will modify."""
    import random
    out: list[tuple[str, str]] = []
    rng = random.Random(seed)
    for person in sorted(os.listdir(base_dir)):
        pdir = os.path.join(base_dir, person)
        if not os.path.isdir(pdir):
            continue
        files = list_image_files(pdir)
        if not files:
            continue
        if select_one_per_person:
            files = [rng.choice(files)]
        for fn in files:
            out.append((person, os.path.join(pdir, fn)))
    return out


def load_originals(base_dir: str, select_one_per_person: bool = False, seed: int = 42) -> list[tuple[str, str, np.ndarray]]:
    """(person, filename, gray_tile) for every original image."""
    out: list[tuple[str, str, np.ndarray]] = []
    for person, path in select_originals(base_dir, select_one_per_person, seed):
        img = cv.imread(path)
        if img is None:
            continue
        out.append((person, os.path.basename(path), cv.cvtColor(img, cv.COLOR_BGR2GRAY)))
    return out


def load_split_manifest(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_probes_from_manifest(manifest: dict) -> list[tuple[str, str, np.ndarray]]:
    """(person, filename, BGR color tile) - one row per PROBE image, for every
    identity's manifest probe(s), each disjoint from its own gallery (enrolled)
    image. Reads the ``probes`` list (>= schema with --max-probes-per-identity
    support); falls back to the singular ``probe`` field for older manifests.
    A person with K probes contributes K independent identification-trial rows
    (same person label, different probe image) - the headline
    --max-probes-per-identity 1 manifest gives exactly one row per person, as
    before. Kept in COLOR (not pre-converted to gray): dl41's colour-only
    modifications (monochrome, color_8bit, rgb565) need it, and every other
    transform (legacy or dl41) works unchanged on either a gray or color tile."""
    root = manifest["dataset_root"]
    out: list[tuple[str, str, np.ndarray]] = []
    for person in sorted(manifest["identities"]):
        entry = manifest["identities"][person]
        rels = entry.get("probes")
        if rels is None:
            single = entry.get("probe")
            rels = [single] if single else []
        for rel in rels:
            img = cv.imread(os.path.join(root, rel))
            if img is None:
                continue
            out.append((person, os.path.basename(rel), img))
    return out


def load_gallery_from_manifest(manifest: dict) -> list[tuple[str, str]]:
    """(person, absolute gallery image path) for EVERY manifest identity
    (including singletons/demoted). Consumed by enrollment
    (run_lfw2_robustness.py.ensure_lfw2_enrollment), not by this module's own
    probe loop. ``gallery`` is normally a single relpath string (one enrolled
    image per identity); a multi-shot manifest (e.g.
    make_lasalle_clean10_split.py) may instead give a LIST of relpaths, in
    which case this yields one (person, path) tuple per image -- repeated
    person entries are the enrollment contract multi-shot LBPH already
    relies on (see enroll_lfw_multishot.py)."""
    root = manifest["dataset_root"]
    out: list[tuple[str, str]] = []
    for person in sorted(manifest["identities"]):
        entry = manifest["identities"][person]
        rel = entry.get("gallery")
        if not rel:
            continue
        rels = rel if isinstance(rel, list) else [rel]
        for r in rels:
            out.append((person, os.path.join(root, r)))
    return out


def to_bgr_gray(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(bgr, gray) from either representation - originals/probes may be a 2D
    gray tile (legacy same-image path) or a 3D BGR tile (manifest path, kept
    in color for the dl41 colour-only modifications)."""
    if image.ndim == 3:
        return image, cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    return cv.cvtColor(image, cv.COLOR_GRAY2BGR), image


def tile_sample(image_bgr: np.ndarray, image_gray: np.ndarray) -> FaceSample:
    """FaceSample for a pre-cropped tile when YuNet found nothing: the whole
    tile is the face, no landmarks (SFace falls back to a plain resize)."""
    h, w = image_gray.shape[:2]
    quality_gray = cv.resize(image_gray, (100, 100), interpolation=cv.INTER_AREA)
    return FaceSample(
        image_bgr=image_bgr,
        yunet_row=None,
        face_gray=image_gray,
        quality_gray=quality_gray,
        landmarks=None,
        face_px=int(min(h, w)),
        score=0.0,
    )


class _ScoreMemo:
    """Cache an engine's last score: modes score the SAME sample back to back, so
    holding one (sample, match) pair collapses duplicate LBPH/SFace work across
    cv_only/cascade. Keyed by object identity; the held reference keeps
    id() stable. Everything else proxies to the wrapped adapter."""

    def __init__(self, inner):
        self._inner = inner
        self._sample = None
        self._match = None

    def score(self, sample):
        if sample is not self._sample:
            self._sample = sample
            self._match = self._inner.score(sample)
        return self._match

    def __getattr__(self, name):
        return getattr(self._inner, name)


def build_recognizers(args: argparse.Namespace, modes: list[str]) -> dict[str, HybridRecognizer]:
    cfg = load_thresholds(_abs(args.thresholds_json))
    gate_thresholds = GateThresholds.from_dict(cfg.get("gate"))
    quality_thresholds = QualityThresholds.from_dict(cfg.get("quality"))
    lbph = LBPHAdapter(
        model_path=_abs(args.lbph_model),
        labels_path=_abs(args.lbph_labels),
        far_anchors=cfg.get("lbph_far_anchors"),
    )
    sface = None
    if any(m != "cv_only" for m in modes):
        impostors = _abs(args.sface_impostors) if args.sface_impostors else None
        if impostors and not Path(impostors).exists():
            impostors = None
        sface = SFaceAdapter(
            gallery_path=_abs(args.sface_gallery),
            impostors_path=impostors,
        )
    if getattr(args, "reuse_engine_scores", False):
        lbph = _ScoreMemo(lbph)
        if sface is not None:
            sface = _ScoreMemo(sface)
    return {
        mode: HybridRecognizer(
            lbph=lbph,
            sface=sface,
            gate_thresholds=gate_thresholds,
            quality_thresholds=quality_thresholds,
            mode=mode,
        )
        for mode in modes
    }


def score_probe(
    recognizers: dict[str, HybridRecognizer],
    sample: FaceSample | None,
    person: str,
) -> dict[str, dict]:
    """Run every mode on one probe; ``sample=None`` means strict no-face fail."""
    out: dict[str, dict] = {}
    for mode, hybrid in recognizers.items():
        if sample is None:
            out[mode] = {"matched": False, "rank1_matched": False, "escalated": False, "latency_ms": 0.0}
            continue
        t0 = time.perf_counter()
        decision = hybrid.predict(sample)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        rec = {
            # matched: correct identity AND clears the mode's accept threshold
            # (TPIR @ threshold). rank1_matched: correct identity as the
            # deciding engine's nearest gallery entry, threshold-free -
            # HybridDecision.name_raw is the argmin/argmax label before any
            # tau_accept/tau_reject/genuine-rule gating (recognizer.py). These
            # are DIFFERENT questions: a mode can rank the right person first
            # and still reject them for sitting outside the accept band.
            "matched": decision.name == person,
            "rank1_matched": decision.name_raw == person,
            "escalated": bool(decision.escalated),
            "latency_ms": latency_ms,
        }
        if mode in ("cv_only", "cascade"):
            # The pre-escalation LBPH signal (identical across modes for the
            # same sample) - the raw material of the gate-competence AUC.
            rec["lbph_distance"] = float(decision.lbph_distance)
            rec["lbph_margin"] = float(decision.lbph_margin)
            rec["reason"] = decision.reason
        out[mode] = rec
    return out


# --------------------------------------------------------------------------- #
# Complementarity battery: recovery rate, McNemar, gate competence
# (identification axis - a different 2x2 from the false-accept table the
#  joint independence sweep reports; see docs/presentation/
#  complementarity_battery/WHY_AND_HOW.md for the design)
# --------------------------------------------------------------------------- #
def battery_row(mod_name: str, level, person: str, fname: str,
                scores: dict[str, dict], no_face: bool) -> dict:
    sig = scores.get("cv_only") or scores.get("cascade") or {}
    cas = scores.get("cascade")
    return {
        "modification": mod_name,
        "level": level,
        "person": person,
        "file": fname,
        "no_face": bool(no_face),
        "cv_correct": bool(scores["cv_only"]["matched"]),
        "dl_correct": bool(scores["dl_only"]["matched"]),
        "escalated": (bool(cas["escalated"]) if cas else None),
        "gate_reason": (cas.get("reason") if cas else None),
        "lbph_distance": sig.get("lbph_distance"),
        "lbph_margin": sig.get("lbph_margin"),
    }


def _pairing_stats(rows: list[dict]) -> dict:
    """w/x/y/z identification table + recovery, both-fail, McNemar."""
    n = len(rows)
    w = sum(1 for r in rows if r["cv_correct"] and r["dl_correct"])
    x = sum(1 for r in rows if r["cv_correct"] and not r["dl_correct"])
    y = sum(1 for r in rows if not r["cv_correct"] and r["dl_correct"])
    z = n - w - x - y
    lbph_wrong = y + z
    return {
        "probes": n,
        "table": {"both_right": w, "cv_only_right": x, "dl_only_right": y, "both_wrong": z},
        "recovery_rate_ci95": wilson_interval_percent(y, lbph_wrong) if lbph_wrong else None,
        "both_fail_ci95": wilson_interval_percent(z, n) if n else None,
        "mcnemar": mcnemar_test(x, y),
    }


def _gate_stats(rows: list[dict]) -> dict | None:
    """Does the gate signal predict LBPH failure? AUC + deployed-rule confusion.

    Probes with no LBPH signal (strict-policy no-face rows) never reached the
    gate, so they are excluded and counted separately.
    """
    scored = [r for r in rows if r.get("escalated") is not None
              and r.get("lbph_distance") is not None]
    if not scored:
        return None
    labels = [0 if r["cv_correct"] else 1 for r in scored]  # 1 = LBPH wrong
    tp = sum(1 for r in scored if r["escalated"] and not r["cv_correct"])
    fp = sum(1 for r in scored if r["escalated"] and r["cv_correct"])
    fn = sum(1 for r in scored if not r["escalated"] and not r["cv_correct"])
    tn = sum(1 for r in scored if not r["escalated"] and r["cv_correct"])
    wrong, right, esc = tp + fn, fp + tn, tp + fp
    reasons: dict[str, int] = {}
    for r in scored:
        if r["escalated"] and not r["cv_correct"]:
            key = (r.get("gate_reason") or "?").split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
    return {
        "probes": len(scored),
        "excluded_no_signal": len(rows) - len(scored),
        "auc_lbph_distance": rank_auc(labels, [r["lbph_distance"] for r in scored]),
        "auc_lbph_margin": rank_auc(labels, [-r["lbph_margin"] for r in scored]),
        "escalate_vs_lbph_wrong": {
            "tpr_recall_of_wrong": (tp / wrong) if wrong else None,
            "fpr_on_right": (fp / right) if right else None,
            "precision": (tp / esc) if esc else None,
            "escalated": esc,
            "lbph_wrong": wrong,
        },
        "escalation_reasons_on_wrong": reasons,
    }


def compute_battery(rows: list[dict], modes: list[str]) -> dict:
    modified = [r for r in rows if r["modification"] != "clean"]
    clean = [r for r in rows if r["modification"] == "clean"]
    per_mod = []
    for mod_name in dict.fromkeys(r["modification"] for r in modified):
        mod_rows = [r for r in modified if r["modification"] == mod_name]
        stats = _pairing_stats(mod_rows)
        scored = [r for r in mod_rows if r.get("lbph_distance") is not None]
        stats["auc_lbph_distance"] = rank_auc(
            [0 if r["cv_correct"] else 1 for r in scored],
            [r["lbph_distance"] for r in scored],
        ) if scored else None
        per_mod.append({"modification": mod_name, **stats})
    battery = {
        "note": "Identification-axis pairing (correct identity within threshold), "
                "NOT the false-accept table of the joint independence sweep. "
                "cv_correct = cv_only accept; dl_correct = dl_only accept. "
                "recovery = P(SFace right | LBPH wrong); both_fail = the ceiling "
                "no fusion of these engines can beat; McNemar tests the "
                "discordant cells (x = cv-only-right vs y = dl-only-right).",
        "clean": _pairing_stats(clean) if clean else None,
        "overall_modified": _pairing_stats(modified),
        "per_modification": per_mod,
    }
    if "cascade" in modes:
        battery["gate"] = {
            "modified_only": _gate_stats(modified),
            "all_probes": _gate_stats(rows),
        }
    return battery


def write_battery_csv(rows: list[dict], path: Path) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["modification", "level", "person", "file", "no_face", "cv_correct",
              "dl_correct", "escalated", "gate_reason", "lbph_distance", "lbph_margin"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r.get(k) for k in fields} for r in rows)


def main() -> int:
    args = parse_args()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in MODES:
            raise ValueError(f"Unknown mode {m!r}. Valid: {MODES}")

    modifications_list, variant_count = get_modification_set(args.mod_set)

    split_manifest = None
    if args.split_manifest:
        split_manifest = load_split_manifest(_abs(args.split_manifest))
        originals = load_probes_from_manifest(split_manifest)
        protocol = "identification_disjoint"
        protocol_label = "Accuracy Ratio"
        if not originals:
            raise RuntimeError(
                f"No probe images found in split manifest {args.split_manifest}. "
                "Expected an lsface-lfw-ident-split-v1 manifest with >=1 identity "
                "carrying a non-null 'probe' entry."
            )
    else:
        originals = load_originals(_abs(args.originals_dir), select_one_per_person=args.select_one_per_person, seed=args.seed)
        protocol = "transform_sensitivity"
        protocol_label = "Transform Sensitivity"
        if not originals:
            raise RuntimeError(
                f"No original images found under {args.originals_dir}. "
                "Expected identity folders of pre-cropped tiles (data/split_lasalle/test)."
            )

    if args.limit_identities:
        if split_manifest is not None:
            # Smoke runs enroll only the FIRST N manifest gallery identities
            # (run_lfw2_robustness.ensure_lfw2_enrollment truncates
            # load_gallery_from_manifest(...)[:N], both in sorted-person
            # order). Probes must be intersected with that same enrolled set,
            # not independently truncated to N rows: probe-bearing identities
            # are a 1,680-of-5,749 subset scattered through the gallery
            # ordering, so `originals[:N]` would hand most probes an identity
            # that was never enrolled and score them wrong by construction -
            # a guaranteed-miss floor that reads as a real accuracy number.
            enrolled = {p for p, _ in load_gallery_from_manifest(split_manifest)[:args.limit_identities]}
            originals = [row for row in originals if row[0] in enrolled]
            print(f"[INFO] --limit-identities {args.limit_identities}: {len(enrolled)} enrolled "
                  f"gallery identities -> {len(originals)} probes from that subset.")
        else:
            originals = originals[:args.limit_identities]
            print(f"[INFO] --limit-identities {args.limit_identities}: processing {len(originals)} identities.")

    total_unsegmented_originals = len(originals)
    if args.segment_count > 1:
        from src.independence_report import segment_bounds
        start, end = segment_bounds(total_unsegmented_originals, args.segment_count, args.segment_index)
        originals = originals[start:end]
        print(f"[INFO] Segment {args.segment_index}/{args.segment_count}: processing originals [{start}:{end}] out of {total_unsegmented_originals}")
        if not originals:
            # segment_bounds sizes segments as ceil(n/k), so the first k-1 can
            # already cover all n and leave this one empty. Every downstream
            # rate divides by len(originals); fail with the cause rather than
            # a bare ZeroDivisionError several hundred lines later.
            raise RuntimeError(
                f"Segment {args.segment_index}/{args.segment_count} is empty: "
                f"[{start}:{end}] of {total_unsegmented_originals} originals. "
                f"Use --segment-count <= {total_unsegmented_originals} such that "
                "ceil(n/k)*(k-1) < n (scripts/pipeline/run_lfw2_robustness.py "
                "computes this automatically)."
            )
    print(f"[INFO] protocol={protocol} ({protocol_label}) mod_set={args.mod_set} "
          f"originals={len(originals)} (unsegmented total={total_unsegmented_originals}) -> modified probes per mode = "
          f"{len(originals)} x {variant_count} = {len(originals) * variant_count}")

    recognizers = build_recognizers(args, modes)
    detector = create_face_detector("yunet")
    lbph_assume_cropped = args.lbph_assume_cropped == "true"

    def probe(image: np.ndarray, person: str) -> tuple[dict[str, dict], bool]:
        image_bgr, image_gray = to_bgr_gray(image)
        sample = detect_sample(
            detector, image_bgr=image_bgr, image_gray=image_gray,
            assume_cropped=lbph_assume_cropped,
        )
        no_face = sample is None
        if no_face and args.no_face_policy == "fallback":
            sample = tile_sample(image_bgr, image_gray)
        return score_probe(recognizers, sample, person), no_face

    battery_enabled = "cv_only" in modes and "dl_only" in modes
    battery_rows: list[dict] = []
    if not battery_enabled:
        print("[INFO] Complementarity battery skipped (needs cv_only AND dl_only in --modes).")

    # Clean (unmodified) acceptance per mode - the held-out baseline. Under the
    # disjoint protocol these are genuinely different images from the gallery
    # (Rank-1 identification, not "does the same image match itself"); under
    # the legacy same-image path this is the original degenerate baseline
    # (labelled transform_sensitivity below, never "Accuracy Ratio").
    clean_matched = {m: 0 for m in modes}
    clean_rank1 = {m: 0 for m in modes}
    clean_no_face = 0
    for person, fname, gray in originals:
        scores, no_face = probe(gray, person)
        clean_no_face += no_face
        for m in modes:
            clean_matched[m] += scores[m]["matched"]
            clean_rank1[m] += scores[m]["rank1_matched"]
        if battery_enabled:
            battery_rows.append(battery_row("clean", None, person, fname, scores, no_face))

    per_mod: list[dict] = []
    latencies: dict[str, list[float]] = {m: [] for m in modes}
    for mod_name, fn, levels in modifications_list:
        level_rows = []
        for level in levels:
            matched = {m: 0 for m in modes}
            rank1_matched = {m: 0 for m in modes}
            escalated = 0
            no_face_count = 0
            for person, fname, gray in originals:
                rng = stable_rng(args.seed, person, fname, mod_name, level)
                modified = fn(gray, level, rng)
                scores, no_face = probe(modified, person)
                no_face_count += no_face
                for m in modes:
                    matched[m] += scores[m]["matched"]
                    rank1_matched[m] += scores[m]["rank1_matched"]
                    latencies[m].append(scores[m]["latency_ms"])
                if "cascade" in scores:
                    escalated += scores["cascade"]["escalated"]
                if battery_enabled:
                    battery_rows.append(
                        battery_row(mod_name, level, person, fname, scores, no_face))
            level_rows.append({
                "level": level,
                "modified_total": len(originals),
                "no_face": no_face_count,
                "matched": matched,
                "rank1_matched": rank1_matched,
                "escalated": escalated if "cascade" in modes else None,
                # ar_percent: TPIR @ threshold (correct identity AND clears the
                # mode's accept rule). rank1_percent: threshold-free - did the
                # deciding engine's argmin/argmax gallery pick land on the
                # right identity at all? See score_probe()'s rank1_matched.
                "ar_percent": {m: 100.0 * matched[m] / len(originals) for m in modes},
                "rank1_percent": {m: 100.0 * rank1_matched[m] / len(originals) for m in modes},
                "cascade_escalation_percent": (
                    100.0 * escalated / len(originals) if "cascade" in modes else None
                ),
            })
        mod_ar = {
            m: sum(r["ar_percent"][m] for r in level_rows) / len(level_rows) for m in modes
        }
        mod_rank1 = {
            m: sum(r["rank1_percent"][m] for r in level_rows) / len(level_rows) for m in modes
        }
        # Pooled binomial view of the same modification (matched over all its
        # level probes), so each AR carries a Wilson 95% CI.
        mod_probes = len(level_rows) * len(originals)
        mod_ar_ci = {
            m: wilson_interval_percent(
                sum(r["matched"][m] for r in level_rows), mod_probes
            )
            for m in modes
        }
        row = {
            "modification": mod_name,
            "ar_percent": mod_ar,
            "ar_pooled_ci95": mod_ar_ci,
            "rank1_percent": mod_rank1,
            "levels": level_rows,
        }
        if "cascade" in modes:
            row["cascade_escalation_percent"] = sum(
                r["cascade_escalation_percent"] for r in level_rows
            ) / len(level_rows)
        if "cv_only" in modes and "dl_only" in modes:
            delta = mod_ar["dl_only"] - mod_ar["cv_only"]
            row["dl_minus_cv_points"] = delta
            row["winner"] = (
                "tie" if abs(delta) <= AR_TIE_TOLERANCE
                else ("dl_stronger" if delta > 0 else "cv_stronger")
            )
            if "cascade" in modes:
                row["cascade_vs_best_points"] = (
                    mod_ar["cascade"] - max(mod_ar["cv_only"], mod_ar["dl_only"])
                )
        per_mod.append(row)
        summary = "  ".join(f"{m}={mod_ar[m]:6.2f}%" for m in modes)
        canon_tag = " [detector-canonical]" if mod_name in DL41_DETECTOR_CANONICAL else ""
        print(f"  {mod_name:<16} {summary}{canon_tag}")

    # Detector-canonical mods (rot_90/180/270, flip_lr under dl41) ALWAYS get
    # their own breakout section, because "failed on an upside-down face" and
    # "failed on a blurred face" are different claims and averaging them hides
    # that. Whether they are ALSO counted in the headline mean is
    # --headline-scope: default all41 keeps the headline over all 41 variants
    # so the number is directly comparable to the DL team's ar-table.py, which
    # averages every modification in MODIFICATION_MAPS. See
    # docs/audits/STATE-08-01.md.
    is_canonical = (lambda name: name in DL41_DETECTOR_CANONICAL) if args.mod_set == "dl41" else (lambda name: False)
    canonical_rows = [r for r in per_mod if is_canonical(r["modification"])]
    headline_rows = (
        list(per_mod) if args.headline_scope == "all41"
        else [r for r in per_mod if not is_canonical(r["modification"])]
    )

    # Retention per modification/mode: AR_mod / AR_clean, defined against the
    # THRESHOLD-GATED number (ar_percent / clean_acceptance_percent) - this
    # separates "this engine is weak on this dataset in general" from "this
    # modification did damage" (both explicit headline AR and the
    # transform_sensitivity label need this to be interpretable at all).
    clean_ar_percent = {m: 100.0 * clean_matched[m] / len(originals) for m in modes}
    clean_rank1_percent = {m: 100.0 * clean_rank1[m] / len(originals) for m in modes}
    for row in per_mod:
        row["retention"] = {
            m: (row["ar_percent"][m] / clean_ar_percent[m]) if clean_ar_percent[m] > 0 else None
            for m in modes
        }

    overall = {
        m: sum(row["ar_percent"][m] for row in headline_rows) / len(headline_rows) for m in modes
    } if headline_rows else {m: 0.0 for m in modes}
    overall_rank1 = {
        m: sum(row["rank1_percent"][m] for row in headline_rows) / len(headline_rows) for m in modes
    } if headline_rows else {m: 0.0 for m in modes}
    detector_canonical_overall = {
        m: sum(row["ar_percent"][m] for row in canonical_rows) / len(canonical_rows) for m in modes
    } if canonical_rows else None
    detector_canonical_rank1_overall = {
        m: sum(row["rank1_percent"][m] for row in canonical_rows) / len(canonical_rows) for m in modes
    } if canonical_rows else None
    # Pooled over ALL headline-variant probes (canonical mods excluded): one
    # binomial per mode -> Wilson CI.
    total_probes = len(originals) * sum(len(r["levels"]) for r in headline_rows)
    overall_ci = {
        m: wilson_interval_percent(
            sum(r["matched"][m] for row in headline_rows for r in row["levels"]),
            total_probes,
        )
        for m in modes
    }
    overall_rank1_ci = {
        m: wilson_interval_percent(
            sum(r["rank1_matched"][m] for row in headline_rows for r in row["levels"]),
            total_probes,
        )
        for m in modes
    }
    payload = {
        "protocol": protocol,
        "protocol_label": protocol_label,
        "mod_set": args.mod_set,
        "split_manifest": args.split_manifest,
        "split_manifest_triples_sha256": (split_manifest or {}).get("triples_sha256"),
        "originals_dir": args.originals_dir if not split_manifest else None,
        "originals": len(originals),
        "total_unsegmented_originals": total_unsegmented_originals,
        "segment_count": args.segment_count,
        "segment_index": args.segment_index,
        "variant_count": variant_count,
        "headline_scope": args.headline_scope,
        "headline_variant_count": len(headline_rows),
        "headline_modifications": [r["modification"] for r in headline_rows],
        "detector_canonical_variant_count": len(canonical_rows),
        "modified_probes_per_mode": total_probes,
        "seed": args.seed,
        "no_face_policy": args.no_face_policy,
        "lbph_assume_cropped": lbph_assume_cropped,
        "clean_no_face": clean_no_face,
        "clean_matched": clean_matched,
        "clean_rank1_matched": clean_rank1,
        # clean_acceptance_percent: TPIR @ threshold on the undamaged probe
        # (correct identity AND clears the mode's accept rule).
        # clean_rank1_percent: threshold-free Rank-1 identification rate on
        # the same undamaged probe (did the deciding engine's argmin/argmax
        # gallery pick land on the right identity at all). These can differ a
        # lot: a mode can rank the right person first and still reject them.
        "clean_acceptance_percent": clean_ar_percent,
        "clean_acceptance_ci95": {
            m: wilson_interval_percent(clean_matched[m], len(originals)) for m in modes
        },
        "clean_rank1_percent": clean_rank1_percent,
        "clean_rank1_ci95": {
            m: wilson_interval_percent(clean_rank1[m], len(originals)) for m in modes
        },
        "overall_ar_percent": overall,
        "overall_ar_pooled_ci95": overall_ci,
        "overall_rank1_percent": overall_rank1,
        "overall_rank1_pooled_ci95": overall_rank1_ci,
        "detector_canonical_ar_percent": detector_canonical_overall,
        "detector_canonical_rank1_percent": detector_canonical_rank1_overall,
        "detector_canonical_modifications": [r["modification"] for r in canonical_rows],
        "mean_latency_ms": {
            m: (float(np.mean(latencies[m])) if latencies[m] else 0.0) for m in modes
        },
        "latency_ms_percentiles": {
            m: (
                {
                    "median": float(np.percentile(latencies[m], 50)),
                    "p95": float(np.percentile(latencies[m], 95)),
                }
                if latencies[m] else {"median": 0.0, "p95": 0.0}
            )
            for m in modes
        },
        "modifications": per_mod,
    }
    if "cv_only" in modes and "dl_only" in modes:
        payload["complementarity"] = {
            "cv_stronger": [r["modification"] for r in per_mod if r.get("winner") == "cv_stronger"],
            "dl_stronger": [r["modification"] for r in per_mod if r.get("winner") == "dl_stronger"],
            "tie": [r["modification"] for r in per_mod if r.get("winner") == "tie"],
            "tie_tolerance_points": AR_TIE_TOLERANCE,
        }
        if "cascade" in modes:
            payload["complementarity"]["cascade_within_2pts_of_best"] = sum(
                1 for r in per_mod if r["cascade_vs_best_points"] >= -AR_TIE_TOLERANCE
            )
    if battery_enabled:
        payload["complementarity_battery"] = compute_battery(battery_rows, modes)
        if args.battery_csv:
            csv_path = Path(_abs(args.battery_csv))
            write_battery_csv(battery_rows, csv_path)
            print(f"[OK] Wrote {csv_path}")

    out_json = Path(_abs(args.output_json))
    out_md = Path(_abs(args.output_md))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(to_markdown(payload, modes), encoding="utf-8")

    print("\n[RESULT] overall AR: " + "  ".join(f"{m}={overall[m]:.2f}%" for m in modes))
    comp = payload.get("complementarity", {})
    if "cv_stronger" in comp:
        print(f"[COMPLEMENTARITY] cv_stronger={comp['cv_stronger']} "
              f"dl_stronger={comp['dl_stronger']} tie={len(comp['tie'])} mods")
    bat = payload.get("complementarity_battery")
    if bat:
        om = bat["overall_modified"]
        rec = om["recovery_rate_ci95"]
        bf = om["both_fail_ci95"]
        mc = om["mcnemar"]
        print(f"[BATTERY] modified probes={om['probes']} table w/x/y/z="
              f"{om['table']['both_right']}/{om['table']['cv_only_right']}/"
              f"{om['table']['dl_only_right']}/{om['table']['both_wrong']}")
        if rec:
            print(f"[BATTERY] recovery P(SFace ok | LBPH wrong) = {rec['percent']:.2f}% "
                  f"[{rec['ci95_low_percent']:.2f}-{rec['ci95_high_percent']:.2f}] "
                  f"({rec['count']}/{rec['trials']}); both-fail = {bf['percent']:.2f}%")
        if not mc["degenerate"]:
            print(f"[BATTERY] McNemar x={mc['b']} y={mc['c']} p_exact={mc['p_exact']:.3g}")
        gate = (bat.get("gate") or {}).get("modified_only")
        if gate:
            evw = gate["escalate_vs_lbph_wrong"]
            print(f"[BATTERY] gate AUC(d1)={_fmt_opt(gate['auc_lbph_distance'])} "
                  f"AUC(margin)={_fmt_opt(gate['auc_lbph_margin'])} | escalate-on-wrong "
                  f"TPR={_fmt_opt(evw['tpr_recall_of_wrong'])} FPR={_fmt_opt(evw['fpr_on_right'])}")
    print(f"[OK] Wrote {out_json}")
    print(f"[OK] Wrote {out_md}")
    return 0


def _mod_row_line(r: dict, modes: list[str], extra_cols: str) -> str:
    cells = " | ".join(f"{r['ar_percent'][m]:.1f}%" for m in modes)
    ret = " / ".join(
        f"{r['retention'][m]:.2f}" if r.get('retention', {}).get(m) is not None else "n/a"
        for m in modes
    )
    row = f"| {r['modification']} | {cells} | {ret} |"
    if extra_cols:
        row = row[:-2] + f" | {r.get('winner', '')} |"
    if "cascade" in modes:
        row = row[:-2] + f" | {r.get('cascade_escalation_percent', 0.0):.0f}% |"
    return row


def _rank1_row_line(r: dict, modes: list[str]) -> str:
    cells = " | ".join(f"{r['rank1_percent'][m]:.1f}%" for m in modes)
    return f"| {r['modification']} | {cells} |"


def to_markdown(payload: dict, modes: list[str]) -> str:
    protocol_label = payload.get("protocol_label", "Accuracy Ratio")
    protocol = payload.get("protocol", "identification_disjoint")
    mod_set = payload.get("mod_set", "legacy")
    split_manifest = payload.get("split_manifest")
    headline_scope = payload.get("headline_scope", "all41")
    headline_names = payload.get("headline_modifications")
    if headline_names is None:  # pre-headline_scope payloads
        headline_names = [r["modification"] for r in payload["modifications"]
                          if r["modification"] not in (payload.get("detector_canonical_modifications") or [])]
    headline_rows = [r for r in payload["modifications"] if r["modification"] in set(headline_names)]
    canonical_rows = [r for r in payload["modifications"]
                       if r["modification"] in (payload.get("detector_canonical_modifications") or [])]
    canonical_in_headline = headline_scope == "all41" and bool(canonical_rows)

    lines = [
        f"# {protocol_label} - {mod_set} modification set: CV (LBPH) vs DL (SFace) vs hybrid cascade",
        "",
        f"Protocol: `{protocol}`" + (
            f" | split manifest: `{split_manifest}` "
            f"(triples sha256 `{payload.get('split_manifest_triples_sha256')}`)"
            if split_manifest else
            " (same-image path - enrollment and probing share the same seeded image; "
            "see docs/audits/STATE-08-01.md. This is NOT recognition accuracy.)"
        ),
        "",
        f"Originals: `{payload.get('originals_dir') or split_manifest}`"
        + (" (manifest probes)" if split_manifest else "")
        + f" ({payload['originals']} tiles) | "
        f"{payload['variant_count']} variants/original "
        + (f"(all {len(headline_rows)} in the headline mean; "
           f"{len(canonical_rows)} of them are detector-canonical and are ALSO "
           f"broken out separately below)"
           if canonical_in_headline else
           f"({len(headline_rows)} headline + {len(canonical_rows)} detector-canonical)")
        + " | "
        f"seed={payload['seed']} | no-face policy: `{payload['no_face_policy']}`.",
        "",
        "AR = TPIR @ threshold (correct identity AND clears the mode's accept "
        "rule). Rank-1 = threshold-free (did the deciding engine's nearest "
        "gallery pick land on the right identity at all, regardless of "
        "accept/reject). These answer different questions: a mode can rank "
        "the right person first and still reject them for sitting outside "
        "its accept band - see docs/audits/STATE-08-01.md. AR per "
        "modification = mean over its levels; overall = mean over "
        + ("ALL 41 modifications, matching the DL team's ar-table.py. The 4 "
           "detector-canonical ones (rot_90/180/270, flip_lr) are included here "
           "AND broken out separately below, since a recognizer failing on an "
           "upside-down face is expected behaviour and reads differently from a "
           "failure on blur or noise."
           if canonical_in_headline else
           "HEADLINE modifications only (detector-canonical rot_90/180/270/flip_lr "
           "excluded - see their own section below).")
        + " Retention = AR_mod / AR_clean (threshold-gated, "
        "clean = the held-out baseline row, undegraded probes).",
        "",
        "| Metric | " + " | ".join(modes) + " |",
        "|---|" + "---:|" * len(modes),
        "| Clean held-out baseline - Rank-1 (threshold-free) | " + " | ".join(
            f"{payload['clean_rank1_percent'][m]:.2f}%" for m in modes) + " |",
        "| Clean held-out baseline - TPIR @ threshold | " + " | ".join(
            f"{payload['clean_acceptance_percent'][m]:.2f}%" for m in modes) + " |",
        f"| **Overall AR ({len(headline_rows)} mods, TPIR @ threshold)** | " + " | ".join(
            f"**{payload['overall_ar_percent'][m]:.2f}%**" for m in modes) + " |",
        "| Pooled AR [95% CI] | " + " | ".join(
            "{percent:.2f}% [{ci95_low_percent:.2f}-{ci95_high_percent:.2f}]".format(
                **payload["overall_ar_pooled_ci95"][m]) for m in modes) + " |",
        f"| Overall Rank-1 ({len(headline_rows)} mods, threshold-free) | " + " | ".join(
            f"{payload['overall_rank1_percent'][m]:.2f}%" for m in modes) + " |",
        "| Pooled Rank-1 [95% CI] | " + " | ".join(
            "{percent:.2f}% [{ci95_low_percent:.2f}-{ci95_high_percent:.2f}]".format(
                **payload["overall_rank1_pooled_ci95"][m]) for m in modes) + " |",
        "| Mean latency | " + " | ".join(
            f"{payload['mean_latency_ms'][m]:.2f} ms" for m in modes) + " |",
        "| Latency median / p95 | " + " | ".join(
            "{median:.2f} / {p95:.2f} ms".format(
                **payload["latency_ms_percentiles"][m]) for m in modes) + " |",
        "",
        f"## Per modification ({len(headline_rows)} mods) - AR (TPIR @ threshold)",
        "",
    ]
    header = "| Modification | " + " | ".join(modes) + " | retention |"
    sep = "|---|" + "---:|" * len(modes) + "---:|"
    extra_cols = ""
    if "cv_only" in modes and "dl_only" in modes:
        header = header[:-2] + " | winner |"
        sep += "---|"
        extra_cols = "winner"
    if "cascade" in modes:
        header = header[:-2] + " | escalation |"
        sep += "---:|"
    lines += [header, sep]
    for r in headline_rows:
        lines.append(_mod_row_line(r, modes, extra_cols))
    lines.append("")

    rank1_header = "| Modification | " + " | ".join(modes) + " |"
    rank1_sep = "|---|" + "---:|" * len(modes)
    lines += [
        f"## Per modification ({len(headline_rows)} mods) - Rank-1 identification (threshold-free)",
        "",
        rank1_header, rank1_sep,
    ]
    for r in headline_rows:
        lines.append(_rank1_row_line(r, modes))
    lines.append("")

    if canonical_rows:
        lines += [
            "## Detector-canonical (rot_90/180/270, flip_lr)"
            + (" - INCLUDED in the headline mean above, broken out here as well"
               if canonical_in_headline else
               " - NOT averaged into the headline overall-AR mean"),
            "",
            "A recognizer failing on an upside-down face is expected behaviour, and flip "
            "is near-free for a roughly-symmetric embedding, so these four read "
            "differently from the damage-style modifications."
            + (" They are counted in the headline mean (--headline-scope all41, the "
               "default, matching the DL team's ar-table.py) and repeated here so the "
               "headline can be decomposed. Re-run with --headline-scope "
               "exclude-canonical for the headline without them."
               if canonical_in_headline else
               " Folding them in would distort the headline number in both "
               "directions, so they are excluded (--headline-scope exclude-canonical)."),
            "",
        ]
        dc = payload.get("detector_canonical_ar_percent")
        dc1 = payload.get("detector_canonical_rank1_percent")
        if dc:
            lines += [
                "| Metric | " + " | ".join(modes) + " |",
                "|---|" + "---:|" * len(modes),
                "| Detector-canonical AR (TPIR @ threshold) | " + " | ".join(f"**{dc[m]:.2f}%**" for m in modes) + " |",
            ]
            if dc1:
                lines.append(
                    "| Detector-canonical Rank-1 (threshold-free) | "
                    + " | ".join(f"**{dc1[m]:.2f}%**" for m in modes) + " |"
                )
            lines.append("")
        lines += [header, sep]
        for r in canonical_rows:
            lines.append(_mod_row_line(r, modes, extra_cols))
        lines += ["", rank1_header, rank1_sep]
        for r in canonical_rows:
            lines.append(_rank1_row_line(r, modes))
        lines.append("")

    comp = payload.get("complementarity")
    if comp:
        lines += ["## Complementarity summary", ""]
        if "cv_stronger" in comp:
            tol = comp["tie_tolerance_points"]
            lines += [
                f"- CV stronger (> {tol:.0f} pts): "
                + (", ".join(comp["cv_stronger"]) or "none"),
                f"- DL stronger (> {tol:.0f} pts): "
                + (", ".join(comp["dl_stronger"]) or "none"),
                f"- Ties: {len(comp['tie'])} modifications",
            ]
            if "cascade_within_2pts_of_best" in comp:
                lines.append(
                    f"- Cascade within {tol:.0f} pts of the better "
                    f"engine on {comp['cascade_within_2pts_of_best']} / "
                    f"{len(payload['modifications'])} modifications"
                )
        lines.append("")

    battery = payload.get("complementarity_battery")
    if battery:
        lines += battery_markdown(battery)
    return "\n".join(lines)


def _fmt_pct_ci(entry: dict | None) -> str:
    if not entry:
        return "n/a"
    return (f"{entry['percent']:.1f}% [{entry['ci95_low_percent']:.1f}"
            f"-{entry['ci95_high_percent']:.1f}]")


def _fmt_p(p: float | None) -> str:
    if p is None:
        return "n/a"
    return f"{p:.2g}" if p >= 1e-4 else f"{p:.1e}"


def battery_markdown(battery: dict) -> list[str]:
    om = battery["overall_modified"]
    t = om["table"]
    mc = om["mcnemar"]
    lines = [
        "## Complementarity battery (identification axis)",
        "",
        "Per-probe pairing of cv_only vs dl_only correctness on the SAME probes "
        "(w = both right, x = only LBPH right, y = only SFace right, z = both wrong). "
        "recovery = y/(y+z) - the share of LBPH's misses SFace rescues; "
        "both-fail = z/N - the ceiling no fusion beats; McNemar tests x vs y.",
        "",
        f"- Modified probes: {om['probes']} | w/x/y/z = "
        f"{t['both_right']}/{t['cv_only_right']}/{t['dl_only_right']}/{t['both_wrong']}",
        f"- **Recovery rate** = {_fmt_pct_ci(om['recovery_rate_ci95'])} "
        f"({om['recovery_rate_ci95']['count']}/{om['recovery_rate_ci95']['trials']})"
        if om["recovery_rate_ci95"] else "- Recovery rate: n/a (LBPH never wrong)",
        f"- **Both-fail ceiling** = {_fmt_pct_ci(om['both_fail_ci95'])}",
        f"- **McNemar** (x={mc['b']} vs y={mc['c']}): p_exact = {_fmt_p(mc['p_exact'])}, "
        f"chi2_cc = {mc['statistic']:.1f}" if not mc["degenerate"]
        else "- McNemar: degenerate (no discordant probes)",
    ]
    clean = battery.get("clean")
    if clean:
        ct = clean["table"]
        lines.append(
            f"- Clean probes ({clean['probes']}): w/x/y/z = "
            f"{ct['both_right']}/{ct['cv_only_right']}/{ct['dl_only_right']}/{ct['both_wrong']}")
    lines += [
        "",
        "| Modification | LBPH wrong | SFace rescues | Recovery | Both-fail | McNemar p | AUC(d1) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in battery["per_modification"]:
        rt = row["table"]
        wrong = rt["dl_only_right"] + rt["both_wrong"]
        rec = row["recovery_rate_ci95"]
        auc = row.get("auc_lbph_distance")
        lines.append(
            f"| {row['modification']} | {wrong} | {rt['dl_only_right']} | "
            f"{(rec['percent'] if rec else float('nan')):.0f}% | "
            f"{row['both_fail_ci95']['percent']:.1f}% | "
            f"{_fmt_p(row['mcnemar']['p_exact'])} | "
            + (f"{auc:.2f} |" if auc is not None else "n/a |")
        )
    gate = battery.get("gate") or {}
    gm = gate.get("modified_only")
    if gm:
        evw = gm["escalate_vs_lbph_wrong"]
        auc_d_str = f"**{gm['auc_lbph_distance']:.3f}**" if gm.get("auc_lbph_distance") is not None else "**n/a**"
        auc_m_str = f"{gm['auc_lbph_margin']:.3f}" if gm.get("auc_lbph_margin") is not None else "n/a"
        lines += [
            "",
            "### Gate competence (does LBPH know when it's wrong?)",
            "",
            f"- ROC AUC, LBPH distance -> 'LBPH wrong' (modified probes): "
            f"{auc_d_str}; margin signal: {auc_m_str}",
            f"- Deployed gate vs 'LBPH wrong': escalates {evw['escalated']} probes; "
            f"TPR (wrong probes escalated) = {_fmt_opt(evw['tpr_recall_of_wrong'])}, "
            f"FPR (right probes escalated) = {_fmt_opt(evw['fpr_on_right'])}, "
            f"precision = {_fmt_opt(evw['precision'])}",
            f"- Escalation reasons on rescued-eligible (LBPH-wrong) probes: "
            + ", ".join(f"{k}={v}" for k, v in
                        sorted(gm["escalation_reasons_on_wrong"].items(),
                               key=lambda kv: -kv[1])),
        ]
        ga = gate.get("all_probes")
        if ga:
            ga_auc_str = f"{ga['auc_lbph_distance']:.3f}" if ga.get("auc_lbph_distance") is not None else "n/a"
            lines.append(
                f"- Including clean probes: AUC(d1) = {ga_auc_str}, "
                f"gate TPR = {_fmt_opt(ga['escalate_vs_lbph_wrong']['tpr_recall_of_wrong'])}, "
                f"FPR = {_fmt_opt(ga['escalate_vs_lbph_wrong']['fpr_on_right'])}")
        if gm.get("excluded_no_signal"):
            lines.append(f"- Probes excluded (no gate signal, strict no-face): "
                         f"{gm['excluded_no_signal']}")
    lines.append("")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
