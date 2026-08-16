import json
import math
from pathlib import Path
import numpy as np
import cv2 as cv

from lbph_config import (
    descriptor_from_mapping,
    make_lbph,
    release_descriptor_from_manifest,
    validate_loaded_lbph,
)

class HybridCascade:
    def __init__(self, base_dir=".", *, models_dir=None, config_path=None, artifacts_dir=None):
        # ``base_dir`` matches the upstream hardware constructor. Keep the
        # previous ``models_dir=`` spelling as an additive rollback alias.
        self.models_dir = Path(models_dir if models_dir is not None else base_dir)
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else self._active_artifacts_dir()
        
        # Load Thresholds
        thresh_path = Path(config_path) if config_path else self.models_dir / "config" / "thresholds.json"
        if config_path is None and not thresh_path.exists():
            thresh_path = self.models_dir / "thresholds.json"
        with open(thresh_path, "r") as f:
            cfg = json.load(f)
            try:
                self.threshold_descriptor = descriptor_from_mapping(
                    cfg.get("lbph_descriptor"), source=str(thresh_path)
                )
            except ValueError as error:
                raise RuntimeError(
                    f"Threshold file {thresh_path} has no valid LBPH descriptor "
                    "compatibility metadata. Refusing to start."
                ) from error
            self.tau_accept = cfg["gate"]["tau_accept"]
            self.tau_reject = cfg["gate"]["tau_reject"]
            self.sface_l2_genuine = cfg["sface"]["l2_genuine"]
            
            # Quality bounds
            self.q_min_face = cfg["quality"]["px_min"]
            self.q_tau_blur = cfg["quality"]["tau_blur"]

        # 1. Initialize YuNet
        yunet_path = self.models_dir / "models" / "face_detection_yunet_2023mar.onnx"
        if not yunet_path.exists():
            yunet_path = self.models_dir / "face_detection_yunet_2023mar.onnx"
        self.detector = cv.FaceDetectorYN.create(
            str(yunet_path),
            "", (320, 320), 0.9, 0.3, 5000
        )

        # 2. Initialize LBPH
        # The constructor is only a default. OpenCV read() replaces these
        # values with the serialized model parameters, so validate after read.
        self.lbph = make_lbph(self.threshold_descriptor)
        lbph_model = self.artifacts_dir / "lbph.yml"
        lbph_labels = self.artifacts_dir / "labels.json"
        release_manifest_path = self.artifacts_dir / "manifest.json"
        release_manifest = None
        release_descriptor = self.threshold_descriptor
        legacy_manifest = False
        if not lbph_model.exists():  # Original porting bundle compatibility.
            lbph_model = self.models_dir / "artifacts" / "lbph_seed42_manifest731bcf52fec2_cropped.yml"
            if not lbph_model.exists():
                lbph_model = self.models_dir / "lbph_seed42_manifest731bcf52fec2_cropped.yml"
            lbph_labels = self.models_dir / "artifacts" / "lbph_labels_seed42_manifest731bcf52fec2_cropped.json"
            if not lbph_labels.exists():
                lbph_labels = self.models_dir / "lbph_labels_seed42_manifest731bcf52fec2_cropped.json"
            # Legacy bundles have no release manifest; their serialized model
            # is checked directly against thresholds.json below.
            release_manifest_path = None
            print(
                f"[WARN] Using legacy bundled LBPH model {lbph_model}; "
                f"validating it against thresholds descriptor "
                f"{self.threshold_descriptor.descriptor_id}."
            )
        else:
            if not release_manifest_path.exists():
                raise RuntimeError(f"Active enrollment release {self.artifacts_dir} is missing manifest.json.")
            with release_manifest_path.open("r", encoding="utf-8") as f:
                release_manifest = json.load(f)
            try:
                release_descriptor, legacy_manifest = release_descriptor_from_manifest(
                    release_manifest,
                    self.threshold_descriptor,
                    source=str(release_manifest_path),
                )
            except ValueError as error:
                raise RuntimeError(
                    f"Active enrollment release {release_manifest_path} has invalid "
                    "LBPH descriptor compatibility metadata. Refusing to start."
                ) from error
            if legacy_manifest:
                print(
                    f"[WARN] Active release {self.artifacts_dir} has no LBPH descriptor "
                    f"metadata; treating thresholds.json descriptor "
                    f"{self.threshold_descriptor.descriptor_id} as the expected legacy profile."
                )
        self.lbph.read(str(lbph_model))
        loaded_descriptor = validate_loaded_lbph(
            self.lbph,
            self.threshold_descriptor,
            context=f"serialized model {lbph_model}",
        )
        if release_manifest is not None and not legacy_manifest:
            if loaded_descriptor != release_descriptor:
                raise RuntimeError(
                    f"LBPH descriptor mismatch for release/model pair {self.artifacts_dir}: "
                    f"release expects {release_descriptor.descriptor_id}, "
                    f"loaded model is {loaded_descriptor.descriptor_id}."
                )
        with open(lbph_labels, "r") as f:
            self.lbph_labels = {int(v): k for k, v in json.load(f).items()}
        self.labels = dict(self.lbph_labels)

        # 3. Initialize SFace
        sface_onnx_path = self.models_dir / "models" / "face_recognition_sface_2021dec.onnx"
        if not sface_onnx_path.exists():
            sface_onnx_path = self.models_dir / "face_recognition_sface_2021dec.onnx"
        self.sface = cv.FaceRecognizerSF.create(
            str(sface_onnx_path), ""
        )
        gallery_path = self.artifacts_dir / "sface_gallery.npy"
        if not gallery_path.exists():
            gallery_path = self.models_dir / "artifacts" / "sface_gallery_seed42_manifest731bcf52fec2_cropped.npy"
            if not gallery_path.exists():
                gallery_path = self.models_dir / "sface_gallery_seed42_manifest731bcf52fec2_cropped.npy"
        gallery_dict = np.load(gallery_path, allow_pickle=True).item()
        self.sface_labels = list(gallery_dict.keys())
        self.sface_gallery = [gallery_dict[name].reshape(1, -1) for name in self.sface_labels]

    def _active_artifacts_dir(self):
        """Use hardware enrollment's current release when present, else legacy files."""
        pointer = self.models_dir / "enrollment" / "current.json"
        if not pointer.exists():
            return self.models_dir
        payload = json.loads(pointer.read_text(encoding="utf-8"))
        release = pointer.parent / payload["release"]
        if not release.is_dir():
            raise FileNotFoundError(f"Enrollment release referenced by {pointer} is missing: {release}")
        return release

    def _normalize_lbph(self, face_gray):
        """Tan-Triggs preprocessing required for this LBPH model."""
        img = cv.resize(face_gray, (100, 100), interpolation=cv.INTER_AREA)
        img = np.float32(img) / 255.0
        alpha, tau, gamma = 0.1, 10.0, 0.2
        img = np.power(img, gamma)
        img = cv.GaussianBlur(img, (0, 0), sigmaX=1.0)
        img = img / np.power(np.mean(np.power(np.abs(img), alpha)), 1.0 / alpha)
        img = img / np.power(np.mean(np.power(np.abs(img), tau)), 1.0 / tau)
        img = tau * np.tanh(img / tau)
        img = cv.normalize(img, None, 0, 255, cv.NORM_MINMAX)
        return np.uint8(img)

    def infer(self, image_bgr):
        h, w = image_bgr.shape[:2]
        self.detector.setInputSize((w, h))
        image_gray = cv.cvtColor(image_bgr, cv.COLOR_BGR2GRAY)
        
        _, faces = self.detector.detect(image_bgr)
        if faces is None or len(faces) == 0:
            return {"status": "no_face"}
        
        # Take largest face
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, bw, bh = [int(v) for v in largest_face[:4]]
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        bw = max(1, min(bw, w - x))
        bh = max(1, min(bh, h - y))
        face_px = min(bw, bh)
        
        # Quality Check
        quality_flags = []
        if face_px < self.q_min_face:
            quality_flags.append(f"small_face({face_px}px)")
            
        face_gray = image_gray[y:y+bh, x:x+bw]
        if face_gray.size == 0:
            return {"status": "no_face"}
            
        quality_gray = cv.resize(face_gray, (100, 100), interpolation=cv.INTER_AREA)
        blur_val = cv.Laplacian(quality_gray, cv.CV_64F).var()
        if blur_val < self.q_tau_blur:
            quality_flags.append(f"blurry({blur_val:.1f})")

        # Step 1: LBPH Fast Path
        lbph_norm = self._normalize_lbph(face_gray)
        pred_id, lbph_dist = self.lbph.predict(lbph_norm)
        lbph_name = self.lbph_labels.get(int(pred_id), "Unknown")
        
        # Gate Logic
        escalate = False
        reason = ""
        
        if len(quality_flags) > 0:
            escalate = True
            reason = "quality:" + ",".join(quality_flags)
        elif self.tau_accept < lbph_dist < self.tau_reject:
            escalate = True
            reason = "ambiguous_band"
            
        if not escalate:
            if lbph_dist <= self.tau_accept:
                return {
                    "status": "accepted", "engine": "lbph", "name": lbph_name,
                    "distance": lbph_dist, "bbox": (x, y, bw, bh)
                }
            else:
                return {
                    "status": "rejected", "engine": "lbph", "reason": "confident_reject",
                    "name": lbph_name, "distance": lbph_dist, "bbox": (x, y, bw, bh)
                }
            
        # Step 2: SFace Escalation (runs if escalated)
        aligned = self.sface.alignCrop(image_bgr, largest_face)
        feature = self.sface.feature(aligned)
        
        best_l2 = float('inf')
        best_idx = -1
        for i, g_feat in enumerate(self.sface_gallery):
            l2_dist = self.sface.match(feature, g_feat, cv.FaceRecognizerSF_FR_NORM_L2)
            if l2_dist < best_l2:
                best_l2 = l2_dist
                best_idx = i
                
        sface_name = self.sface_labels[best_idx]
        
        if best_l2 <= self.sface_l2_genuine:
            return {
                "status": "accepted", "engine": "sface", "name": sface_name,
                "l2": best_l2, "lbph_distance": lbph_dist, "gate_reason": reason,
                "bbox": (x, y, bw, bh)
            }
            
        return {
            "status": "rejected", "engine": "sface", "reason": "impostor",
            "name": sface_name, "l2": best_l2, "lbph_distance": lbph_dist, "gate_reason": reason,
            "bbox": (x, y, bw, bh)
        }

if __name__ == "__main__":
    cascade = HybridCascade(".")
    
    # Test on a known image from the dataset
    test_img_path = r"C:\Users\acer\Documents\USLS 4th Year\Computer Vision\classical-cv\data\lasalle_db1_processed\Andrew_Eroyla\dark_down.jpg"
    frame = cv.imread(test_img_path)
    
    if frame is None:
        print(f"Could not load {test_img_path}")
    else:
        print(f"Running inference on {test_img_path}...")
        result = cascade.infer(frame)
        import pprint
        pprint.pprint(result)
