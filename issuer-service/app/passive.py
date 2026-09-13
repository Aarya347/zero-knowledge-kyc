"""Passive (anti-spoofing) liveness via minivision-ai/Silent-Face-Anti-Spoofing.

Wraps the upstream MiniFASNet ensemble exactly as upstream's test.py does:
haar face detection -> per-model crop -> predict -> (label, score), with
label 1 = genuine, 0 = attack, and the per-model threshold parsed from the
checkpoint filename (e.g. "2.7_80x80_MiniFASNet" -> 0.70).

Fail-closed: if the vendored repo/models are missing, construction raises
VendorUnavailable and the caller must refuse issuance.
"""
import os
import sys


class VendorUnavailable(Exception):
    pass


class PassiveLiveness:
    def __init__(self, vendor_dir: str, device: str = "cpu"):
        self.vendor_dir = os.path.abspath(vendor_dir)
        model_dir = os.path.join(self.vendor_dir, "resources", "anti_spoof_models")
        src_dir = os.path.join(self.vendor_dir, "src")
        if not os.path.isdir(src_dir) or not os.path.isdir(model_dir):
            raise VendorUnavailable(f"Silent-Face vendor not found at {self.vendor_dir}")
        ckpts = [f for f in os.listdir(model_dir) if f.endswith(".pth")]
        if not ckpts:
            raise VendorUnavailable("no .pth checkpoints in vendor resources")
        if self.vendor_dir not in sys.path:
            sys.path.insert(0, self.vendor_dir)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        try:
            from anti_spoof_predict import AntiSpoofPredict  # noqa: vendored upstream
        except Exception as e:
            raise VendorUnavailable(f"cannot import vendored Silent-Face code: {e}")
        self._AntiSpoofPredict = AntiSpoofPredict
        self.model_dir = model_dir
        self.device = device
        orig_cwd = os.getcwd()
        try:
            os.chdir(self.vendor_dir)
            self._engine = AntiSpoofPredict(device)
        finally:
            os.chdir(orig_cwd)

    @staticmethod
    def _threshold_for(model_name: str) -> float:
        # Mirrors upstream utility.parse_model_name threshold convention.
        try:
            return int(model_name.split("_")[0]) / 10.0
        except Exception:
            return 0.70

    def check_frame(self, frame_bgr, face_box=None):
        """Returns (is_genuine, label, score). Raises VendorUnavailable if broken."""
        import cv2
        import numpy as np
        from src.generate_patches import CropImage
        from src.utility import parse_model_name

        image_cropper = CropImage()
        if face_box is not None:
            image_bbox = face_box
        else:
            try:
                orig_cwd = os.getcwd()
                os.chdir(self.vendor_dir)
                image_bbox = self._engine.get_bbox(frame_bgr)
            finally:
                os.chdir(orig_cwd)

        models = [f for f in os.listdir(self.model_dir) if f.endswith(".pth")]
        if not models:
            raise VendorUnavailable("no models found in model_dir")

        prediction = np.zeros((1, 3))
        for model_name in models:
            h_input, w_input, model_type, scale = parse_model_name(model_name)
            param = {
                "org_img": frame_bgr,
                "bbox": image_bbox,
                "scale": scale,
                "out_w": w_input,
                "out_h": h_input,
                "crop": True,
            }
            if scale is None:
                param["crop"] = False
            img = image_cropper.crop(**param)
            prediction += self._engine.predict(img, os.path.join(self.model_dir, model_name))

        label = int(np.argmax(prediction))
        score = float(prediction[0][label] / len(models))
        strictest = min(self._threshold_for(f) for f in models)
        genuine = (label == 1) and (score >= strictest)
        return genuine, label, score

    def check_video(self, frames, k: int = 5):
        """ALL sampled frames must be classified genuine. Returns dict verdict."""
        n = len(frames)
        idxs = sorted({int(i * (n - 1) / max(1, k - 1)) for i in range(k)}) if n > 1 else [0]
        per_frame = []
        for i in idxs:
            g, label, score = self.check_frame(frames[i])
            per_frame.append({"frame_index": int(i), "label": label, "score": round(score, 4)})
        ok = all(p["label"] == 1 for p in per_frame)
        return {"genuine": ok, "frames": per_frame}
