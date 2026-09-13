import os
import tempfile
import cv2
import numpy as np
import pytest

from synth import Identity, render_id_card, draw_face
from app.id_face_preprocessor import (
    preprocess_id_face,
    detect_portrait_face,
    crop_face_with_margin,
    check_face_quality,
    upscale_face,
    enhance_face_conservatively,
    PreprocessingError,
)


def test_detect_and_crop_synthetic_id():
    """Verify that detect_portrait_face and crop_face_with_margin cleanly isolate
    the ID photo from a full document."""
    ident = Identity(42)
    id_card = render_id_card(ident)
    
    bbox, conf, landmarks, strategy = detect_portrait_face(id_card)
    assert bbox is not None
    assert "x" in bbox and "y" in bbox and "w" in bbox and "h" in bbox
    assert conf >= 0.50
    assert strategy in ("mtcnn", "ssd", "haar_cascade", "haar_multiscale")
    
    # Check that bbox covers roughly the ID photo region (w: 100-300, h: 100-300)
    assert 50 <= bbox["w"] <= 350
    assert 50 <= bbox["h"] <= 350
    
    crop, crop_coords = crop_face_with_margin(id_card, bbox, margin=0.25)
    assert crop.shape[0] > bbox["h"]
    assert crop.shape[1] > bbox["w"]
    assert crop.size > 0


def test_preprocess_id_face_pipeline_success():
    """Verify the full preprocess_id_face pipeline on an ID card document."""
    ident = Identity(101)
    id_card = render_id_card(ident)
    
    processed_face, meta = preprocess_id_face(id_card)
    
    assert processed_face is not None
    assert meta["status"] == "success"
    assert meta["original_dims"] == (640, 900)
    assert meta["detected_bbox"] is not None
    assert meta["cropped_dims"] is not None
    assert meta["final_dims"] is not None
    assert meta["final_dims"][0] >= 200
    assert meta["final_dims"][1] >= 200
    assert "quality_metrics_initial" in meta
    assert "quality_metrics_final" in meta
    assert isinstance(meta["applied_enhancements"], list)


def test_small_face_upscaling():
    """Verify that small face crops are upscaled to the target minimum dimension."""
    ident = Identity(55)
    face_raw = draw_face(ident, 0.0, size=100)
    assert min(face_raw.shape[:2]) == 100
    
    upscaled, was_up, desc = upscale_face(face_raw, target_min_dim=240)
    assert was_up is True
    assert min(upscaled.shape[:2]) >= 240
    assert "lanczos4" in desc or "fsrcnn" in desc


def test_quality_metrics_calculation():
    """Verify that check_face_quality returns valid numeric indicators."""
    img = np.zeros((150, 150, 3), dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (130, 130), (200, 180, 150), -1)
    cv2.circle(img, (75, 75), 25, (40, 40, 40), -1)
    
    metrics = check_face_quality(img)
    assert "sharpness" in metrics
    assert "brightness" in metrics
    assert "contrast" in metrics
    assert "noise" in metrics
    assert "quality_score" in metrics
    assert 0.0 <= metrics["quality_score"] <= 100.0


def test_conservative_enhancement_low_contrast():
    """Verify that low-contrast input receives CLAHE enhancement."""
    # Create low contrast washed-out face
    img = np.full((120, 120, 3), 120, dtype=np.uint8)
    img += np.random.randint(-5, 6, img.shape, dtype=np.int16).astype(np.uint8)
    
    quality = check_face_quality(img)
    enhanced, ops = enhance_face_conservatively(img, quality)
    
    assert "clahe_contrast_norm" in ops


def test_non_destructive_original_image_preservation():
    """Verify that preprocess_id_face strictly preserves the original image."""
    ident = Identity(77)
    id_card = render_id_card(ident)
    id_card_copy = id_card.copy()
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        temp_path = f.name
    try:
        cv2.imwrite(temp_path, id_card)
        initial_stat = os.stat(temp_path)
        
        processed_face, meta = preprocess_id_face(temp_path)
        
        after_stat = os.stat(temp_path)
        assert initial_stat.st_mtime == after_stat.st_mtime
        assert initial_stat.st_size == after_stat.st_size
        
        # In-memory array preservation check
        processed_face_arr, meta_arr = preprocess_id_face(id_card)
        np.testing.assert_array_equal(id_card, id_card_copy)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_failure_handling_no_face_detected():
    """Verify that images with no face portrait return graceful error metadata."""
    blank_card = np.full((600, 400, 3), 240, dtype=np.uint8)
    cv2.putText(blank_card, "TEXT ONLY ID CARD", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    
    processed, meta = preprocess_id_face(blank_card)
    assert processed is None
    assert meta["status"] == "error"
    assert meta["error_code"] in ("NO_FACE_DETECTED", "DETECTION_FAILED")


def test_failure_handling_invalid_input():
    """Verify handling of invalid/corrupt inputs."""
    processed, meta = preprocess_id_face(b"not a valid image bytes")
    assert processed is None
    assert meta["status"] == "error"
    assert meta["error_code"] == "INVALID_IMAGE"


def test_debug_artifacts_saving():
    """Verify that save_debug writes inspection images when enabled."""
    ident = Identity(99)
    id_card = render_id_card(ident)
    
    with tempfile.TemporaryDirectory() as td:
        processed, meta = preprocess_id_face(id_card, save_debug=True, debug_dir=td)
        assert processed is not None
        assert os.path.exists(os.path.join(td, "debug_id_original.png"))
        assert os.path.exists(os.path.join(td, "debug_id_crop_raw.png"))
        assert os.path.exists(os.path.join(td, "debug_id_face_preprocessed.png"))
