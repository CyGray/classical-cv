"""Build a gallery/probe-DISJOINT identification split for LFW1 (``data/lfw-dataset``).

Fixes the accuracy-ratio methodology bug documented in
``docs/audits/STATE-08-01.md``: the 41-modification benchmark previously
enrolled and probed with the SAME function and seed
(``select_originals(..., select_one_per_person=True, seed=42)`` in
``src/benchmark/accuracy_ratio_hybrid.py``), so every probe was a degraded
copy of the identity's own enrolled image and intra-class distance before
damage was always 0. This script builds the standard Best-Rowden-style 1:N
identification split instead: one gallery image and one DIFFERENT probe
image per identity (when a second image exists).

Design (see ``docs/audits/STATE-08-01.md`` for the full rationale):

* **Gallery** - one image per identity, for ALL identities, including
  singletons. Singletons supply impostor pressure to the 1:N search and keep
  gallery size comparable to the prior (leaky) run; they never get a probe.
* **Probes** - for each identity with >=2 images, up to ``--max-probes-per-
  identity`` (default **1**) further images, disjoint from its gallery pick
  and from each other. Default 1 gives 1,680 probes (one per multi-image
  identity) - the headline configuration. LFW is heavily skewed (13,233
  images / 5,749 identities, but e.g. George_W_Bush alone has 530), so a
  larger K is opt-in, not default: pulling every non-gallery image as a probe
  would let a handful of identities dominate the pooled mean and reintroduces
  a milder near-duplicate leak (many of those extra images are near-identical
  frames from the same press event). K>1 draws from the SAME seed-42 stream;
  the realized per-identity probe count and count histogram are always
  recorded so the skew stays visible.
* **Selection is uniform-random, NOT quality/similarity ranked.** Picking the
  "best" or most-similar pair would reintroduce the exact same leak this
  script exists to close. A single ``random.Random(42)`` instance is walked
  identity-by-identity in sorted order; within an identity, files are
  ``sorted()`` before sampling. This is the ONLY randomness source.
* **Quality gate (the one allowed exception to "no ranking"):** both chosen
  images must pass YuNet detection (mirrors the exact ``detect_sample(...,
  assume_cropped=True)`` call the rest of the hybrid pipeline uses). If a
  chosen image fails, it is deterministically replaced by drawing (still via
  the same ``random.Random`` instance, still ``rng.choice`` over the
  identity's remaining untried files) from what's left, in sorted order. If
  no valid 2-image pair can be formed, the identity is DEMOTED to
  gallery-only and counted (never silently dropped) - its gallery slot is
  chosen the same way, walking remaining files for a YuNet pass; if literally
  every file of an identity fails YuNet, the first sorted file is kept anyway
  (logged) so no identity vanishes from the gallery.

RNG consumption order (identity-by-identity, sorted person order; documented
here because it is the split's reproducibility contract):

    for person in sorted(identities):
        files = sorted(list_image_files(person_dir))
        if len(files) == 1:
            gallery = rng.choice(files)                      # 1 rng call
        else:
            k = min(max_probes_per_identity, len(files) - 1)
            batch = rng.sample(files, 1 + k)                  # 1 rng call
            gallery, probes = batch[0], batch[1:]             # gallery, then probe slots in order
            tried = set(batch)
            for role in (gallery, then each probe slot in order, if it fails yunet):
                while role fails yunet and untried files remain:
                    replacement = rng.choice(remaining_untried)  # 1 rng call
                    tried.add(replacement)

For ``--max-probes-per-identity 1`` (the default), ``1 + k == 2`` whenever the
identity has >=2 images, so this is exactly the original two-slot draw
(``rng.sample(files, 2)``) - K=1 output is bit-identical to the split this
script produced before K became configurable.

Output: ``data/splits/lfw_ident_split_seed42.json``, schema
``lsface-lfw-ident-split-v1``.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import random
import sys
from pathlib import Path

import cv2 as cv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classical_faces.datasets import list_image_files  # noqa: E402
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.hybrid.recognizer import detect_sample  # noqa: E402

DEFAULT_DATASET_ROOT = PROJECT_ROOT / "data" / "lfw-dataset"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "splits" / "lfw_ident_split_seed42.json"
SCHEMA = "lsface-lfw-ident-split-v1"

# The build actually downloaded/verified for this task (see docs/audits/STATE-08-01.md):
# original, UNFUNNELED LFW from the figshare mirror (the UMass host is unreachable
# from this machine). Deliberately NOT the Kaggle `jessicali9530/lfw-dataset` copy
# (deep-funneled) and NOT any `*_processed`/one-per-identity/100x100 tree - those
# collapse to one image per person before this split ever runs, which is exactly
# the failure mode this script exists to avoid. Parameterised (not hardcoded logic)
# so a second, deep-funneled ablation manifest can be built later with
# `--lfw-build deep-funneled --source-url ... --archive-sha256 ...` and no code change.
DEFAULT_LFW_BUILD = "original-unfunneled"
DEFAULT_SOURCE_URL = "https://ndownloader.figshare.com/files/5976018"
DEFAULT_ARCHIVE_SHA256 = "055f7d9c632d7370e6fb4afc7468d40f970c34a80d4c6f50ffec63f5a8d536c0"
EXPECTED_IMAGE_SIZE = (250, 250)  # (width, height) of the original-unfunneled build
MIN_MULTI_IMAGE_IDENTITIES = 1680  # hard floor; a degenerate/pre-collapsed tree fails this


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the gallery/probe-disjoint LFW identification split manifest."
    )
    parser.add_argument("--dataset-root", "--dataset-dir", dest="dataset_root",
                         default=str(DEFAULT_DATASET_ROOT),
                         help="LFW identity folders (default: data/lfw-dataset). "
                              "Must be the original-unfunneled tree (or another build "
                              "passed with a matching --lfw-build label) - NOT "
                              "data/lfw/{light,medium,heavy}, NOT any *_processed tree.")
    parser.add_argument("--lfw-build", default=DEFAULT_LFW_BUILD,
                         help="Label for which LFW build --dataset-root points at "
                              "(default: original-unfunneled). Recorded in the manifest "
                              "so distances from different builds are never mixed silently.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL,
                         help="Where --dataset-root's archive was downloaded from (recorded, not fetched).")
    parser.add_argument("--archive-sha256", default=DEFAULT_ARCHIVE_SHA256,
                         help="SHA256 of the downloaded archive (recorded, not verified against disk).")
    parser.add_argument("--seed", type=int, default=42,
                         help="Single random.Random seed driving every selection (default 42).")
    parser.add_argument("--max-probes-per-identity", type=int, default=1,
                         help="Up to this many probes per multi-image identity, drawn from "
                              "the same seed-42 stream (default 1 = the headline "
                              "configuration, 1,680 probes). LFW's per-identity image count "
                              "is heavily skewed (e.g. George_W_Bush has 530), so raising this "
                              "is opt-in: it is NOT the same as using every non-gallery image.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                         help=f"Output manifest path (default {DEFAULT_OUTPUT}).")
    parser.add_argument("--limit-identities", type=int, default=0,
                         help="Debug/smoke-test only: stop after this many identities "
                              "(0 = all). Identities are still walked in sorted order, "
                              "so this is a stable prefix, not a random subset. NOTE: "
                              "this also bypasses the >=1680-multi-image-identity guard "
                              "rail below (a small prefix legitimately has fewer).")
    return parser.parse_args()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_relpath(abs_path: str, root: str) -> str:
    return os.path.relpath(abs_path, root).replace(os.sep, "/")


class WrongLfwBuildError(RuntimeError):
    """Raised when a sampled image's dimensions don't match the expected
    original-unfunneled build - the guard against silently splitting a
    pre-resized / one-per-identity / wrong-build tree (e.g. `*_processed`,
    100x100, or a deep-funneled copy) instead of the real dataset."""


class YunetGate:
    """Thin cache over ``detect_sample`` so re-checking the same file twice
    (shouldn't happen given the walk below, but cheap insurance) is free.
    Also enforces the expected image size on every file it ever opens - this
    is what stops a wrong-build tree (pre-resized, one-per-identity, etc.)
    from silently producing a degenerate split again."""

    def __init__(self, expected_size: tuple[int, int] | None = EXPECTED_IMAGE_SIZE):
        self.detector = create_face_detector("yunet")
        self._cache: dict[str, bool] = {}
        self.n_checks = 0
        self.expected_size = expected_size  # (width, height), or None to skip the check

    def passes(self, path: str) -> bool:
        if path in self._cache:
            return self._cache[path]
        self.n_checks += 1
        img = cv.imread(path)
        if img is None:
            self._cache[path] = False
            return False
        if self.expected_size is not None:
            h, w = img.shape[:2]
            if (w, h) != self.expected_size:
                raise WrongLfwBuildError(
                    f"{path}: image size {(w, h)} != expected {self.expected_size} "
                    f"for this LFW build. This usually means --dataset-root points at "
                    f"a pre-resized/one-per-identity/wrong-build tree (e.g. a "
                    f"`*_processed` folder, or a deep-funneled copy) rather than the "
                    f"original-unfunneled 250x250 tree this split expects. If you are "
                    f"intentionally building a manifest for a different LFW build, pass "
                    f"a matching --lfw-build label (this guard currently assumes "
                    f"'{DEFAULT_LFW_BUILD}')."
                )
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        sample = detect_sample(self.detector, image_bgr=img, image_gray=gray, assume_cropped=True)
        ok = sample is not None
        self._cache[path] = ok
        return ok


def pick_gallery_only(files: list[str], person_dir: str, rng: random.Random, gate: YunetGate,
                       already_tried: set[str] | None = None) -> tuple[str, int, bool]:
    """Walk ``files`` (already sampled order encoded by caller) for one YuNet-passing
    image. Returns (filename, n_resamples, forced_without_pass).
    ``already_tried`` seeds the tried-set so a demoted pair-selection doesn't
    re-try images already known to fail."""
    tried = set(already_tried or set())
    remaining = [f for f in files if f not in tried]
    n_resamples = 0
    # First candidate: rng.choice over whatever is untried (documented single-call draw).
    while remaining:
        if not tried:
            # true "first pick" case (singleton or fresh demoted walk)
            candidate = rng.choice(remaining)
        else:
            candidate = rng.choice(remaining)
            n_resamples += 1
        tried.add(candidate)
        remaining = [f for f in files if f not in tried]
        if gate.passes(os.path.join(person_dir, candidate)):
            return candidate, n_resamples, False
    # Every file failed YuNet: keep the first sorted file so the identity is
    # never dropped from the gallery (logged as forced_without_pass).
    return files[0], n_resamples, True


def build_split(
    dataset_dir: str,
    seed: int,
    limit_identities: int = 0,
    lfw_build: str = DEFAULT_LFW_BUILD,
    source_url: str = DEFAULT_SOURCE_URL,
    archive_sha256: str = DEFAULT_ARCHIVE_SHA256,
    max_probes_per_identity: int = 1,
) -> dict:
    # Only enforce the fixed 250x250 size for the build this script was verified
    # against; a future ablation leg (e.g. deep-funneled) may have different
    # dimensions and passes its own --lfw-build label, so skip the size guard then.
    expected_size = EXPECTED_IMAGE_SIZE if lfw_build == DEFAULT_LFW_BUILD else None
    rng = random.Random(seed)
    gate = YunetGate(expected_size=expected_size)

    persons = sorted(
        p for p in os.listdir(dataset_dir) if os.path.isdir(os.path.join(dataset_dir, p))
    )

    if not limit_identities:
        # Hard guard rail: fail loudly BEFORE doing any work if this tree has
        # already been collapsed to <2 images/identity (e.g. a `*_processed`
        # one-per-identity tree) - that is exactly the prior bug's failure mode.
        n_multi = sum(
            1 for p in persons
            if len(list_image_files(os.path.join(dataset_dir, p))) >= 2
        )
        if n_multi < MIN_MULTI_IMAGE_IDENTITIES:
            raise WrongLfwBuildError(
                f"Only {n_multi} identities under {dataset_dir} have >=2 images "
                f"(expected >= {MIN_MULTI_IMAGE_IDENTITIES} for the "
                f"'{DEFAULT_LFW_BUILD}' build). This dataset root looks pre-collapsed "
                f"to one image per identity (or otherwise wrong) - a disjoint "
                f"gallery/probe split is impossible to build from it. Point "
                f"--dataset-root at the original-unfunneled 250x250 tree "
                f"(data/lfw-dataset), not a `*_processed` or one-per-identity folder."
            )

    if limit_identities:
        persons = persons[:limit_identities]

    if max_probes_per_identity < 1:
        raise ValueError("--max-probes-per-identity must be >= 1")

    identities: dict[str, dict] = {}
    n_gallery = 0
    n_probes_total = 0
    n_demoted = 0
    n_singletons = 0
    n_yunet_resamples = 0
    n_forced_without_pass = 0
    probe_count_histogram: dict[int, int] = {}

    for person in persons:
        person_dir = os.path.join(dataset_dir, person)
        files = sorted(list_image_files(person_dir))
        if not files:
            continue

        if len(files) == 1:
            n_singletons += 1
            gallery_fn, resamples, forced = pick_gallery_only(files, person_dir, rng, gate)
            n_yunet_resamples += resamples
            n_forced_without_pass += int(forced)
            identities[person] = {
                "gallery": to_relpath(os.path.join(person_dir, gallery_fn), dataset_dir),
                "probe": None,
                "probes": [],
                "demoted": False,
                "singleton": True,
                "yunet_resamples": resamples,
                "yunet_forced_without_pass": forced,
            }
            n_gallery += 1
            probe_count_histogram[0] = probe_count_histogram.get(0, 0) + 1
            continue

        # Multi-image identity: one rng.sample(files, 1 + k) draw - batch[0] is
        # the gallery slot, batch[1:] are the (up to k) probe slots, in order.
        # k=min(max_probes_per_identity, len(files)-1). For the default K=1
        # this is exactly rng.sample(files, 2) - bit-identical to the split
        # this script produced before K became configurable.
        k = min(max_probes_per_identity, len(files) - 1)
        batch = rng.sample(files, 1 + k)
        gallery_fn, probe_fns = batch[0], batch[1:]
        tried = set(batch)
        resamples_this_identity = 0

        def resolve(candidate: str) -> tuple[str, bool]:
            """Verify candidate against YuNet; if it fails, deterministically
            resample from this identity's remaining untried files (same rng,
            rng.choice, sorted-file order). Returns (final_filename, ok)."""
            nonlocal resamples_this_identity, tried
            current = candidate
            while True:
                if gate.passes(os.path.join(person_dir, current)):
                    return current, True
                remaining = [f for f in files if f not in tried]
                if not remaining:
                    return current, False
                current = rng.choice(remaining)
                tried.add(current)
                resamples_this_identity += 1

        gallery_final, gallery_ok = resolve(gallery_fn)
        # Resolve probe slots IN ORDER (gallery first, matches original
        # single-probe RNG order exactly when k==1).
        probe_results = [resolve(pf) for pf in probe_fns]
        n_yunet_resamples += resamples_this_identity

        probes_final = [
            fn for fn, ok in probe_results if ok and gallery_ok and fn != gallery_final
        ]
        any_probe_slot_failed = any(not ok for _fn, ok in probe_results)
        # Probe-slot failures that still leave >=1 usable probe (K>1 partial
        # fulfillment) are counted here; the demoted branch below counts its
        # own gallery-forced-without-pass separately (via forced2) so a fully
        # failed identity isn't double-counted across both branches.
        if gallery_ok and probes_final:
            n_forced_without_pass += sum(1 for _fn, ok in probe_results if not ok)

        if gallery_ok and probes_final:
            identities[person] = {
                "gallery": to_relpath(os.path.join(person_dir, gallery_final), dataset_dir),
                "probe": to_relpath(os.path.join(person_dir, probes_final[0]), dataset_dir),
                "probes": [to_relpath(os.path.join(person_dir, p), dataset_dir) for p in probes_final],
                "demoted": False,
                "singleton": False,
                "n_probes_requested": k,
                "n_probes_realized": len(probes_final),
                "yunet_resamples": resamples_this_identity,
                "yunet_forced_without_pass": any_probe_slot_failed or not gallery_ok,
            }
            n_gallery += 1
            n_probes_total += len(probes_final)
            probe_count_histogram[len(probes_final)] = probe_count_histogram.get(len(probes_final), 0) + 1
        else:
            # Could not form EVEN ONE valid disjoint YuNet-passing probe ->
            # demote to gallery-only, COUNT it, never silently drop. Walk
            # remaining files (same rng) for one passing gallery image;
            # fall back to the first sorted file if literally none pass.
            n_demoted += 1
            gallery_fn2, resamples2, forced2 = pick_gallery_only(
                files, person_dir, rng, gate, already_tried=tried
            )
            n_yunet_resamples += resamples2
            n_forced_without_pass += int(forced2)
            identities[person] = {
                "gallery": to_relpath(os.path.join(person_dir, gallery_fn2), dataset_dir),
                "probe": None,
                "probes": [],
                "demoted": True,
                "singleton": False,
                "n_probes_requested": k,
                "n_probes_realized": 0,
                "yunet_resamples": resamples_this_identity + resamples2,
                "yunet_forced_without_pass": forced2,
            }
            n_gallery += 1
            probe_count_histogram[0] = probe_count_histogram.get(0, 0) + 1

    triples = sorted(
        (person, entry["gallery"], ",".join(entry["probes"]))
        for person, entry in identities.items()
    )
    triples_text = "\n".join(f"{p}|{g}|{pr}" for p, g, pr in triples)

    manifest = {
        "schema": SCHEMA,
        "dataset_root": str(Path(dataset_dir).resolve()),
        "lfw_build": lfw_build,
        "source_url": source_url,
        "archive_sha256": archive_sha256,
        "seed": seed,
        "max_probes_per_identity": max_probes_per_identity,
        "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "protocol": "gallery-probe-disjoint 1:N identification (Best-Rowden et al. 2014 style)",
        "identities": identities,
        "counts": {
            "n_identities": len(identities),
            "n_gallery": n_gallery,
            "n_probes": n_probes_total,
            "n_demoted": n_demoted,
            "n_singletons": n_singletons,
            "n_yunet_resamples": n_yunet_resamples,
            "n_yunet_forced_without_pass": n_forced_without_pass,
            "n_yunet_checks": gate.n_checks,
            "probe_count_histogram": {str(k): v for k, v in sorted(probe_count_histogram.items())},
        },
        "triples_sha256": sha256_hex(triples_text),
    }
    return manifest


def main() -> int:
    args = parse_args()
    dataset_dir = str(Path(args.dataset_root).resolve())
    if not os.path.isdir(dataset_dir):
        print(f"[ERROR] Dataset dir not found: {dataset_dir}")
        return 1

    manifest = build_split(
        dataset_dir, args.seed, args.limit_identities,
        lfw_build=args.lfw_build, source_url=args.source_url,
        archive_sha256=args.archive_sha256,
        max_probes_per_identity=args.max_probes_per_identity,
    )

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    c = manifest["counts"]
    print("\n[SUMMARY]")
    print(f"  max_probes_per_identity: {manifest['max_probes_per_identity']}")
    print(f"  n_identities        : {c['n_identities']}")
    print(f"  n_gallery           : {c['n_gallery']}")
    print(f"  n_probes            : {c['n_probes']}")
    print(f"  n_demoted           : {c['n_demoted']}")
    print(f"  n_singletons        : {c['n_singletons']}")
    print(f"  n_yunet_resamples   : {c['n_yunet_resamples']}")
    print(f"  n_yunet_forced      : {c['n_yunet_forced_without_pass']}")
    print(f"  n_yunet_checks      : {c['n_yunet_checks']}")
    print(f"  probe_count_hist    : {c['probe_count_histogram']}")
    print(f"  triples sha256      : {manifest['triples_sha256']}")
    print(f"  manifest            : {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
