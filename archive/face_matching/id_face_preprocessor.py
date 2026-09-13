"""
Modular ID-Document Face Preprocessing Pipeline for zk-KYC

Enhances the quality of low-resolution, compressed, or small ID card portrait photos
BEFORE feeding them to the DeepFace/Facenet512 face-matching pipeline.

Pipeline:
  1. Detect portrait face on the document (multi-strategy: MTCNN / SSD / Haar cascade / multi-scale).
  2. Validate bounding box constraints (aspect ratio, area relative to document, confidence).
  3. Crop the face with a proportional margin (25% default) to preserve facial outline.
  4. Measure quality metrics (sharpness, brightness, contrast, noise, composite quality score).
  5. Align face horizontally if facial landmarks (eyes) are available.
  6. Upscale small face crops using FSRCNN DNN super-resolution and/or Lanczos-4 interpolation.
  7. Apply conservative, adaptive enhancement (mild CLAHE contrast, bilateral denoise, mild unsharp mask).
  8. Return preprocessed face and rich diagnostic metadata.
"""

import os
import math
import numpy as np
import cv2
from typing import Tuple, Dict, Any, Optional, Union

# Attempt to load dnn_superres if available
_SR_MODEL = None
_SR_INIT_ATTEMPTED = False


def _get_super_res_model():
    global _SR_MODEL, _SR_INIT_ATTEMPTED
    if _SR_INIT_ATTEMPTED:
        return _SR_MODEL
    _SR_INIT_ATTEMPTED = True
    if hasattr(cv2, "dnn_superres"):
        models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
        fsrcnn_path = os.path.join(models_dir, "FSRCNN_x2.pb")
        if os.path.exists(fsrcnn_path):
            try:
                sr = cv2.dnn_superres.DnnSuperResImpl_create()
                sr.readModel(fsrcnn_path)
                sr.setModel("fsrcnn", 2)
                _SR_MODEL = sr
            except Exception as e:
                _SR_MODEL = None
    return _SR_MODEL


# Built-in frontal face cascade for fast, robust document portrait localization
_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_FACE_CASCADE = cv2.CascadeClassifier(_CASCADE_PATH) if os.path.exists(_CASCADE_PATH) else None


