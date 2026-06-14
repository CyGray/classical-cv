"""Optional/backup variant matchers for the classical recognizers.

These do NOT replace the deployed OpenCV recognizers - they are opt-in
alternatives benchmarked side by side (``scripts/compare_variants.py``):

* **CompactLBPH** - implements ``docs/SUGGESTION.md`` ("focus only on the
  specific features like eyes, eyebrow, nose, and mouth" / keep only the
  important parts of the feature and discard the rest). The 64 KB LBPH
  histogram (8x8 cells x 256 bins x float32) is reduced to a byte budget by
  (a) optionally restricting to the facial-landmark grid cells and
  (b) ranking the remaining dimensions by Fisher score on the training set and
  keeping the top-K that fit the budget; optional uint8 quantization trades
  per-dimension precision for 4x more dimensions. Matching is chi-square
  against per-identity centroid templates (or all training templates).

* **SubspaceMatcher** - accuracy-upgrade options for Eigen/Fisherfaces on
  their native projections: drop the first PCA components (illumination),
  whiten by eigenvalues (Mahalanobis), cosine distance, and per-identity
  centroid galleries. Feature bytes = retained components x 4 B, unchanged.

Both consume features extracted from the *standard* trained OpenCV models via
the same round-trip readers the independence tests use, so the underlying
representation stays identical to the deployed pipeline.
"""

import os
import tempfile
from dataclasses import dataclass, field

import cv2 as cv
import numpy as np

from src.independence_common import _read_lbph_histograms

LBPH_GRID = 8
LBPH_BINS = 256
LBPH_DIM = LBPH_GRID * LBPH_GRID * LBPH_BINS  # 16384


# --------------------------------------------------------------------------- #
# Feature extraction (batch round-trips through OpenCV, exact representations)
# --------------------------------------------------------------------------- #
def lbph_histograms_from_tiles(tiles: list[np.ndarray], batch: int = 250) -> np.ndarray:
    """Exact OpenCV LBPH histograms (radius 1, 8 neighbours, 8x8 grid), float32.

    Round-trips through XML, not YAML: cv2's YAML parser intermittently fails
    on large LBPH model files (persistence_yml "Parsing error", data-dependent).
    Batches stay capped so a single temp model never grows unwieldy.
    """
    batch = max(1, min(int(batch), 250))
    feats: list[np.ndarray] = []
    for start in range(0, len(tiles), batch):
        chunk = tiles[start: start + batch]
        model = cv.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        model.train(chunk, np.arange(len(chunk), dtype=np.int32))
        tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
        tmp.close()
        try:
            model.save(tmp.name)
            histograms, _ = _read_lbph_histograms(tmp.name)
        finally:
            os.unlink(tmp.name)
        feats.extend(h.astype(np.float32) for h in histograms)
    return np.stack(feats, axis=0)


def read_subspace_model(model_path: str, root_key: str):
    """(eigenvectors DxK, mean 1xD, eigenvalues K, projections NxK, labels N)."""
    fs = cv.FileStorage(model_path, cv.FILE_STORAGE_READ)
    root = fs.getNode(root_key)
    eigenvectors = np.asarray(root.getNode("eigenvectors").mat(), dtype=np.float64)
    mean = np.asarray(root.getNode("mean").mat(), dtype=np.float64).reshape(1, -1)
    eigenvalues = np.asarray(root.getNode("eigenvalues").mat(), dtype=np.float64).reshape(-1)
    proj_node = root.getNode("projections")
    projections = np.stack(
        [proj_node.at(i).mat().flatten() for i in range(proj_node.size())], axis=0
    ).astype(np.float64)
    labels = root.getNode("labels").mat().flatten().astype(np.int32)
    fs.release()
    return eigenvectors, mean, eigenvalues, projections, labels


