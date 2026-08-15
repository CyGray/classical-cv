"""Provenance and SVG checks for canonical LSDB-DL41 complementarity figures.

The recovery-rate and gate-competence manuscript figures are intentionally
redrawn from recorded canonical evidence rather than copied from historical
result artwork.  This module is the single contract those figure scripts use
to reject a changed, non-canonical, or unreviewed input before drawing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CAMPAIGN = "lsdb_dl41_2026-08-10"
CANONICAL_CAMPAIGN_RELATIVE = (
    "complementarity_test/reruns/" + CANONICAL_CAMPAIGN
)
RESULTS_ROOT = WORKSPACE_ROOT / "docs" / "results"
MANIFEST_PATH = RESULTS_ROOT / "RESULTS_MANIFEST.json"
RUN_PROVENANCE_RELATIVE = f"{CANONICAL_CAMPAIGN_RELATIVE}/run_provenance.json"
RECOVERY_SOURCE_RELATIVE = f"{CANONICAL_CAMPAIGN_RELATIVE}/complementarity_probes.csv"
GATE_SOURCE_RELATIVE = f"{CANONICAL_CAMPAIGN_RELATIVE}/accuracy_ratio_hybrid.json"


class CanonicalComplementarityError(RuntimeError):
    """Raised when a requested manuscript figure no longer has canonical inputs."""


@dataclass(frozen=True)
class CanonicalSource:
    """A manifest- and provenance-verified source artifact."""

    relative_path: str
    path: Path
    sha256: str
    source_git_commit_at: str


def canonical_source_path(relative_path: str) -> Path:
    """Resolve a known canonical result path from the workspace root."""

    return RESULTS_ROOT / Path(relative_path)


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of one file without loading it all."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_canonical_source(source: Path, expected_relative_path: str) -> CanonicalSource:
    """Validate one exact LSDB-DL41 source against manifest and run provenance.

    The figure scripts deliberately do not accept arbitrary CSV/JSON files.
    A different campaign needs an explicit script/contract review rather than
    silently producing publication-looking artwork from a new population.
    """

    expected_path = canonical_source_path(expected_relative_path)
    if not source.is_file():
        raise CanonicalComplementarityError(f"Source artifact is missing: {source}")
    if not expected_path.is_file():
        raise CanonicalComplementarityError(
            f"Canonical source artifact is missing: {expected_path}"
        )
    if source.resolve() != expected_path.resolve():
        raise CanonicalComplementarityError(
            "This figure is pinned to the canonical LSDB-DL41 artifact "
            f"'{expected_relative_path}', not '{source}'."
        )

    manifest = _load_json(MANIFEST_PATH)
    artifact = _verified_manifest_artifact(manifest, expected_relative_path)
    provenance_artifact = _verified_manifest_artifact(manifest, RUN_PROVENANCE_RELATIVE)
    provenance_path = canonical_source_path(RUN_PROVENANCE_RELATIVE)
    if sha256_file(provenance_path) != provenance_artifact["sha256"]:
        raise CanonicalComplementarityError(
            "The canonical run_provenance.json checksum differs from the results manifest."
        )

    observed_sha256 = sha256_file(expected_path)
    if observed_sha256 != artifact["sha256"]:
        raise CanonicalComplementarityError(
            "The canonical source checksum differs from the results manifest: "
            f"{expected_relative_path}."
        )

    provenance = _load_json(provenance_path)
    if provenance.get("campaign") != CANONICAL_CAMPAIGN:
        raise CanonicalComplementarityError(
            "run_provenance.json does not identify the expected LSDB-DL41 campaign."
        )
    if provenance.get("status") != "canonical_snapshot":
        raise CanonicalComplementarityError(
            "run_provenance.json is not marked canonical_snapshot."
        )
    artifact_hashes = provenance.get("artifact_sha256")
    if not isinstance(artifact_hashes, Mapping):
        raise CanonicalComplementarityError(
            "run_provenance.json does not provide source artifact checksums."
        )
    provenance_sha256 = _normalise_sha256(
        artifact_hashes.get(expected_path.name),
        f"run provenance checksum for {expected_path.name}",
    )
    if provenance_sha256 != observed_sha256:
        raise CanonicalComplementarityError(
            "The canonical source checksum differs from run_provenance.json: "
            f"{expected_relative_path}."
        )
    source_git_commit_at = provenance.get("source_git_commit_at")
    if not isinstance(source_git_commit_at, str) or not source_git_commit_at.strip():
        raise CanonicalComplementarityError(
            "run_provenance.json lacks source_git_commit_at for deterministic SVG metadata."
        )

    return CanonicalSource(
        relative_path=expected_relative_path,
        path=expected_path,
        sha256=observed_sha256,
        source_git_commit_at=source_git_commit_at,
    )


def canonical_svg_metadata(
    source: CanonicalSource,
    *,
    title: str,
    description: str,
) -> dict[str, str]:
    """Return deterministic SVG metadata tied to one canonical evidence file."""

    return {
        "Title": title,
        "Description": description,
        "Date": source.source_git_commit_at,
        "Source": source.relative_path,
        "Identifier": f"sha256:{source.sha256}",
    }


def verify_editable_svg(
    output: Path,
    *,
    source: CanonicalSource,
    required_text: Iterable[str],
) -> None:
    """Reject malformed, raster-backed, or semantically incomplete SVG output."""

    if not output.is_file():
        raise CanonicalComplementarityError(f"Expected SVG was not written: {output}")
    if output.suffix.lower() != ".svg":
        raise CanonicalComplementarityError(f"Expected an SVG output, got: {output}")

    contents = output.read_text(encoding="utf-8")
    try:
        root = ElementTree.fromstring(contents)
    except ElementTree.ParseError as error:
        raise CanonicalComplementarityError(f"Generated SVG is malformed: {output}") from error

    if _local_name(root.tag) != "svg":
        raise CanonicalComplementarityError(f"Generated file is not an SVG document: {output}")
    names = [_local_name(element.tag) for element in root.iter()]
    if "image" in names:
        raise CanonicalComplementarityError(
            f"Generated figure embeds a raster image instead of editable SVG artwork: {output}"
        )
    if "text" not in names:
        raise CanonicalComplementarityError(
            f"Generated figure has no editable SVG text elements: {output}"
        )
    for text in required_text:
        if text not in contents:
            raise CanonicalComplementarityError(
                f"Generated figure is missing required text '{text}': {output}"
            )
    if source.relative_path not in contents or source.sha256 not in contents:
        raise CanonicalComplementarityError(
            f"Generated figure is missing canonical source metadata: {output}"
        )
    if source.source_git_commit_at not in contents:
        raise CanonicalComplementarityError(
            f"Generated figure is missing deterministic source-date metadata: {output}"
        )


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CanonicalComplementarityError(
            f"Could not read canonical provenance file: {path}"
        ) from error
    if not isinstance(value, Mapping):
        raise CanonicalComplementarityError(f"Expected a JSON object in: {path}")
    return value


def _verified_manifest_artifact(
    manifest: Mapping[str, Any], relative_path: str
) -> dict[str, Any]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise CanonicalComplementarityError("RESULTS_MANIFEST.json does not contain an artifacts list.")
    matches = [item for item in artifacts if isinstance(item, Mapping) and item.get("path") == relative_path]
    if len(matches) != 1:
        raise CanonicalComplementarityError(
            "RESULTS_MANIFEST.json must contain exactly one record for "
            f"'{relative_path}', found {len(matches)}."
        )
    artifact = dict(matches[0])
    if artifact.get("status") != "canonical_snapshot":
        raise CanonicalComplementarityError(
            f"'{relative_path}' is not a canonical_snapshot artifact."
        )
    if artifact.get("rerun_required") is not False:
        raise CanonicalComplementarityError(
            f"'{relative_path}' is marked rerun_required in RESULTS_MANIFEST.json."
        )
    artifact["sha256"] = _normalise_sha256(
        artifact.get("sha256"), f"manifest checksum for {relative_path}"
    )
    return artifact


def _normalise_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise CanonicalComplementarityError(f"Missing {label}.")
    normalised = value.strip().lower()
    if len(normalised) != 64 or any(character not in "0123456789abcdef" for character in normalised):
        raise CanonicalComplementarityError(f"Invalid {label}: {value!r}.")
    return normalised


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
