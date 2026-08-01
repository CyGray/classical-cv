"""Build a ``lsface-selection-manifest-v1`` JSON for a raw LFW copy.

``scripts/utils/make_selection_manifest.py`` cannot be used for raw LFW: it imports
``select_one_image_per_person``, which hardcodes ``light_front.jpg`` (the La Salle
DB1 convention) and raises on LFW's arbitrary filenames. This script instead
replicates ``scripts/pipeline/run_lfw_independence.py::select_probes`` exactly -
same ``random.Random(seed)``, same sorted-identity iteration order, same
``rng.choice(files)`` per identity - so the hybrid test scores the *same*
per-identity probe images as the LBPH-only native-``predict_collect`` run
(``run_lfw_lbph_native_predict_independence.py``), which is what makes the two
runs' thresholds comparable.

The pre-existing ``docs/features/BATCH_WORK/selection_manifest_lfw1_hybrid.json``
is pinned to a *different* LFW copy (its ``source_root`` is the now-absent
``face-detection-g3/data/lfw-dataset``); every one of its SHA-256 entries
mismatches ``classical-cv/data/lfw-dataset``, so ``load_selection_manifest``
aborts. Regenerate against the copy actually being swept.

Usage::

    python scripts/archive/make_lfw_selection_manifest.py \
        --dataset-dir data/lfw-dataset --iterations 1 --random-seed 42 \
        --output docs/features/BATCH_WORK/selection_manifest_lfw1_classical.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "pipeline"))

from run_lfw_independence import select_probes  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default=str(PROJECT_ROOT / "data" / "lfw-dataset"))
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--max-identities", type=int, default=0)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()

    selections: dict[str, dict[str, str]] = {}
    sha256_map: dict[str, str] = {}
    for it in range(args.iterations):
        # Same seed offset convention as independence_test.main(): random_seed + it.
        probes = select_probes(dataset_dir, args.max_identities, args.random_seed + it)
        it_selection: dict[str, str] = {}
        for person, path, _extras in probes:
            relpath = Path(path).resolve().relative_to(dataset_dir).as_posix()
            it_selection[person] = relpath
            if relpath not in sha256_map:
                sha256_map[relpath] = sha256_file(dataset_dir / relpath)
        selections[str(it)] = it_selection
        print(f"[INFO] iteration {it}: {len(it_selection)} identities", flush=True)

    manifest = {
        "schema": "lsface-selection-manifest-v1",
        "seed": args.random_seed,
        "iterations": args.iterations,
        "n_identities": len(selections["0"]),
        "source_root": str(dataset_dir),
        "generator": "scripts/archive/make_lfw_selection_manifest.py "
                     "(replicates run_lfw_independence.select_probes)",
        "selections": selections,
        "sha256": sha256_map,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[SAVE] {out} ({len(sha256_map)} hashed files)")
    print(f"[SHA256] manifest itself: {sha256_file(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
