#!/usr/bin/env python3
"""Multi-shot LBPH + SFace enrollment for the LFW >=5-images-per-identity
population (423 identities as of 2026-08-02 - see
docs/experiments/lfw-multishot-lbph/README.md, workspace root). Isolates
"does multi-shot LBPH training fix wild-LFW AR" from the self-match leak
that would otherwise inflate the number, by building THREE artifact sets
(a third, ``singleshot``, was added on advisor review - see below - to also
isolate the gallery-size/population confound):

* ``selfmatch`` - LBPH trained on ALL images of each identity (multi-shot).
  SFace gallery = a single deterministically-picked reference image, which is
  ALSO part of LBPH training. The reference image is copied to
  ``data/lfw_multishot_selfmatch_probes/<person>/`` so the legacy
  transform_sensitivity path in accuracy_ratio_hybrid.py probes an image the
  model was already trained on. Reported as a self-match reference/ceiling
  number, never as Accuracy Ratio.
* ``heldout`` - the SAME deterministically-picked image per identity is held
  out ENTIRELY: excluded from LBPH training AND from the SFace gallery.
  LBPH trains on the remaining >=4 images; the SFace gallery uses one of
  those remaining images (last in sorted order - mirrors
  scripts/pipeline/run_lfw2_robustness.py::ensure_lfw2_enrollment's
  "last-in-selection wins" mechanic, just made explicit via sort order
  instead of relying on dict-overwrite semantics). The held-out image is
  copied to ``data/lfw_multishot_heldout_probes/<person>/`` - a genuine
  gallery/probe-disjoint protocol at the individual level, even though it
  still reports as ``transform_sensitivity`` (a labelling quirk of the
  underlying script, not a bug - the probe and every enrolled image are
  genuinely different files).

All variants pick the SAME reference/held-out file per person (single
seeded RNG, same method as ``select_originals()`` in accuracy_ratio_hybrid.py:
sorted persons, one ``rng.choice(files)`` per person) - this is intentional:
that file plays the "self-match probe" role in variant 1 and the "true
held-out probe" role in variants 2 and 3, so they differ ONLY in
whether/how much that one image (and how many others) was used for training.

A third variant, ``singleshot``, is the clean CONTROL for ``heldout`` (added
on advisor review): SAME 423-identity population, SAME held-out probe files,
SAME SFace gallery image/feature as ``heldout``, but LBPH trains on ONLY that
one gallery image (1-shot) instead of the remaining >=4. Comparing
``heldout`` against the shared 5,749-identity/1,680-probe main baseline
cannot isolate "does multi-shot help" from two confounds that ride along
with it: gallery size (423 vs 5,749 - Rank-1 is mechanically easier in a
13.6x smaller gallery) and population (this high-image-count 423 subset of
public figures vs all of LFW). ``singleshot`` matches ``heldout`` on both of
those and differs ONLY in training-images-per-identity, so
``heldout`` vs ``singleshot`` is the actual multi-shot-isolating comparison;
``singleshot`` vs the main baseline separately shows the gallery-size/
population effect.

Detection (YuNet) and SFace embedding run exactly ONCE per image (single
pass over the 423-identity population), cached in memory, and reused to
build all requested variants' LBPH models and SFace galleries - avoids
repeating the ~6,000-image detect+embed cost per variant.

Writes (LBPHAdapter/SFaceAdapter-compatible, same formats
ensure_lfw2_enrollment writes - see that function's docstring):
  models/lfw_multishot/<variant>/lbph_model.yml
  models/lfw_multishot/<variant>/lbph_labels.json
  models/lfw_multishot/<variant>/sface_gallery.npy
  models/lfw_multishot/<variant>/sface_labels.json
  models/lfw_multishot/<variant>/manifest.json
  data/lfw_multishot_<variant>_probes/<person>/<picked_file>  (one file per person)
  data/splits/lfw_multishot_population_seed42.json  (the 423-identity population + picks, shared by all variants)

Does NOT touch scripts/pipeline/run_lfw2_robustness.py or models/lfw2/.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import random
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import cv2 as cv  # noqa: E402
import numpy as np  # noqa: E402

from src.classical_faces.datasets import list_image_files  # noqa: E402
from src.classical_faces.detection import create_face_detector  # noqa: E402
from src.classical_faces.pipeline import SPECS  # noqa: E402
from src.classical_faces.preprocess import IMG_SIZE, normalize_face  # noqa: E402
from src.hybrid.recognizer import detect_sample  # noqa: E402
from src.sface.recognizer import SFaceGallery, SFaceRecognizer, default_sface_model_path  # noqa: E402

VARIANTS = ("selfmatch", "heldout", "singleshot")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lfw-root", default=str(PROJECT_ROOT / "data" / "lfw-dataset"))
    p.add_argument("--min-images", type=int, default=5,
                    help="Population filter: identities with >= this many images.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--variant", choices=[*VARIANTS, "all"], default="all",
                    help="'all' (default) builds all three: selfmatch, heldout, singleshot.")
    p.add_argument("--out-root", default=str(PROJECT_ROOT / "models" / "lfw_multishot"))
    p.add_argument("--probes-root", default=str(PROJECT_ROOT / "data"))
    p.add_argument("--population-json",
                    default=str(PROJECT_ROOT / "data" / "splits" / "lfw_multishot_population_seed42.json"))
    p.add_argument("--limit-identities", type=int, default=0,
                    help="Debug/smoke-test only: enroll at most this many identities (0 = all).")
    return p.parse_args()


def build_population(lfw_root: str, min_images: int) -> dict[str, list[str]]:
    """{person: sorted image filenames} for every identity with >= min_images."""
    out: dict[str, list[str]] = {}
    for person in sorted(os.listdir(lfw_root)):
        pdir = os.path.join(lfw_root, person)
        if not os.path.isdir(pdir):
            continue
        files = list_image_files(pdir)
        if len(files) >= min_images:
            out[person] = files
    return out


def pick_reference(population: dict[str, list[str]], seed: int) -> dict[str, str]:
    """One deterministic filename per person - same method as
    accuracy_ratio_hybrid.select_originals(): sorted persons, single seeded
    RNG, one rng.choice(files) per person, in order."""
    rng = random.Random(seed)
    picked: dict[str, str] = {}
    for person in sorted(population):
        picked[person] = rng.choice(population[person])
    return picked


def main() -> int:
    args = parse_args()
    variants = list(VARIANTS) if args.variant == "all" else [args.variant]

    population = build_population(args.lfw_root, args.min_images)
    if not population:
        raise RuntimeError(f"No identities with >= {args.min_images} images under {args.lfw_root}")
    persons = sorted(population)
    if args.limit_identities:
        persons = persons[:args.limit_identities]
        population = {p: population[p] for p in persons}
    picked = pick_reference(population, args.seed)

    total_images = sum(len(v) for v in population.values())
    counts = sorted(len(v) for v in population.values())
    median_count = counts[len(counts) // 2] if len(counts) % 2 else (
        counts[len(counts) // 2 - 1] + counts[len(counts) // 2]) / 2
    print(f"[POP] {len(persons)} identities with >= {args.min_images} images "
          f"({total_images} total images, median {median_count}, max {max(counts)})")

    pop_json_path = Path(args.population_json)
    pop_json_path.parent.mkdir(parents=True, exist_ok=True)
    pop_json_path.write_text(json.dumps({
        "schema": "lsface-lfw-multishot-population-v1",
        "lfw_root": args.lfw_root,
        "min_images": args.min_images,
        "seed": args.seed,
        "identities": len(persons),
        "total_images": total_images,
        "median_images_per_identity": median_count,
        "max_images_per_identity": max(counts),
        "reference_pick_method": "sorted persons, single random.Random(seed), "
                                  "rng.choice(sorted(list_image_files(person_dir))) per person "
                                  "(same method as accuracy_ratio_hybrid.select_originals)",
        "population": {p: population[p] for p in persons},
        "picked_reference_file": picked,
        "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2), encoding="utf-8")
    print(f"[POP] Wrote {pop_json_path}")

    # --- Single detect+embed pass over every population image, cached. ---
    print(f"[EMBED] Detecting + embedding {total_images} images (single pass, shared by all requested variants)...")
    detector = create_face_detector("yunet")
    sface = SFaceRecognizer(default_sface_model_path())
    equalization = SPECS["lbph"].default_equalization

    # cache[person][filename] = (normalized_face_gray, sface_feature)
    cache: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
    yunet_misses = 0
    n_done = 0
    for person in persons:
        cache[person] = {}
        for fn in population[person]:
            path = os.path.join(args.lfw_root, person, fn)
            img = cv.imread(path)
            if img is None:
                continue
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            sample = detect_sample(detector, image_bgr=img, image_gray=gray, assume_cropped=False)
            if sample is None:
                face_gray = gray
                feature = sface.feature_from_crop(img)
                yunet_misses += 1
            else:
                face_gray = sample.face_gray
                feature = (
                    sface.feature_from_row(sample.image_bgr, sample.yunet_row)
                    if sample.yunet_row is not None
                    else sface.feature_from_crop(sample.image_bgr)
                )
            norm = normalize_face(face_gray, img_size=IMG_SIZE, equalization=equalization)
            cache[person][fn] = (norm, feature)
            n_done += 1
            if n_done % 1000 == 0:
                print(f"[EMBED] {n_done}/{total_images} images embedded...")
    print(f"[EMBED] Done. {n_done}/{total_images} images embedded (YuNet misses: {yunet_misses}).")

    label_map = {person: idx for idx, person in enumerate(persons)}

    for variant in variants:
        print(f"\n[{variant.upper()}] Building enrollment...")
        faces: list[np.ndarray] = []
        labels: list[int] = []
        embeddings: dict[str, list[np.ndarray]] = {}
        gallery_file: dict[str, str] = {}
        excluded_file: dict[str, str] = {}

        for person in persons:
            ref = picked[person]
            all_files = sorted(cache[person])
            if variant == "selfmatch":
                # Every image trains LBPH; ref moved LAST so it wins the
                # SFace gallery slot too.
                order = [f for f in all_files if f != ref] + [ref]
                gallery_pick = ref
            elif variant == "heldout":
                # ref is excluded entirely; last remaining file (sorted)
                # wins the SFace gallery slot.
                order = [f for f in all_files if f != ref]
                if not order:
                    raise RuntimeError(f"{person}: no images left after holding out {ref!r} "
                                        f"(population filter --min-images should prevent this)")
                gallery_pick = order[-1]
                excluded_file[person] = ref
            else:  # singleshot: the clean single-image CONTROL for the
                # heldout comparison (advisor review, 2026-08-02) -- isolates
                # multi-shot-vs-1-shot from gallery-size (423 vs 5,749) and
                # population (high-image-count subset vs all of LFW), which
                # comparing heldout directly against the main 5,749-identity
                # baseline could NOT isolate. SAME gallery_pick file as
                # heldout (last remaining sorted file after excluding ref),
                # SAME held-out probe (ref, excluded here too) -- only
                # training-images-per-identity (1 vs >=4) differs from heldout.
                remaining = [f for f in all_files if f != ref]
                if not remaining:
                    raise RuntimeError(f"{person}: no images left after holding out {ref!r} "
                                        f"(population filter --min-images should prevent this)")
                gallery_pick = remaining[-1]
                order = [gallery_pick]
                excluded_file[person] = ref
            for fn in order:
                norm, _feature = cache[person][fn]
                faces.append(norm)
                labels.append(label_map[person])
            embeddings[person] = [cache[person][gallery_pick][1]]
            gallery_file[person] = gallery_pick

        print(f"[{variant.upper()}] Training LBPH on {len(faces)} faces "
              f"({len(label_map)} identities)...")
        recognizer = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        recognizer.train(faces, np.array(labels, dtype=np.int32))

        out_dir = Path(args.out_root) / variant
        out_dir.mkdir(parents=True, exist_ok=True)
        lbph_model = out_dir / "lbph_model.yml"
        lbph_labels = out_dir / "lbph_labels.json"
        sface_gallery = out_dir / "sface_gallery.npy"
        sface_labels = out_dir / "sface_labels.json"
        recognizer.save(str(lbph_model))
        lbph_labels.write_text(json.dumps(label_map, indent=2), encoding="utf-8")
        SFaceGallery.from_samples(sface, embeddings).save(str(sface_gallery), str(sface_labels))

        # Probe directory: one file per person, copied verbatim (no
        # re-encoding) so accuracy_ratio_hybrid's legacy same-image
        # (transform_sensitivity) path can walk it unmodified.
        probes_dir = Path(args.probes_root) / f"lfw_multishot_{variant}_probes"
        if probes_dir.exists():
            shutil.rmtree(probes_dir)
        probe_file_by_person = gallery_file if variant == "selfmatch" else excluded_file
        for person, fn in probe_file_by_person.items():
            src = Path(args.lfw_root) / person / fn
            dst_dir = probes_dir / person
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst_dir / fn)

        manifest = {
            "variant": variant,
            "lfw_root": args.lfw_root,
            "seed": args.seed,
            "min_images": args.min_images,
            "identities": len(label_map),
            "lbph_training_faces": len(faces),
            "probes_dir": str(probes_dir),
            "probe_is_training_image": variant == "selfmatch",
            "probe_excluded_from_training_and_gallery": variant in ("heldout", "singleshot"),
            "sface_gallery_file_per_person": gallery_file,
            "note": (
                "selfmatch: probe == the LBPH-training/SFace-gallery reference image "
                "(self-match leak by design - reference/ceiling number, NOT Accuracy Ratio)."
                if variant == "selfmatch" else
                "heldout: probe is EXCLUDED from LBPH training and the SFace gallery "
                "entirely - genuine gallery/probe-disjoint protocol at the image level, "
                "despite reporting as 'transform_sensitivity' (see accuracy_ratio_hybrid.py; "
                "that is a labelling quirk of the underlying script, not a bug here)."
                if variant == "heldout" else
                "singleshot: single-image-per-identity CONTROL for heldout (added on advisor "
                "review) - SAME 423-identity population, SAME probe files, SAME gallery_pick "
                "file/feature as heldout, SAME thresholds; only training-images-per-identity "
                "(1 here vs >=4 in heldout) differs. Isolates the multi-shot variable from "
                "the gallery-size (423 vs 5,749) and population (high-image-count subset vs "
                "all of LFW) confounds that a direct heldout-vs-main-baseline comparison could "
                "not separate."
            ),
            "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"[{variant.upper()}] Wrote {out_dir} and {probes_dir} ({len(probe_file_by_person)} probe files)")

    print("\n[DONE] Multi-shot enrollment complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