class PreprocessingError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def detect_portrait_face(
    img_bgr: np.ndarray,
    min_face_size: int = 25,
    max_doc_area_ratio: float = 0.75,
    min_doc_area_ratio: float = 0.005,
) -> Tuple[Dict[str, int], float, Optional[Dict[str, Tuple[int, int]]], str]:
    """
    Detects the primary portrait face on an ID document image using a multi-strategy cascade.
    
    Strategies:
      1. MTCNN via DeepFace (extracts accurate 5-point eye landmarks).
      2. SSD ResNet-10 via DeepFace (robust across diverse passport/ID photo layouts and styles).
      3. OpenCV Haar Cascade (fast local CPU fallback).
      4. Multi-scale sliding cascade for large documents.
    
    Returns:
      (bbox_dict, confidence, landmarks_or_None, strategy_name)
      where bbox_dict is {"x": int, "y": int, "w": int, "h": int}
    """
    if img_bgr is None or img_bgr.size == 0:
        raise PreprocessingError("INVALID_IMAGE", "Empty or unreadable image array")

    h_doc, w_doc = img_bgr.shape[:2]
    doc_area = h_doc * w_doc
    candidates = []

    # Strategy 1 & 2: MTCNN and SSD via DeepFace
    for backend in ("mtcnn", "ssd"):
        try:
            from deepface import DeepFace
            extracted = DeepFace.extract_faces(
                img_path=img_bgr,
                detector_backend=backend,
                enforce_detection=False,
                align=False,
            )
            for f in extracted:
                fa = f.get("facial_area", {})
                conf = float(f.get("confidence", 0.0) or 0.0)
                x, y, w, h = fa.get("x", 0), fa.get("y", 0), fa.get("w", 0), fa.get("h", 0)
                area = w * h
                area_ratio = area / max(1, doc_area)
                aspect_ratio = w / max(1, h)

                # Strict validation: reject whole-document false detections and extreme shapes
                if (
                    w >= min_face_size
                    and h >= min_face_size
                    and min_doc_area_ratio <= area_ratio <= max_doc_area_ratio
                    and 0.50 <= aspect_ratio <= 1.50
                    and conf >= 0.60
                ):
                    landmarks = None
                    left_eye = fa.get("left_eye")
                    right_eye = fa.get("right_eye")
                    if left_eye and right_eye:
                        landmarks = {"left_eye": tuple(left_eye), "right_eye": tuple(right_eye)}
                    candidates.append((area, conf, {"x": x, "y": y, "w": w, "h": h}, landmarks, backend))
            if candidates:
                break
        except Exception:
            pass

    # Strategy 3: OpenCV Haar Cascade detector
    if not candidates and _FACE_CASCADE is not None:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        gray_eq = cv2.equalizeHist(gray)
        
        for g_input in (gray, gray_eq):
            for mn in (3, 2):
                faces = _FACE_CASCADE.detectMultiScale(
                    g_input,
                    scaleFactor=1.05,
                    minNeighbors=mn,
                    minSize=(min_face_size, min_face_size),
                    flags=cv2.CASCADE_SCALE_IMAGE,
                )
                for (x, y, w, h) in faces:
                    area = w * h
                    area_ratio = area / max(1, doc_area)
                    aspect_ratio = w / max(1, h)
                    if (
                        w >= min_face_size
                        and h >= min_face_size
                        and min_doc_area_ratio <= area_ratio <= max_doc_area_ratio
                        and 0.55 <= aspect_ratio <= 1.45
                    ):
                        haar_conf = min(0.95, 0.70 + (area / doc_area) * 0.5)
                        candidates.append((area, haar_conf, {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}, None, "haar_cascade"))
                if candidates:
                    break
            if candidates:
                break

    # Strategy 4: Multi-scale downscaling for very large ID images (> 1000px)
    if not candidates and _FACE_CASCADE is not None and max(h_doc, w_doc) > 1000:
        scale_factor = 800.0 / max(h_doc, w_doc)
        small_img = cv2.resize(img_bgr, (0, 0), fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_AREA)
        gray_small = cv2.cvtColor(small_img, cv2.COLOR_BGR2GRAY)
        faces_small = _FACE_CASCADE.detectMultiScale(
            gray_small,
            scaleFactor=1.08,
            minNeighbors=2,
            minSize=(int(min_face_size * scale_factor), int(min_face_size * scale_factor)),
        )
        for (sx, sy, sw, sh) in faces_small:
            x, y, w, h = int(sx / scale_factor), int(sy / scale_factor), int(sw / scale_factor), int(sh / scale_factor)
            area = w * h
            area_ratio = area / max(1, doc_area)
            aspect_ratio = w / max(1, h)
            if (
                w >= min_face_size
                and h >= min_face_size
                and min_doc_area_ratio <= area_ratio <= max_doc_area_ratio
                and 0.55 <= aspect_ratio <= 1.45
            ):
                candidates.append((area, 0.75, {"x": x, "y": y, "w": w, "h": h}, None, "haar_multiscale"))

    if not candidates:
        raise PreprocessingError("NO_FACE_DETECTED", "No valid face portrait detected on the ID document")

    # If multiple candidates found, sort by area * confidence descending
    if len(candidates) > 1:
        candidates.sort(key=lambda c: c[0] * c[1], reverse=True)

    # Pick the most prominent, confident candidate
    best = candidates[0]
    return best[2], float(best[1]), best[3], best[4]


def crop_face_with_margin(
    img_bgr: np.ndarray,
    bbox: Dict[str, int],
    margin: float = 0.25,
) -> Tuple[np.ndarray, Dict[str, int]]:
    """
    Crops the face bounding box with a proportional margin to include forehead,
    chin, ears, and hair outline without boundary clipping.
    
    Returns:
      (crop_bgr, crop_coords_dict)
    """
    h_img, w_img = img_bgr.shape[:2]
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]

    pad_x = int(w * margin)
    pad_y = int(h * margin)

    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(w_img, x + w + pad_x)
    y1 = min(h_img, y + h + pad_y)

    crop = img_bgr[y0:y1, x0:x1].copy()
    crop_coords = {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "w": x1 - x0, "h": y1 - y0}
    return crop, crop_coords


