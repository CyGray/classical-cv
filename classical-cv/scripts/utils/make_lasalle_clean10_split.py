"""Build the "clean10" gallery/probe-DISJOINT 1:N identification split for
La Salle DB1, using the training-data composition ``docs/reports/DATASET_MATRIX.md``
found optimal for LBPH: 10 gallery images per identity (5 ``light_*`` + 5
``dark_*`` poses: front/up/down/left/right), holding out ``light_name`` +
``dark_name`` as the 2 probes per identity. This mirrors DATASET_MATRIX's
``clean`` recipe (280 train / 56 test across 28 ids) exactly, rebuilt from
``data/lasalle_db1_processed`` because ``data/split_lasalle`` has rotted
(verified 2026-08-02: 10 train ids x 1 file, 14 empty test dirs -- unusable).

Unlike ``make_controlled_ident_split.py`` (single random gallery image),
this is a DETERMINISTIC pose-based split, not a random pick -- every
identity gets the identical pose composition. Schema stays
``lsface-controlled-ident-split-v1`` with one addition: ``gallery`` is a
LIST of relpaths (10 entries), not a single string, so LBPH enrollment can
train multiple templates per identity. ``load_gallery_from_manifest`` in
``src/benchmark/accuracy_ratio_hybrid.py`` was extended to accept either
shape.

Verified 2026-08-02: all 28 identities in data/lasalle_db1_processed share
the exact same 12 filenames (dark_{down,front,left,name,right,up}.jpg,
light_{down,front,left,name,right,up}.jpg) -- no per-identity naming drift.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path

GALLERY_POSES = [
    "light_front", "light_up", "light_down", "light_left", "light_right",
    "dark_front", "dark_up", "dark_down", "dark_left", "dark_right",
]
PROBE_POSES = ["light_name", "dark_name"]
EXT = ".jpg"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset-root", default="data/lasalle_db1_processed")
    p.add_argument("--dataset-label", default="lasalle_db1_processed_clean10")
    p.add_argument("--output", default="data/splits/lasalle_db1_ident_split_clean10_seed42.json")
    p.add_argument("--seed", type=int, default=42,
                    help="Recorded for schema parity; this split is deterministic (pose-based), not RNG-driven.")
    return p.parse_args()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_relpath(abs_path: str, root: str) -> str:
    return os.path.relpath(abs_path, root).replace(os.sep, "/")


def build_split(dataset_root: str, dataset_label: str, seed: int) -> dict:
    persons = sorted(
        p for p in os.listdir(dataset_root) if os.path.isdir(os.path.join(dataset_root, p))
    )
    if not persons:
        raise RuntimeError(f"No identity folders under {dataset_root}")

    identities: dict[str, dict] = {}
    for person in persons:
        person_dir = os.path.join(dataset_root, person)
        files = set(os.listdir(person_dir))
        missing = [f"{pose}{EXT}" for pose in GALLERY_POSES + PROBE_POSES if f"{pose}{EXT}" not in files]
        if missing:
            raise RuntimeError(f"{person}: missing expected files {missing}")

        gallery_rels = [to_relpath(os.path.join(person_dir, f"{pose}{EXT}"), dataset_root)
                         for pose in GALLERY_POSES]
        probe_rels = [to_relpath(os.path.join(person_dir, f"{pose}{EXT}"), dataset_root)
                      for pose in PROBE_POSES]
        identities[person] = {
            "gallery": gallery_rels,
            "probe": probe_rels[0],
            "probes": probe_rels,
            "n_files_total": len(files),
            "n_probes_realized": len(probe_rels),
            "n_gallery_realized": len(gallery_rels),
            "demoted": False,
            "singleton": False,
        }

    triples = sorted(
        (person, ",".join(entry["gallery"]), ",".join(entry["probes"]))
        for person, entry in identities.items()
    )
    triples_text = "\n".join(f"{p}|{g}|{pr}" for p, g, pr in triples)

    return {
        "schema": "lsface-controlled-ident-split-v1",
        "dataset_root": str(Path(dataset_root).resolve()),
        "dataset_label": dataset_label,
        "seed": seed,
        "recipe": "dataset_matrix_clean (docs/reports/DATASET_MATRIX.md): 5 light_* + 5 dark_* poses gallery, light_name+dark_name held out as probes",
        "max_probes_per_identity": None,
        "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "protocol": "gallery-probe-disjoint 1:N identification (10-image multi-shot gallery per identity, deterministic pose-based split)",
        "identities": identities,
        "counts": {
            "n_identities": len(identities),
            "n_gallery": len(identities) * len(GALLERY_POSES),
            "n_probes": len(identities) * len(PROBE_POSES),
            "probe_count_histogram": {str(len(PROBE_POSES)): len(identities)},
        },
        "triples_sha256": sha256_hex(triples_text),
    }


def main() -> int:
    args = parse_args()
    dataset_root = str(Path(args.dataset_root).resolve())
    if not os.path.isdir(dataset_root):
        print(f"[ERROR] Dataset root not found: {dataset_root}")
        return 1

    manifest = build_split(dataset_root, args.dataset_label, args.seed)

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    c = manifest["counts"]
    print("\n[SUMMARY]")
    print(f"  dataset_label       : {args.dataset_label}")
    print(f"  n_identities        : {c['n_identities']}")
    print(f"  n_gallery           : {c['n_gallery']} (10 per identity)")
    print(f"  n_probes            : {c['n_probes']} (2 per identity)")
    print(f"  triples sha256      : {manifest['triples_sha256']}")
    print(f"  manifest            : {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
