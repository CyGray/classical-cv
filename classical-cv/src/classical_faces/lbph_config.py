"""Central LBPH descriptor profiles and native recognizer factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LBPHConfig:
    config_id: str
    radius: int
    neighbors: int
    grid_x: int
    grid_y: int

    @property
    def id(self) -> str:
        return self.config_id

    @property
    def token(self) -> str:
        return self.config_id

    @property
    def params(self) -> dict[str, int]:
        return {
            "radius": self.radius,
            "neighbors": self.neighbors,
            "grid_x": self.grid_x,
            "grid_y": self.grid_y,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"config_id": self.config_id, **self.params}

    @property
    def descriptor_bytes(self) -> int:
        return self.grid_x * self.grid_y * (2 ** self.neighbors) * 4


DEPLOYED_LBPH_CONFIG = LBPHConfig("r1_n8_g8x8", 1, 8, 8, 8)
SELECTED_LBPH_CONFIG = LBPHConfig("r3_n8_g6x6", 3, 8, 6, 6)
ACTIVE_LBPH_CONFIG = DEPLOYED_LBPH_CONFIG

# Short aliases are part of the central rollout contract. Keep the verbose
# names above for callers that prefer explicitness.
DEPLOYED = DEPLOYED_LBPH_CONFIG
SELECTED = SELECTED_LBPH_CONFIG
ACTIVE = ACTIVE_LBPH_CONFIG

LBPH_CONFIG_BY_ID = {
    config.config_id: config
    for config in (DEPLOYED_LBPH_CONFIG, SELECTED_LBPH_CONFIG)
}
LBPH_CONFIGS = LBPH_CONFIG_BY_ID


def resolve_lbph_config(selector: str | LBPHConfig | None = None) -> LBPHConfig:
    if selector is None or selector in ("", "active", "deployed"):
        return ACTIVE_LBPH_CONFIG if selector != "deployed" else DEPLOYED_LBPH_CONFIG
    if isinstance(selector, LBPHConfig):
        return selector
    if selector == "selected":
        return SELECTED_LBPH_CONFIG
    try:
        return LBPH_CONFIG_BY_ID[selector]
    except KeyError as exc:
        raise ValueError(f"Unknown LBPH config {selector!r}") from exc


def create_lbph_recognizer(config: str | LBPHConfig | None = None):
    import cv2 as cv

    resolved = resolve_lbph_config(config)
    return cv.face.LBPHFaceRecognizer_create(**resolved.params)