def check_face_quality(crop_bgr: np.ndarray) -> Dict[str, Any]:
    """
    Computes objective quality metrics on the cropped face:
      - sharpness: Laplacian variance (higher is sharper)
      - brightness: Mean luminance in LAB color space (0-255)
      - contrast: Standard deviation of luminance (higher is richer dynamic range)
      - noise: Estimated standard deviation of high-frequency noise
      - quality_score: Composite 0-100 quality score
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return {"sharpness": 0.0, "brightness": 0.0, "contrast": 0.0, "noise": 0.0, "quality_score": 0.0}

    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 1. Sharpness via Laplacian variance
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # 2. Brightness & Contrast via LAB L-channel
    lab = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0]
    brightness_mean = float(np.mean(l_channel))
    contrast_std = float(np.std(l_channel))

    # 3. Noise estimation via median filter residual
    median_filtered = cv2.medianBlur(gray, 3)
    noise_residual = cv2.absdiff(gray, median_filtered)
    noise_est = float(np.mean(noise_residual))

    # 4. Composite quality score (0-100)
    res_score = min(1.0, min(w, h) / 250.0) * 35.0
    sharp_score = min(1.0, laplacian_var / 200.0) * 30.0
    contrast_score = min(1.0, contrast_std / 45.0) * 20.0
    illum_score = max(0.0, 1.0 - abs(brightness_mean - 128.0) / 100.0) * 15.0

    quality_score = float(round(res_score + sharp_score + contrast_score + illum_score, 1))

    return {
        "sharpness": float(round(laplacian_var, 2)),
        "brightness": float(round(brightness_mean, 2)),
        "contrast": float(round(contrast_std, 2)),
        "noise": float(round(noise_est, 2)),
        "quality_score": quality_score,
        "dims": (w, h),
    }


def align_face(
    crop_bgr: np.ndarray,
    landmarks: Optional[Dict[str, Tuple[int, int]]],
    crop_bbox_offset: Tuple[int, int] = (0, 0),
) -> Tuple[np.ndarray, bool, float]:
    """
    Aligns facial orientation horizontally if eye landmarks are provided.
    
    Returns:
      (aligned_crop, alignment_applied_bool, rotation_angle_degrees)
    """
    if not landmarks or "left_eye" not in landmarks or "right_eye" not in landmarks:
        return crop_bgr, False, 0.0

    lx, ly = landmarks["left_eye"]
    rx, ry = landmarks["right_eye"]

    # Compute tilt angle between the eyes
    dx = rx - lx
    dy = ry - ly
    angle = math.degrees(math.atan2(dy, dx))

    # If angle is already within +/- 1.5 degrees or excessive (> 45 deg), don't alter
    if abs(angle) < 1.5 or abs(angle) > 45.0:
        return crop_bgr, False, float(round(angle, 2))

    h, w = crop_bgr.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    aligned = cv2.warpAffine(crop_bgr, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)
    return aligned, True, float(round(angle, 2))


def upscale_face(
    crop_bgr: np.ndarray,
    target_min_dim: int = 240,
) -> Tuple[np.ndarray, bool, str]:
    """
    Upscales the face crop if dimensions are small (< target_min_dim).
    Uses FSRCNN DNN Super-Resolution if available, chained with high-quality Lanczos-4
    to ensure target_min_dim is reliably met.
    
    Returns:
      (upscaled_crop, was_upscaled, method_description)
    """
    h, w = crop_bgr.shape[:2]
    min_dim = min(h, w)

    if min_dim >= target_min_dim:
        return crop_bgr, False, "none_already_sufficient_resolution"

    current = crop_bgr
    sr = _get_super_res_model()
    used_sr = False
    
    if sr is not None and min_dim < 180:
        try:
            current = sr.upsample(current)
            used_sr = True
        except Exception:
            pass

    cur_h, cur_w = current.shape[:2]
    cur_min = min(cur_h, cur_w)
    
    # If still below target_min_dim, apply Lanczos-4 to reach target size
    if cur_min < target_min_dim:
        scale = target_min_dim / float(cur_min)
        new_w = int(round(cur_w * scale))
        new_h = int(round(cur_h * scale))
        current = cv2.resize(current, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        fin_h, fin_w = current.shape[:2]
        method_desc = f"{'fsrcnn_x2+' if used_sr else ''}lanczos4 ({w}x{h} -> {fin_w}x{fin_h})"
    else:
        fin_h, fin_w = current.shape[:2]
        method_desc = f"fsrcnn_x2 ({w}x{h} -> {fin_w}x{fin_h})"

    return current, True, method_desc


def enhance_face_conservatively(
    crop_bgr: np.ndarray,
    quality_metrics: Dict[str, Any],
) -> Tuple[np.ndarray, list[str]]:
    """
    Applies conservative, non-hallucinatory enhancements only when metrics indicate need:
      1. Contrast & Dynamic Range Normalization (mild CLAHE on L-channel if contrast is low).
      2. Illumination gamma compensation if heavily underexposed or overexposed.
      3. Mild bilateral denoising if noise estimate is high.
      4. Mild unsharp masking if image is soft/blurry and not noisy.
    
    Returns:
      (enhanced_bgr, list_of_applied_operations)
    """
    img = crop_bgr.copy()
    applied = []

    brightness = quality_metrics.get("brightness", 128.0)
    contrast = quality_metrics.get("contrast", 40.0)
    sharpness = quality_metrics.get("sharpness", 100.0)
    noise = quality_metrics.get("noise", 0.0)

    # 1. Illumination / Gamma Adjustment (mild, clamped)
    if brightness < 85.0:
        gamma = max(0.85, math.log(120.0 / 255.0) / math.log(max(10.0, brightness) / 255.0))
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
        img = cv2.LUT(img, table)
        applied.append(f"gamma_brighten_{gamma:.2f}")
    elif brightness > 195.0:
        gamma = min(1.20, math.log(145.0 / 255.0) / math.log(brightness / 255.0))
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
        img = cv2.LUT(img, table)
        applied.append(f"gamma_darken_{gamma:.2f}")

    # 2. Contrast Normalization via CLAHE on L-channel (conservative clip limit 1.4)
    if contrast < 42.0:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=1.4, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)
        lab_enhanced = cv2.merge((l_clahe, a, b))
        img = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        applied.append("clahe_contrast_norm")

    # 3. Mild Bilateral Denoising (preserves sharp facial edges while smoothing compression artifacts)
    if noise > 7.0:
        img = cv2.bilateralFilter(img, d=5, sigmaColor=20, sigmaSpace=20)
        applied.append("bilateral_denoise")

    # 4. Mild Unsharp Masking (only if image is soft/blurry and not excessively noisy)
    if sharpness < 110.0 and noise < 8.0:
        gaussian = cv2.GaussianBlur(img, (0, 0), sigmaX=1.8)
        sharpened = cv2.addWeighted(img, 1.25, gaussian, -0.25, 0)
        img = np.clip(sharpened, 0, 255).astype(np.uint8)
        applied.append("mild_unsharp_mask")

    return img, applied


def preprocess_id_face(
    image_input: Union[str, bytes, np.ndarray],
    save_debug: bool = False,
    debug_dir: Optional[str] = None,
    target_min_dim: int = 240,
) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
    """
    Main entrypoint for ID Document Face Preprocessing.
    
    Accepts:
      image_input: File path (str), raw image bytes (bytes), or BGR image (np.ndarray).
      save_debug: Whether to save visual debug artifacts to debug_dir.
      debug_dir: Destination folder for debug artifacts (if enabled).
      target_min_dim: Minimum resolution threshold for upscaling.
      
    Returns:
      (preprocessed_face_bgr, metadata_dict)
      where preprocessed_face_bgr is the enhanced face image (or None on unresolvable error),
      and metadata_dict contains structured diagnostic data.
    """
    # 1. Decode / Validate Input Image
    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            return None, {"status": "error", "error_code": "FILE_NOT_FOUND", "detail": f"Path not found: {image_input}"}
        img_raw = cv2.imread(image_input)
    elif isinstance(image_input, bytes):
        img_raw = cv2.imdecode(np.frombuffer(image_input, np.uint8), cv2.IMREAD_COLOR)
    elif isinstance(image_input, np.ndarray):
        img_raw = image_input.copy()
    else:
        return None, {"status": "error", "error_code": "INVALID_INPUT_TYPE", "detail": f"Unsupported type: {type(image_input)}"}

    if img_raw is None or img_raw.size == 0:
        return None, {"status": "error", "error_code": "INVALID_IMAGE", "detail": "Image could not be decoded"}

    h_orig, w_orig = img_raw.shape[:2]
    meta: Dict[str, Any] = {
        "status": "pending",
        "original_dims": (w_orig, h_orig),
        "detected_bbox": None,
        "detection_confidence": None,
        "detection_strategy": None,
        "cropped_dims": None,
        "final_dims": None,
        "quality_metrics_initial": None,
        "quality_metrics_final": None,
        "applied_enhancements": [],
        "debug_paths": {},
    }

    # 2. Detect Portrait Face
    try:
        bbox, conf, landmarks, strategy = detect_portrait_face(img_raw)
        meta["detected_bbox"] = bbox
        meta["detection_confidence"] = round(conf, 3)
        meta["detection_strategy"] = strategy
    except PreprocessingError as e:
        meta["status"] = "error"
        meta["error_code"] = e.code
        meta["error_detail"] = str(e)
        return None, meta
    except Exception as e:
        meta["status"] = "error"
        meta["error_code"] = "DETECTION_FAILED"
        meta["error_detail"] = str(e)
        return None, meta

    # 3. Crop Face with Proportional Margin
    crop, crop_coords = crop_face_with_margin(img_raw, bbox, margin=0.25)
    meta["cropped_dims"] = (crop.shape[1], crop.shape[0])

    # 4. Measure Initial Face Quality
    initial_quality = check_face_quality(crop)
    meta["quality_metrics_initial"] = initial_quality

    # 5. Facial Landmark Alignment (if eyes are detected)
    aligned_crop, was_aligned, tilt_angle = align_face(crop, landmarks)
    if was_aligned:
        meta["applied_enhancements"].append(f"aligned_rotation_{tilt_angle:.1f}deg")
    current_crop = aligned_crop

    # 6. High-Quality Super-Resolution / Lanczos-4 Upscaling
    upscaled_crop, was_upscaled, upscale_method = upscale_face(current_crop, target_min_dim=target_min_dim)
    if was_upscaled:
        meta["applied_enhancements"].append(f"upscale_{upscale_method}")
    current_crop = upscaled_crop

    # 7. Adaptive, Conservative Enhancement
    enhanced_crop, ops = enhance_face_conservatively(current_crop, initial_quality)
    meta["applied_enhancements"].extend(ops)
    final_face = enhanced_crop

    # 8. Measure Final Quality & Final Dimensions
    final_quality = check_face_quality(final_face)
    meta["quality_metrics_final"] = final_quality
    meta["final_dims"] = (final_face.shape[1], final_face.shape[0])
    meta["status"] = "success"

    # 9. Debug Artifacts Saving (if enabled)
    if save_debug and debug_dir:
        try:
            os.makedirs(debug_dir, exist_ok=True)
            p_orig = os.path.join(debug_dir, "debug_id_original.png")
            p_crop = os.path.join(debug_dir, "debug_id_crop_raw.png")
            p_final = os.path.join(debug_dir, "debug_id_face_preprocessed.png")

            cv2.imwrite(p_orig, img_raw)
            cv2.imwrite(p_crop, crop)
            cv2.imwrite(p_final, final_face)

            meta["debug_paths"] = {
                "original": p_orig,
                "crop": p_crop,
                "preprocessed": p_final,
            }
        except Exception as e:
            meta["debug_save_error"] = str(e)

    return final_face, meta
