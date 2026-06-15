"""SFace recognizer + gallery + FAR model (ported from the DL track).

The math here is a verbatim port of ``face-detection-g3-dl/dnn.py`` and
``feature-extract.py``; nothing about the embedding or the match rule is changed:

* ``feature = recognizer.feature(recognizer.alignCrop(img_bgr, yunet_row))``
  yields a 128-D float32 embedding (**512 B**, satisfying the <1 KB spec LBPH's
  64 KB feature fails),
* ``cosine = recognizer.match(a, b, FR_COSINE)`` (higher is better),
  ``l2 = recognizer.match(a, b, FR_NORM_L2)`` (lower is better), and
* a pair is **genuine** iff ``cosine >= 0.363`` AND ``l2 <= 1.128``.

The gallery and FAR model give SFace the same surface LBPH exposes so the hybrid
gate can compare both engines through ``score()`` / ``far_of()`` instead of raw
scores (LBPH raw is a *distance*, SFace raw is a *cosine* - opposite directions).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2 as cv
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# --- Ported constants (do NOT change; these define the DL track's match rule) --
FR_COSINE = int(getattr(cv, "FaceRecognizerSF_FR_COSINE", 0))
FR_NORM_L2 = int(getattr(cv, "FaceRecognizerSF_FR_NORM_L2", 1))
COSINE_GENUINE_THRESHOLD = 0.363
L2_GENUINE_THRESHOLD = 1.128
SFACE_FEATURE_DIM = 128
SFACE_FEATURE_BYTES = SFACE_FEATURE_DIM * 4  # float32 => 512 bytes


def default_sface_model_path() -> str:
    return str(PROJECT_ROOT / "models" / "sface" / "face_recognition_sface_2021dec.onnx")


def detection_to_yunet_row(box, landmarks, score: float = 1.0) -> np.ndarray:
    """Rebuild the 15-value YuNet face row ``alignCrop`` expects.

    Layout: ``[x, y, w, h, re_x, re_y, le_x, le_y, nt_x, nt_y, rcm_x, rcm_y,
    lcm_x, lcm_y, score]`` - box, then the 5 landmarks (right eye, left eye,
    nose tip, right mouth corner, left mouth corner), then the score. This lets
    the offline/live hybrid feed a detector ``Detection`` straight into SFace.
    """
    x, y, w, h = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
    row = np.zeros(15, dtype=np.float32)
    row[0:4] = (x, y, w, h)
    if landmarks is not None:
        pts = np.asarray(landmarks, dtype=np.float32).reshape(-1)[:10]
        row[4 : 4 + pts.shape[0]] = pts
    else:
        # No landmarks: approximate canonical positions inside the box so
        # alignCrop still produces a centred crop rather than failing.
        row[4:14] = (
            x + 0.30 * w, y + 0.38 * h,  # right eye
            x + 0.70 * w, y + 0.38 * h,  # left eye
            x + 0.50 * w, y + 0.55 * h,  # nose tip
            x + 0.35 * w, y + 0.75 * h,  # right mouth corner
            x + 0.65 * w, y + 0.75 * h,  # left mouth corner
        )
    row[14] = float(score)
    return row


class SFaceRecognizer:
    """Thin wrapper over ``cv.FaceRecognizerSF`` (embedding + match only)."""

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or default_sface_model_path()
        if not Path(self.model_path).exists():
            raise FileNotFoundError(
                f"SFace model not found: {self.model_path}. Vendor "
                "face_recognition_sface_2021dec.onnx into models/sface/ (Phase 1/2)."
            )
        self._recognizer = cv.FaceRecognizerSF.create(self.model_path, "")

    # -- embedding ---------------------------------------------------------- #
    def feature_from_row(self, image_bgr: np.ndarray, yunet_row: np.ndarray) -> np.ndarray:
        """Canonical path: ``alignCrop`` to 112x112 then ``feature`` -> (1,128)."""
        aligned = self._recognizer.alignCrop(image_bgr, np.asarray(yunet_row, dtype=np.float32))
        return self._recognizer.feature(aligned)

    def feature_from_crop(self, crop_bgr: np.ndarray) -> np.ndarray:
        """Fallback when no detection row is available: resize to 112x112 then
        ``feature``. Less accurate than landmark alignment but keeps the system
        producing an embedding when YuNet misses on an already-cropped tile."""
        if crop_bgr.ndim == 2:
            crop_bgr = cv.cvtColor(crop_bgr, cv.COLOR_GRAY2BGR)
        resized = cv.resize(crop_bgr, (112, 112), interpolation=cv.INTER_AREA)
        return self._recognizer.feature(resized)

    # -- scoring ------------------------------------------------------------ #
    def match(self, feat_a: np.ndarray, feat_b: np.ndarray) -> tuple[float, float]:
        cosine = float(self._recognizer.match(feat_a, feat_b, FR_COSINE))
        l2 = float(self._recognizer.match(feat_a, feat_b, FR_NORM_L2))
        return cosine, l2

    @staticmethod
    def is_genuine(cosine: float, l2: float) -> bool:
        return (cosine >= COSINE_GENUINE_THRESHOLD) and (l2 <= L2_GENUINE_THRESHOLD)


@dataclass
class SFaceMatch:
    """Result of scoring one face against the SFace gallery."""

    name: str  # best identity, or "Unknown"
    cosine: float  # best cosine similarity (higher better)
    l2: float  # L2 distance to that best identity (lower better)
    accepted: bool  # passes the dual cosine/L2 genuine rule
    margin: float  # top-1 minus top-2 cosine (ambiguity signal)
    all_cosines: dict[str, float] = field(default_factory=dict)


class SFaceGallery:
    """Per-identity mean embedding store (mirrors the DL ``features-*.npy`` dict)."""

    def __init__(self, embeddings: dict[str, np.ndarray] | None = None) -> None:
        # name -> (1,128) float32 mean embedding
        self.embeddings: dict[str, np.ndarray] = {
            name: np.asarray(vec, dtype=np.float32).reshape(1, -1)
            for name, vec in (embeddings or {}).items()
        }

    @property
    def labels(self) -> list[str]:
        return sorted(self.embeddings.keys())

    @classmethod
    def from_samples(cls, recognizer: SFaceRecognizer, samples: dict[str, list[np.ndarray]]):
        """Average per-identity embeddings into the gallery (mean of unit features)."""
        embeddings: dict[str, np.ndarray] = {}
        for name, feats in samples.items():
            if not feats:
                continue
            stacked = np.vstack([np.asarray(f, dtype=np.float32).reshape(1, -1) for f in feats])
            embeddings[name] = stacked.mean(axis=0, keepdims=True).astype(np.float32)
        return cls(embeddings)

    def score(self, recognizer: SFaceRecognizer, feature: np.ndarray) -> SFaceMatch:
        if not self.embeddings:
            return SFaceMatch(name="Unknown", cosine=-1.0, l2=99.0, accepted=False, margin=0.0)
        cosines: dict[str, float] = {}
        l2s: dict[str, float] = {}
        for name, gallery_feat in self.embeddings.items():
            cosine, l2 = recognizer.match(gallery_feat, feature)
            cosines[name] = cosine
            l2s[name] = l2
        ranked = sorted(cosines.items(), key=lambda kv: kv[1], reverse=True)
        best_name, best_cos = ranked[0]
        second_cos = ranked[1][1] if len(ranked) > 1 else -1.0
        best_l2 = l2s[best_name]
        accepted = SFaceRecognizer.is_genuine(best_cos, best_l2)
        return SFaceMatch(
            name=best_name if accepted else "Unknown",
            cosine=best_cos,
            l2=best_l2,
            accepted=accepted,
            margin=float(best_cos - second_cos),
            all_cosines=cosines,
        )

    # -- persistence -------------------------------------------------------- #
    def save(self, gallery_path: str, labels_path: str) -> None:
        Path(gallery_path).parent.mkdir(parents=True, exist_ok=True)
        np.save(gallery_path, self.embeddings, allow_pickle=True)
        label_map = {name: idx for idx, name in enumerate(self.labels)}
        with open(labels_path, "w", encoding="utf-8") as f:
            json.dump(label_map, f, indent=2)

    @classmethod
    def load(cls, gallery_path: str):
        raw = np.load(gallery_path, allow_pickle=True).item()
        return cls(raw)


class SFaceFarModel:
    """Empirical false-accept-rate curve from an SFace impostor distribution.

    ``far_of(cosine)`` = fraction of impostor pairs whose cosine >= the query, so
    a higher cosine maps to a lower FAR. Built from the DL track's per-identity
    embeddings (the same ``features-*.npy`` independence inputs) by computing the
    off-diagonal pairwise cosines.
    """

    def __init__(self, impostor_cosines: np.ndarray) -> None:
        self.sorted_cosines = np.sort(np.asarray(impostor_cosines, dtype=np.float32))
        self.count = int(self.sorted_cosines.shape[0])

    @classmethod
    def from_features_npy(
        cls,
        path: str,
        *,
        max_identities: int = 2500,
        random_seed: int = 1234,
    ) -> "SFaceFarModel":
        feats = _load_feature_matrix(path)
        if feats.shape[0] > max_identities:
            rng = np.random.default_rng(random_seed)
            idx = rng.choice(feats.shape[0], size=max_identities, replace=False)
            feats = feats[idx]
        # Cosine via normalised matrix product; keep the strict upper triangle
        # (each unordered impostor pair once).
        norm = feats / (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-9)
        sim = norm @ norm.T
        iu = np.triu_indices(sim.shape[0], k=1)
        return cls(sim[iu].astype(np.float32))

    def far_of(self, cosine: float) -> float:
        if self.count == 0:
            return 1.0
        # Number of impostor cosines >= the query, as a fraction.
        idx = int(np.searchsorted(self.sorted_cosines, float(cosine), side="left"))
        ge = self.count - idx
        return max(0.0, min(1.0, ge / self.count))

    def cosine_at_far(self, target_far: float) -> float:
        """Smallest cosine whose impostor FAR <= ``target_far`` (operating point)."""
        if self.count == 0:
            return COSINE_GENUINE_THRESHOLD
        k = int(np.ceil(target_far * self.count))
        k = max(1, min(self.count, k))
        # The k-th largest impostor cosine is the threshold giving ~target_far.
        return float(self.sorted_cosines[self.count - k])


def _load_feature_matrix(path: str) -> np.ndarray:
    """Load a DL ``features-*.npy`` (dict{name:feat} or list[{person,feature}])
    into an ``(N, 128)`` matrix of per-identity embeddings."""
    obj = np.load(path, allow_pickle=True)
    try:
        data = obj.item()
    except (ValueError, AttributeError):
        data = obj.tolist()

    if isinstance(data, dict):
        rows = [np.asarray(v, dtype=np.float32).reshape(-1) for v in data.values()]
        return np.vstack(rows)

    # list of dicts -> collapse to one mean embedding per person so the impostor
    # cosines are identity-vs-identity (not image-vs-image).
    by_person: dict[str, list[np.ndarray]] = {}
    for entry in data:
        by_person.setdefault(entry["person"], []).append(
            np.asarray(entry["feature"], dtype=np.float32).reshape(-1)
        )
    rows = [np.mean(np.vstack(v), axis=0) for v in by_person.values()]
    return np.vstack(rows)
