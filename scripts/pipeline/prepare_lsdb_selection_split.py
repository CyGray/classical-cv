"""Create deterministic fit/calibration folders for LSDB model selection.

The untouched `test` split is never copied here.  Candidate-model thresholds
must be fitted on `calibration`, then evaluated once on `test`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--calibration-per-identity", type=int, default=2)
    args = p.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    identities = sorted(x for x in source.iterdir() if x.is_dir())
    if not identities:
        raise SystemExit(f"No identity folders: {source}")
    manifest: dict[str, object] = {"source": str(source), "identities": {}}
    for identity in identities:
        images = sorted(x for x in identity.iterdir() if x.is_file())
        n = args.calibration_per_identity
        if len(images) <= n:
            raise SystemExit(f"{identity.name}: need > {n} images")
        # Stable filename split: last n files = calibration; rest = fit.
        fit, calibration = images[:-n], images[-n:]
        for bucket, items in (("fit", fit), ("calibration", calibration)):
            dst = output / bucket / identity.name
            dst.mkdir(parents=True, exist_ok=True)
            for image in items:
                shutil.copy2(image, dst / image.name)
        manifest["identities"][identity.name] = {
            "fit": [x.name for x in fit],
            "calibration": [x.name for x in calibration],
        }
    manifest["source_sha256"] = digest([p for d in identities for p in sorted(d.iterdir()) if p.is_file()])
    (output / "split_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
