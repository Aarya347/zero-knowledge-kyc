import os
import tempfile
import cv2
from cv2 import dnn_superres

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from . import config
from .video_utils import write_temp_image  # noqa: E402
from .id_face_preprocessor import preprocess_id_face  # noqa: E402


class FaceMatcher:
    def __init__(self, model_name: str = "Facenet512", detector: str = "mtcnn"):
        from deepface import DeepFace
        self._DeepFace = DeepFace
        self.model_name = model_name
        self.detector = detector
        # Pre-build so first request isn't paying weight download latency.
        DeepFace.build_model(model_name)

    def same_person(self, reference_image_path: str, frame_bgr) -> tuple[bool, float]:
        import numpy as np

        ref_to_verify = reference_image_path
        temp_preprocessed_file = None
        prep_meta = {}

        # 1. Preprocess Reference ID photo (crop portrait, align, upscale, conservative enhance)
        if getattr(config, "PREPROCESS_ID_FACE", True):
            save_debug = getattr(config, "DEBUG_PREPROCESSING", False)
            debug_dir = getattr(config, "DEBUG_DIR", "") or None
            preprocessed_face, prep_meta = preprocess_id_face(
                reference_image_path,
                save_debug=save_debug,
                debug_dir=debug_dir,
            )
            if preprocessed_face is not None:
                temp_preprocessed_file = write_temp_image(_encode(preprocessed_face))
                ref_to_verify = temp_preprocessed_file
            else:
                # Detection or quality failure on the ID card: reject match safely
                print(f"[FACE_MATCH] Preprocessing failed on reference ID: {prep_meta.get('error_code')} - {prep_meta.get('error_detail')}", flush=True)
                return False, 1.0

        probe = write_temp_image(_encode(frame_bgr))
        try:
            # 2. DeepFace.verify between preprocessed ID face and probe webcam frame
            result = self._DeepFace.verify(
                img1_path=ref_to_verify,
                img2_path=probe,
                model_name=self.model_name,
                detector_backend=self.detector,
                enforce_detection=False,
                silent=True,
            )

            dist = float(result.get("distance", 1.0))
            thresh = float(result.get("threshold", 0.30))
            verified = bool(result.get("verified", False))

            print("\n" + "="*65, flush=True)
            print("[FACE_MATCH] Verification Report:", flush=True)
            if prep_meta.get("status") == "success":
                print(f"  [ID Preprocessing] Strategy: {prep_meta.get('detection_strategy')} (conf={prep_meta.get('detection_confidence')})", flush=True)
                print(f"  [ID Preprocessing] Dims: {prep_meta.get('original_dims')} -> Crop: {prep_meta.get('cropped_dims')} -> Final: {prep_meta.get('final_dims')}", flush=True)
                print(f"  [ID Preprocessing] Enhancements: {prep_meta.get('applied_enhancements') or ['none']}", flush=True)
                q_init = prep_meta.get('quality_metrics_initial', {})
                q_fin = prep_meta.get('quality_metrics_final', {})
                print(f"  [ID Preprocessing] Quality Score: {q_init.get('quality_score')} -> {q_fin.get('quality_score')} (Sharpness: {q_fin.get('sharpness')}, Contrast: {q_fin.get('contrast')})", flush=True)
            print(f"  [Matching] Distance = {dist:.4f} (Threshold = {thresh:.4f}, Model = {self.model_name})", flush=True)
            print(f"  [Decision] Verified = {verified}", flush=True)
            print("="*65 + "\n", flush=True)

            return verified, dist
        except Exception as e:
            print(f"[FACE_MATCH] DeepFace verification error: {e}", flush=True)
            return False, 1.0
        finally:
            if os.path.exists(probe):
                try:
                    os.unlink(probe)
                except Exception:
                    pass
            if temp_preprocessed_file and os.path.exists(temp_preprocessed_file):
                try:
                    os.unlink(temp_preprocessed_file)
                except Exception:
                    pass

    def analyze_held_id_in_video(self, frames, uploaded_photo_path: str) -> dict:
        import numpy as np
        import cv2

        debug_dir = getattr(config, "DEBUG_DIR", "") or tempfile.gettempdir()
        os.makedirs(debug_dir, exist_ok=True)

        print("\n" + "="*70, flush=True)
        print("[HELD_ID_DEBUG] Scanning video frames for live face and held ID...", flush=True)

        face_records = []
        for i, fr in enumerate(frames):
            try:
                extracted = self._DeepFace.extract_faces(
                    img_path=fr,
                    detector_backend=self.detector,
                    enforce_detection=False,
                    align=True,
                )
                valid = [
                    f for f in extracted
                    if f.get("confidence", 0) > 0.80 and f.get("facial_area", {}).get("w", 0) >= 30
                ]
                if valid:
                    valid.sort(key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"], reverse=True)
                    face_records.append((i, fr, valid))
            except Exception:
                pass

        print(f"[HELD_ID_DEBUG] Scanned {len(frames)} frames; found faces in {len(face_records)} frames.", flush=True)

        two_face_frames = [r for r in face_records if len(r[2]) >= 2]
        best_live_crop = None
        best_id_crop = None
        source_desc = ""

        if two_face_frames:
            print(f"[HELD_ID_DEBUG] Found {len(two_face_frames)} frames with >= 2 faces (Live User + Held ID)!", flush=True)
            i, fr, faces = two_face_frames[len(two_face_frames)//2]
            live_f = faces[0]["facial_area"]
            id_f = faces[1]["facial_area"]

            lx, ly, lw, lh = live_f["x"], live_f["y"], live_f["w"], live_f["h"]
            best_live_crop = fr[max(0, ly):min(fr.shape[0], ly+lh), max(0, lx):min(fr.shape[1], lx+lw)]

            idx, idy, idw, idh = id_f["x"], id_f["y"], id_f["w"], id_f["h"]
            best_id_crop = fr[max(0, idy):min(fr.shape[0], idy+idh), max(0, idx):min(fr.shape[1], idx+idw)]
            source_desc = f"Simultaneous 2-face frame #{i}"
        else:
            if len(face_records) >= 2:
                largest = max(face_records, key=lambda r: r[2][0]["facial_area"]["w"] * r[2][0]["facial_area"]["h"])
                smallest = min(face_records, key=lambda r: r[2][0]["facial_area"]["w"] * r[2][0]["facial_area"]["h"])

                l_area = largest[2][0]["facial_area"]["w"] * largest[2][0]["facial_area"]["h"]
                s_area = smallest[2][0]["facial_area"]["w"] * smallest[2][0]["facial_area"]["h"]

                if l_area > 1.6 * s_area:
                    i1, fr1, f1 = largest[0], largest[1], largest[2][0]["facial_area"]
                    i2, fr2, f2 = smallest[0], smallest[1], smallest[2][0]["facial_area"]
                    best_live_crop = fr1[max(0, f1["y"]):min(fr1.shape[0], f1["y"]+f1["h"]), max(0, f1["x"]):min(fr1.shape[1], f1["x"]+f1["w"])]
                    best_id_crop = fr2[max(0, f2["y"]):min(fr2.shape[0], f2["y"]+f2["h"]), max(0, f2["x"]):min(fr2.shape[1], f2["x"]+f2["w"])]
                    source_desc = f"Sequential frames: Live #{i1} vs Held ID #{i2}"

        video_match_distance = None
        if best_live_crop is not None and best_id_crop is not None and best_live_crop.size > 0 and best_id_crop.size > 0:
            live_path = os.path.join(debug_dir, "video_live_face.png")
            id_path = os.path.join(debug_dir, "video_held_id_face.png")
            cv2.imwrite(live_path, best_live_crop)
            cv2.imwrite(id_path, best_id_crop)

            try:
                res_video = self._DeepFace.verify(
                    img1_path=id_path,
                    img2_path=live_path,
                    model_name=self.model_name,
                    detector_backend=self.detector,
                    enforce_detection=False,
                    silent=True,
                )
                video_match_distance = float(res_video.get("distance", 1.0))
                print(f"[HELD_ID_DEBUG] >>> SUCCESS: Extracted {source_desc} <<<", flush=True)
                print(f"[HELD_ID_DEBUG] >>> Video-Live vs Video-Held-ID Distance = {video_match_distance:.4f} (Threshold={res_video.get('threshold')}, Verified={res_video.get('verified')}) <<<", flush=True)
                print(f"[HELD_ID_DEBUG] Saved crops to:\n  Live: {live_path}\n  Held ID: {id_path}", flush=True)
            except Exception as e:
                print(f"[HELD_ID_DEBUG] Video vs Video verify error: {e}", flush=True)
        else:
            print("[HELD_ID_DEBUG] Note: Could not isolate 2 distinct faces in video frames.", flush=True)

        baseline_distance = None
        try:
            if best_live_crop is not None and best_live_crop.size > 0:
                live_path = os.path.join(debug_dir, "video_live_face.png")
                res_uploaded = self._DeepFace.verify(
                    img1_path=uploaded_photo_path,
                    img2_path=live_path,
                    model_name=self.model_name,
                    detector_backend=self.detector,
                    enforce_detection=False,
                    silent=True,
                )
                baseline_distance = float(res_uploaded.get("distance", 1.0))
                print(f"[HELD_ID_DEBUG] Baseline (Uploaded ID vs Video Live) Distance = {baseline_distance:.4f}", flush=True)
        except Exception as e:
            pass

        print("="*70 + "\n", flush=True)

        return {
            "video_distance": video_match_distance,
            "baseline_distance": baseline_distance,
            "source": source_desc,
        }


def _encode(frame_bgr) -> bytes:
    import cv2
    ok, buf = cv2.imencode(".png", frame_bgr)
    if not ok:
        raise RuntimeError("frame encode failed")
    return buf.tobytes()
