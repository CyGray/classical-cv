"""Backward-compatible shim.

The real preprocessing now lives in :mod:`src.classical_faces.preprocess` so all
three classical recognizers share one implementation. This module re-exports it
(plus the historical ``extract_lbph_face`` name) so existing imports such as::

    from src.lbph.preprocess import IMG_SIZE, extract_lbph_face, normalize_face

keep working unchanged (independence tests, detect.py, benchmark scripts).
"""

from src.classical_faces.preprocess import (
    IMG_SIZE,
    FacePreprocessResult,
    align_face_by_eyes,
    detect_largest_face_box,
    extract_classical_face,
    maybe_downscale,
    normalize_face,
    resolve_eye_cascade_path,
)

# Historical name kept for callers written against the LBPH-only module.
extract_lbph_face = extract_classical_face

__all__ = [
    "IMG_SIZE",
    "FacePreprocessResult",
    "align_face_by_eyes",
    "detect_largest_face_box",
    "extract_classical_face",
    "extract_lbph_face",
    "maybe_downscale",
    "normalize_face",
    "resolve_eye_cascade_path",
]