# --------------------------------------------------------------------------- #
# Dimension selection
# --------------------------------------------------------------------------- #
def fisher_scores(features: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Per-dimension Fisher score: between-class variance / within-class variance."""
    overall_mean = features.mean(axis=0)
    classes = np.unique(labels)
    between = np.zeros(features.shape[1], dtype=np.float64)
    within = np.zeros(features.shape[1], dtype=np.float64)
    for c in classes:
        rows = features[labels == c]
        mu = rows.mean(axis=0)
        between += rows.shape[0] * (mu - overall_mean) ** 2
        within += ((rows - mu) ** 2).sum(axis=0)
    return between / (within + 1e-9)


def landmark_cell_mask() -> np.ndarray:
    """Boolean mask over the 16384 LBPH dims keeping eyebrow/eye, nose and mouth
    grid cells of the 8x8 layout (tiles are pre-centered 100x100 face crops).

    Rows 2-3 cols 1-6 (eyebrows+eyes), rows 4-5 cols 2-5 (nose), rows 6 cols 2-5
    (mouth) -> 24 of 64 cells. OpenCV concatenates cell histograms row-major, so
    dim index = (row * 8 + col) * 256 + bin.
    """
    keep = np.zeros(LBPH_DIM, dtype=bool)
    cells: list[tuple[int, int]] = []
    cells += [(r, c) for r in (2, 3) for c in range(1, 7)]   # eyebrows + eyes
    cells += [(r, c) for r in (4, 5) for c in range(2, 6)]   # nose / upper cheeks
    cells += [(6, c) for c in range(2, 6)]                   # mouth
    for r, c in cells:
        start = (r * LBPH_GRID + c) * LBPH_BINS
        keep[start: start + LBPH_BINS] = True
    return keep


def chi2_to_templates(query: np.ndarray, templates: np.ndarray) -> np.ndarray:
    diff = templates - query
    return 0.5 * np.sum((diff * diff) / (templates + query + 1e-10), axis=1)


# --------------------------------------------------------------------------- #
# Compact LBPH (SUGGESTION.md variant)
# --------------------------------------------------------------------------- #
@dataclass
class CompactLBPH:
    budget_bytes: int = 960
    dtype: str = "float32"            # float32 (K = budget/4) or uint8 (K = budget)
    restrict_to_landmarks: bool = False
    gallery: str = "centroid"          # centroid | all
    selected_dims: np.ndarray = field(default=None, repr=False)
    templates: np.ndarray = field(default=None, repr=False)
    template_labels: np.ndarray = field(default=None, repr=False)
    quant_scale: float = 1.0

    @property
    def n_dims(self) -> int:
        return self.budget_bytes // (4 if self.dtype == "float32" else 1)

    @property
    def feature_bytes(self) -> int:
        return int(self.n_dims * (4 if self.dtype == "float32" else 1))

    @property
    def template_store_bytes(self) -> int:
        return int(self.templates.shape[0] * self.feature_bytes)

    def _reduce(self, hists: np.ndarray) -> np.ndarray:
        x = hists[:, self.selected_dims]
        if self.dtype == "uint8":
            x = np.clip(np.round(x * self.quant_scale), 0, 255)
        return x.astype(np.float32)

    def fit(self, train_hists: np.ndarray, train_labels: np.ndarray) -> "CompactLBPH":
        scores = fisher_scores(train_hists, train_labels)
        if self.restrict_to_landmarks:
            scores = np.where(landmark_cell_mask(), scores, -np.inf)
        k = min(self.n_dims, int(np.isfinite(scores).sum()))
        self.selected_dims = np.sort(np.argsort(scores)[::-1][:k])
        if self.dtype == "uint8":
            vmax = float(train_hists[:, self.selected_dims].max())
            self.quant_scale = 255.0 / max(vmax, 1e-9)

        reduced = self._reduce(train_hists)
        if self.gallery == "centroid":
            classes = np.unique(train_labels)
            self.templates = np.stack(
                [reduced[train_labels == c].mean(axis=0) for c in classes], axis=0
            )
            self.template_labels = classes
        else:
            self.templates = reduced
            self.template_labels = train_labels.copy()
        return self

    def predict_batch(self, hists: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(predicted labels, distances) for each row of ``hists``."""
        reduced = self._reduce(hists)
        labels_out = np.empty(reduced.shape[0], dtype=np.int32)
        dists_out = np.empty(reduced.shape[0], dtype=np.float64)
        for i, q in enumerate(reduced):
            d = chi2_to_templates(q, self.templates)
            j = int(np.argmin(d))
            labels_out[i] = self.template_labels[j]
            dists_out[i] = d[j]
        return labels_out, dists_out

    def describe(self) -> str:
        area = "landmarks" if self.restrict_to_landmarks else "all-cells"
        return f"top{self.n_dims}-{area}-{self.dtype}-{self.gallery}"


# --------------------------------------------------------------------------- #
# Subspace (Eigen/Fisher) matcher variants
# --------------------------------------------------------------------------- #
@dataclass
class SubspaceMatcher:
    eigenvectors: np.ndarray          # D x K
    mean: np.ndarray                  # 1 x D
    eigenvalues: np.ndarray           # K
    train_projections: np.ndarray     # N x K
    train_labels: np.ndarray          # N
    drop_first: int = 0
    distance: str = "l2"              # l2 | cosine | whiten-l2 | whiten-cosine
    gallery: str = "nn"               # nn | centroid
    templates: np.ndarray = field(default=None, repr=False)
    template_labels: np.ndarray = field(default=None, repr=False)

    def __post_init__(self):
        k = self.drop_first
        self._scale = 1.0 / np.sqrt(np.maximum(self.eigenvalues[k:], 1e-9))
        gallery_feats = self._transform_projection(self.train_projections)
        if self.gallery == "centroid":
            classes = np.unique(self.train_labels)
            self.templates = np.stack(
                [gallery_feats[self.train_labels == c].mean(axis=0) for c in classes], axis=0
            )
            self.template_labels = classes
        else:
            self.templates = gallery_feats
            self.template_labels = self.train_labels.copy()

    @property
    def n_components(self) -> int:
        return int(self.eigenvectors.shape[1] - self.drop_first)

    @property
    def feature_bytes(self) -> int:
        return self.n_components * 4

    @property
    def template_store_bytes(self) -> int:
        return int(self.templates.shape[0] * self.feature_bytes)

    def _transform_projection(self, proj: np.ndarray) -> np.ndarray:
        x = proj[:, self.drop_first:]
        if self.distance.startswith("whiten"):
            x = x * self._scale
        if self.distance.endswith("cosine"):
            x = x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)
        return x

    def project_tiles(self, tiles: list[np.ndarray]) -> np.ndarray:
        data = np.stack([t.reshape(-1) for t in tiles], axis=0).astype(np.float64)
        return (data - self.mean) @ self.eigenvectors

    def predict_batch(self, projections: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        feats = self._transform_projection(projections)
        labels_out = np.empty(feats.shape[0], dtype=np.int32)
        dists_out = np.empty(feats.shape[0], dtype=np.float64)
        for i, q in enumerate(feats):
            diff = self.templates - q
            d = np.sqrt(np.einsum("ij,ij->i", diff, diff))
            j = int(np.argmin(d))
            labels_out[i] = self.template_labels[j]
            dists_out[i] = d[j]
        return labels_out, dists_out

    def describe(self) -> str:
        drop = f"drop{self.drop_first}" if self.drop_first else "drop0"
        return f"{self.n_components}c-{drop}-{self.distance}-{self.gallery}"
