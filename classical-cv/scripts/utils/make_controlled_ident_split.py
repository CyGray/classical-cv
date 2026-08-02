"""Build a gallery/probe-DISJOINT 1:N identification split manifest for a small,
fully-enumerated controlled dataset (La Salle DB1, AT&T/ORL faces) — same manifest
schema shape as ``data/splits/lfw_ident_split_seed42.json``
(``scripts/utils/make_lfw_identification_split.py``), consumed by the same
``load_split_manifest`` / ``load_gallery_from_manifest`` / ``load_probes_from_manifest``
functions in ``src/benchmark/accuracy_ratio_hybrid.py``.

Unlike the LFW split builder, these datasets have a FIXED, small image count per
identity (12 for La Salle DB1, 10 for AT&T/ORL) and no singletons, so there is no
"K probes, sample-and-fall-back" logic and no YuNet quality gate at build time:
one seeded random gallery pick per identity, and every OTHER image of that
identity becomes a probe (all of them, not a sample) — this is a "full scale,
no subsetting" run per its own design, so leaving images unused would silently
throw away statistical power for no reason. See advisor guidance in this
session: enrollment (``ensure_lasalle_db1_enrollment`` / ``ensure_att_faces_
enrollment``) falls back gracefully on a YuNet miss rather than dropping the
identity, so a build-time quality gate isn't needed here the way it was for
LFW's messier source tree.

Output schema: ``lsface-controlled-ident-split-v1``.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import random
from pathlib import Path

DEFAULT_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".pgm", ".ppm")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset-root", required=True)
    p.add_argument("--dataset-label", required=True,
                    help="Short label recorded in the manifest, e.g. 'lasalle_db1_processed' or 'att_faces'.")
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--extensions", default=",".join(DEFAULT_EXTENSIONS),
                    help="Comma list of allowed (lowercased) file extensions.")
    return p.parse_args()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_relpath(abs_path: str, root: str) -> str:
    return os.path.relpath(abs_path, root).replace(os.sep, "/")


def build_split(dataset_root: str, dataset_label: str, seed: int, extensions: tuple[str, ...]) -> dict:
    rng = random.Random(seed)
    persons = sorted(
        p for p in os.listdir(dataset_root) if os.path.isdir(os.path.join(dataset_root, p))
    )
    if not persons:
        raise RuntimeError(f"No identity folders under {dataset_root}")

    identities: dict[str, dict] = {}
    n_gallery = 0
    n_probes_total = 0
    per_identity_counts: dict[int, int] = {}

    for person in persons:
        person_dir = os.path.join(dataset_root, person)
        files = sorted(
            f for f in os.listdir(person_dir)
            if os.path.splitext(f)[1].lower() in extensions
            and os.path.isfile(os.path.join(person_dir, f))
        )
        if not files:
            continue
        gallery_fn = rng.choice(files)
        probe_fns = [f for f in files if f != gallery_fn]  # ALL remaining images, full scale
        identities[person] = {
            "gallery": to_relpath(os.path.join(person_dir, gallery_fn), dataset_root),
            "probe": (to_relpath(os.path.join(person_dir, probe_fns[0]), dataset_root)
                      if probe_fns else None),
            "probes": [to_relpath(os.path.join(person_dir, p), dataset_root) for p in probe_fns],
            "n_files_total": len(files),
            "n_probes_realized": len(probe_fns),
            "demoted": False,
            "singleton": len(probe_fns) == 0,
        }
        n_gallery += 1
        n_probes_total += len(probe_fns)
        per_identity_counts[len(probe_fns)] = per_identity_counts.get(len(probe_fns), 0) + 1

    triples = sorted(
        (person, entry["gallery"], ",".join(entry["probes"]))
        for person, entry in identities.items()
    )
    triples_text = "\n".join(f"{p}|{g}|{pr}" for p, g, pr in triples)

    return {
        "schema": "lsface-controlled-ident-split-v1",
        "dataset_root": str(Path(dataset_root).resolve()),
        "dataset_label": dataset_label,
        "seed": seed,
        "max_probes_per_identity": None,  # not sampled — ALL remaining images per identity are probes
        "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "protocol": "gallery-probe-disjoint 1:N identification (full-scale, all-remaining-images-as-probes variant)",
        "identities": identities,
        "counts": {
            "n_identities": len(identities),
            "n_gallery": n_gallery,
            "n_probes": n_probes_total,
            "probe_count_histogram": {str(k): v for k, v in sorted(per_identity_counts.items())},
        },
        "triples_sha256": sha256_hex(triples_text),
    }


def main() -> int:
    args = parse_args()
    extensions = tuple(e.strip().lower() for e in args.extensions.split(",") if e.strip())
    dataset_root = str(Path(args.dataset_root).resolve())
    if not os.path.isdir(dataset_root):
        print(f"[ERROR] Dataset root not found: {dataset_root}")
        return 1

    manifest = build_split(dataset_root, args.dataset_label, args.seed, extensions)

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    c = manifest["counts"]
    print("\n[SUMMARY]")
    print(f"  dataset_label       : {args.dataset_label}")
    print(f"  n_identities        : {c['n_identities']}")
    print(f"  n_gallery           : {c['n_gallery']}")
    print(f"  n_probes            : {c['n_probes']}")
    print(f"  probe_count_hist    : {c['probe_count_histogram']}")
    print(f"  triples sha256      : {manifest['triples_sha256']}")
    print(f"  manifest            : {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
