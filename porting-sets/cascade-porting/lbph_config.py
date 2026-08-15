"""Shared, standalone-safe LBPH descriptor profiles for the Pi bundle.

The serialized OpenCV model is the final authority for the parameters used at
runtime.  The profile helpers in this module provide the expected release
metadata and make the post-``read`` comparison explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


DEPLOYED_PROFILE = "deployed"
SELECTED_PROFILE = "selected"


@dataclass(frozen=True)
class LBPHDescriptor:
    """A stable LBPH configuration identifier and its OpenCV parameters."""

    descriptor_id: str
    radius: int
    neighbors: int
    grid_x: int
    grid_y: int

    def __post_init__(self) -> None:
        expected_id = format_descriptor_id(
            self.radius, self.neighbors, self.grid_x, self.grid_y
        )
        if self.descriptor_id != expected_id:
            raise ValueError(
                f"Descriptor id {self.descriptor_id!r} does not match "
                f"its parameters ({expected_id})."
            )
        if min(self.radius, self.neighbors, self.grid_x, self.grid_y) <= 0:
            raise ValueError("LBPH radius, neighbors, and grid dimensions must be positive.")

    def to_dict(self) -> dict[str, int | str]:
        """Return the stable manifest/threshold representation."""

        return {
            "id": self.descriptor_id,
            "radius": self.radius,
            "neighbors": self.neighbors,
            "grid_x": self.grid_x,
            "grid_y": self.grid_y,
        }


def format_descriptor_id(radius: int, neighbors: int, grid_x: int, grid_y: int) -> str:
    """Build the stable ID used in release and threshold metadata."""

    if grid_x == grid_y:
        grid = f"{grid_x}x{grid_y}"
    else:
        grid = f"{grid_x}x{grid_y}"
    return f"r{radius}_n{neighbors}_g{grid}"


DEPLOYED_DESCRIPTOR = LBPHDescriptor(
    descriptor_id="r1_n8_g8x8",
    radius=1,
    neighbors=8,
    grid_x=8,
    grid_y=8,
)
SELECTED_DESCRIPTOR = LBPHDescriptor(
    descriptor_id="r3_n8_g6x6",
    radius=3,
    neighbors=8,
    grid_x=6,
    grid_y=6,
)

DESCRIPTOR_PROFILES = {
    DEPLOYED_PROFILE: DEPLOYED_DESCRIPTOR,
    SELECTED_PROFILE: SELECTED_DESCRIPTOR,
}
DESCRIPTORS_BY_ID = {
    descriptor.descriptor_id: descriptor for descriptor in DESCRIPTOR_PROFILES.values()
}

# Compatibility names shared with the central classical-CV rollout API. The
# Pi bundle remains standalone, but these aliases keep its contract familiar to
# callers that consume the central descriptor metadata.
DEPLOYED_LBPH_CONFIG = DEPLOYED_DESCRIPTOR
SELECTED_LBPH_CONFIG = SELECTED_DESCRIPTOR
ACTIVE_LBPH_CONFIG = DEPLOYED_DESCRIPTOR
LBPH_CONFIG_BY_ID = DESCRIPTORS_BY_ID


def resolve_descriptor(profile_or_id: str | LBPHDescriptor) -> LBPHDescriptor:
    """Resolve a profile name or stable descriptor ID."""

    if isinstance(profile_or_id, LBPHDescriptor):
        return profile_or_id
    key = str(profile_or_id).strip().lower()
    descriptor = DESCRIPTOR_PROFILES.get(key) or DESCRIPTORS_BY_ID.get(key)
    if descriptor is None:
        choices = ", ".join(sorted((*DESCRIPTOR_PROFILES, *DESCRIPTORS_BY_ID)))
        raise ValueError(f"Unknown LBPH descriptor profile {profile_or_id!r}; choose {choices}.")
    return descriptor


def resolve_lbph_config(selector: str | LBPHDescriptor | None = None) -> LBPHDescriptor:
    """Central-API spelling for resolving active/deployed/selected profiles."""

    if selector is None or selector == "" or selector == "active":
        return ACTIVE_LBPH_CONFIG
    return resolve_descriptor(selector)


def lbph_config_id(config: str | LBPHDescriptor) -> str:
    """Return the stable ID through the central-API spelling."""

    return resolve_descriptor(config).descriptor_id


def lbph_config_metadata(config: str | LBPHDescriptor) -> dict[str, int | str]:
    """Return JSON-safe descriptor metadata through the central API."""

    return resolve_descriptor(config).to_dict()


def descriptor_from_mapping(
    payload: Mapping[str, Any] | None, *, source: str = "metadata"
) -> LBPHDescriptor:
    """Parse and cross-check descriptor metadata from JSON."""

    if not isinstance(payload, Mapping):
        raise ValueError(f"{source} must contain an 'lbph_descriptor' object.")
    descriptor_id = payload.get("id", payload.get("descriptor_id"))
    required = ("radius", "neighbors", "grid_x", "grid_y")
    missing = [key for key in required if key not in payload]
    if descriptor_id is None or missing:
        details = f"missing id" if descriptor_id is None else ""
        if missing:
            details = f"{details}{'; ' if details else ''}missing {', '.join(missing)}"
        raise ValueError(f"Invalid LBPH descriptor metadata in {source}: {details}.")
    try:
        params = {key: int(payload[key]) for key in required}
    except (TypeError, ValueError) as error:
        raise ValueError(f"LBPH descriptor parameters in {source} must be integers.") from error
    try:
        return LBPHDescriptor(str(descriptor_id), **params)
    except ValueError as error:
        raise ValueError(f"Invalid LBPH descriptor metadata in {source}: {error}") from error


def make_lbph(profile_or_descriptor: str | LBPHDescriptor = DEPLOYED_PROFILE):
    """Create an OpenCV recognizer with the expected constructor parameters."""

    import cv2 as cv

    descriptor = resolve_descriptor(profile_or_descriptor)
    return cv.face.LBPHFaceRecognizer_create(
        radius=descriptor.radius,
        neighbors=descriptor.neighbors,
        grid_x=descriptor.grid_x,
        grid_y=descriptor.grid_y,
    )


def create_lbph_recognizer(
    config: str | LBPHDescriptor | None = None,
):
    """Central-API spelling for the standalone LBPH factory."""

    return make_lbph(resolve_lbph_config(config))


def inspect_lbph(recognizer: Any) -> LBPHDescriptor:
    """Inspect the parameters OpenCV restored from a recognizer/model."""

    getter_names = {
        "radius": "getRadius",
        "neighbors": "getNeighbors",
        "grid_x": "getGridX",
        "grid_y": "getGridY",
    }
    missing = [name for name in getter_names.values() if not hasattr(recognizer, name)]
    if missing:
        raise RuntimeError(
            "LBPH recognizer does not expose serialized descriptor getters: "
            + ", ".join(missing)
        )
    values = {key: int(getattr(recognizer, getter)()) for key, getter in getter_names.items()}
    descriptor_id = format_descriptor_id(**values)
    return LBPHDescriptor(descriptor_id=descriptor_id, **values)


def validate_descriptor_metadata(
    expected: str | LBPHDescriptor,
    observed: LBPHDescriptor,
    *,
    context: str,
) -> LBPHDescriptor:
    """Fail clearly when a release/model is not compatible with its metadata."""

    expected_descriptor = resolve_descriptor(expected)
    if observed != expected_descriptor:
        raise RuntimeError(
            f"LBPH descriptor mismatch for {context}: expected "
            f"{expected_descriptor.descriptor_id} "
            f"(radius={expected_descriptor.radius}, neighbors={expected_descriptor.neighbors}, "
            f"grid={expected_descriptor.grid_x}x{expected_descriptor.grid_y}), observed "
            f"{observed.descriptor_id} "
            f"(radius={observed.radius}, neighbors={observed.neighbors}, "
            f"grid={observed.grid_x}x{observed.grid_y}). "
            "OpenCV read() restores the serialized parameters; use a matching "
            "release and calibrated thresholds."
        )
    return observed


def release_descriptor_from_manifest(
    manifest: Mapping[str, Any],
    threshold_descriptor: str | LBPHDescriptor,
    *,
    source: str = "release manifest",
) -> tuple[LBPHDescriptor, bool]:
    """Resolve release metadata, accepting older metadata-free manifests.

    Returns ``(descriptor, is_legacy_manifest)``. A legacy manifest has no
    descriptor fields at all, so the threshold descriptor is the compatibility
    authority; malformed or contradictory descriptor fields still fail.
    """

    if not isinstance(manifest, Mapping):
        raise ValueError(f"{source} must contain a JSON object.")
    has_descriptor_fields = "lbph_descriptor" in manifest or "descriptor_id" in manifest
    expected = resolve_descriptor(threshold_descriptor)
    if not has_descriptor_fields:
        return expected, True

    descriptor = descriptor_from_mapping(
        manifest.get("lbph_descriptor"), source=source
    )
    manifest_id = manifest.get("descriptor_id")
    if manifest_id != descriptor.descriptor_id:
        raise ValueError(
            f"descriptor_id {manifest_id!r} does not match "
            f"lbph_descriptor.id {descriptor.descriptor_id!r}"
        )
    validate_descriptor_metadata(expected, descriptor, context=source)
    return descriptor, False


def validate_loaded_lbph(
    recognizer: Any,
    expected: str | LBPHDescriptor,
    *,
    context: str,
) -> LBPHDescriptor:
    """Inspect a loaded model and validate it against release metadata."""

    observed = inspect_lbph(recognizer)
    return validate_descriptor_metadata(expected, observed, context=context)
