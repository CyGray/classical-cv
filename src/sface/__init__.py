"""SFace recognizer wrapper (DL track ported into the CV repo).

SFace (``cv.FaceRecognizerSF`` over ``face_recognition_sface_2021dec.onnx``) used
through the same shape LBPH exposes: ``enroll -> Gallery``, ``score -> Match``,
``far_of -> calibrated FAR``. The recognition math is ported verbatim from the
``face-detection-g3-dl`` track (``dnn.py`` / ``feature-extract.py``):

* embedding = ``recognizer.feature(recognizer.alignCrop(img_bgr, yunet_row))``
  (128-D float32 = 512 B), and
* genuine iff ``cosine >= 0.363`` AND ``L2 <= 1.128``.
"""

from src.sface.recognizer import (
    COSINE_GENUINE_THRESHOLD,
    L2_GENUINE_THRESHOLD,
    SFACE_FEATURE_BYTES,
    SFaceFarModel,
    SFaceGallery,
    SFaceMatch,
    SFaceRecognizer,
    default_sface_model_path,
    detection_to_yunet_row,
)

__all__ = [
    "COSINE_GENUINE_THRESHOLD",
    "L2_GENUINE_THRESHOLD",
    "SFACE_FEATURE_BYTES",
    "SFaceFarModel",
    "SFaceGallery",
    "SFaceMatch",
    "SFaceRecognizer",
    "default_sface_model_path",
    "detection_to_yunet_row",
]
