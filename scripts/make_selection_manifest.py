"""Kyle-side generator: pin the exact per-person image selection used by
``src.hybrid.independence_test`` so batch-campaign members can verify their
local dataset copy hash-matches what the test will pick, without anyone
distributing an augmented-dataset zip (see docs/BATCH_WORK/DESIGN.md Approach
B, section 6.2).

Reproduces the identity listing and per-iteration selection EXACTLY by
importing ``get_person_dirs`` / ``select_one_image_per_person`` from
``src.hybrid.independence_test`` (no reimplementation, no drift risk) and
replays the same seeded ``--max-identities`` subset logic the test applies
right before selection (independence_test.py, main(), around line 581).

Iteration key convention: the test's iteration loop is ``for it in
range(args.iterations)`` (0-based) and seeds each pick with
``args.random_seed + it``. This generator uses that SAME 0-based ``it`` as
the manifest's iteration key, because the key must match what the seed
offset actually is, not the 1-based "[ITERATION N/M]" console label or the
1-based ``run_{it+1}`` output-directory naming the test uses for humans.
Iteration 0 in this manifest == the test's first iteration, seeded with
``random_seed + 0``.

Output schema (v1), forward-slash relpaths relative to --dataset-dir:

    {
      "schema": "lsface-selection-manifest-v1",
      "seed": int,
      "iterations": int,
      "n_identities": int,
      "source_root": str,
      "selections": {"<iteration>": {"<identity>": "<relpath>"}},
      "sha256": {"<relpath>": "<hex>"}
    }
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import, don't reimplement: this is the same listing/selection code path
# src.hybrid.independence_test.main() runs. Importing the module has no
# side effects (its work happens behind `if __name__ == "__main__"`).
from src.hybrid.independence_test import get_person_dirs, select_one_image_per_person

DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "BATCH_WORK" / "selection_manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a pinned selection manifest matching "
                    "src.hybrid.independence_test's exact per-person image picks."
    )
    parser.add_argument("--dataset-dir", required=True,
                         help="Identity folders (e.g. data/lfw-dataset or data/lasalle_db1_processed).")
    parser.add_argument("--seed", type=int, default=42,
                         help="Must match independence_test.py's --random-seed default (42).")
    parser.add_argument("--iterations", type=int, default=1,
                         help="Must match the planned --iterations for the campaign.")
    parser.add_argument("--max-identities", type=int, default=0,
                         help="Same seeded-subset semantics as independence_test.py's "
                              "--max-identities (0 = all identities).")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                         help=f"Output manifest path (default {DEFAULT_OUTPUT}).")
    return parser.parse_args()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def to_relpath(abs_path: str, root: str) -> str:
    return os.path.relpath(abs_path, root).replace(os.sep, "/")


def main() -> int:
    args = parse_args()
    dataset_dir = str(Path(args.dataset_dir).resolve())

    person_dirs = get_person_dirs(dataset_dir)
    if len(person_dirs) < 2:
        print(f"[ERROR] Need >= 2 identity folders under {dataset_dir}.")
        return 1

    # Mirror independence_test.py main(), lines ~581-584 EXACTLY: same seed,
    # same random.Random(seed).sample, same sorted() re-order after sampling.
    if args.max_identities and len(person_dirs) > args.max_identities:
        import random
        subset_rng = random.Random(args.seed)
        person_dirs = sorted(subset_rng.sample(person_dirs, args.max_identities))
        print(f"[INFO] Seeded identity subset: {len(person_dirs)} of the available folders")

    n_identities = len(person_dirs)

    selections: dict[str, dict[str, str]] = {}
    sha256_map: dict[str, str] = {}

    for it in range(args.iterations):
        selected = select_one_image_per_person(person_dirs, args.seed + it)
        iter_entry: dict[str, str] = {}
        for person, abs_path in selected.items():
            relpath = to_relpath(abs_path, dataset_dir)
            iter_entry[person] = relpath
            if relpath not in sha256_map:
                sha256_map[relpath] = sha256_file(abs_path)
        selections[str(it)] = iter_entry
        print(f"[INFO] Iteration {it}: {len(iter_entry)} identities selected "
              f"(seed={args.seed + it})")

    manifest = {
        "schema": "lsface-selection-manifest-v1",
        "seed": args.seed,
        "iterations": args.iterations,
        "n_identities": n_identities,
        "source_root": dataset_dir,
        "selections": selections,
        "sha256": sha256_map,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    manifest_sha = sha256_file(str(output_path))

    print("\n[SUMMARY]")
    print(f"  n_identities   : {n_identities}")
    print(f"  iterations     : {args.iterations}")
    print(f"  files hashed   : {len(sha256_map)}")
    print(f"  manifest       : {output_path}")
    print(f"  manifest sha256: {manifest_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
