"""Document presence verification on live video clips.

Strategy: Verify that a genuine physical document was displayed during the live
session by running a lightweight text-detection and OCR-confidence pass over
candidate video frames. Does NOT run passive anti-spoofing or face matching on
the document clip.

Provides soft corroboration by loosely comparing extracted text/numbers against
the uploaded photo's clean OCR'd birthdate (logging matches without hard-rejecting
noisy video frames).
"""
import re
from typing import Optional, Sequence, Tuple
import cv2
import numpy as np
import pytesseract


class DocumentLivenessError(Exception):
    pass


def _preprocess_frame_for_ocr(frame: np.ndarray) -> np.ndarray:
    """Lightweight preprocessing to maximize text extraction from live video frames."""
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    # Gaussian blur suppresses high-frequency camera noise while keeping text strokes sharp
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def _extract_words_from_frame(frame: np.ndarray) -> list[dict]:
    """Run Tesseract and return confident word tokens."""
    try:
        proc = _preprocess_frame_for_ocr(frame)
        data = pytesseract.image_to_data(proc, config="--psm 6", output_type=pytesseract.Output.DICT)
        words = []
        n = len(data["text"])
        for i in range(n):
            txt = (data["text"][i] or "").strip()
            try:
                conf = int(data["conf"][i])
            except (ValueError, TypeError):
                conf = -1
            clean_txt = re.sub(r"[^\w\-\./:]", "", txt)
            # Require at least 2 chars, at least one alphanumeric, and confident detection (>= 50)
            if len(clean_txt) >= 2 and any(c.isalnum() for c in clean_txt) and conf >= 50:
                words.append({
                    "text": clean_txt,
                    "raw": txt,
                    "conf": conf
                })
        return words
    except Exception as e:
        print(f"[DOC_LIVENESS] Frame OCR error: {e}", flush=True)
        return []


def verify_document_presence(
    frames: Sequence[np.ndarray],
    target_dob: Optional[Tuple[int, int, int]] = None,
    min_words_required: int = 3,
    sample_count: int = 6,
) -> dict:
    """Confirm a physical document was presented in the live video clip.

    Args:
        frames: Decoded video frames from the live document-display clip.
        target_dob: Optional (year, month, day) from the uploaded ID photo for soft corroboration.
        min_words_required: Minimum confident text tokens required on a frame to confirm document presence.
        sample_count: Number of candidate frames to sample evenly across the clip.

    Returns:
        Dictionary with 'passed', 'detected_words', 'corroboration', and diagnostics.
    """
    if not frames or len(frames) == 0:
        return {
            "passed": False,
            "detected_words": 0,
            "corroboration": {"matched": False, "detail": "no frames provided"},
            "reason": "No video frames available to evaluate document presence",
        }

    # Sample frames evenly across the clip
    n_frames = len(frames)
    indices = np.linspace(0, n_frames - 1, min(sample_count, n_frames), dtype=int)
    sampled_frames = [frames[i] for i in sorted(set(indices))]

    best_frame_words = 0
    all_extracted_text = []
    all_word_tokens = []

    for idx, frame in enumerate(sampled_frames):
        words = _extract_words_from_frame(frame)
        if len(words) > best_frame_words:
            best_frame_words = len(words)
        for w in words:
            all_word_tokens.append(w["text"])
            all_extracted_text.append(w["raw"])

    passed = best_frame_words >= min_words_required

    # Soft corroboration against clean uploaded ID's DOB
    corroboration = {
        "matched": False,
        "matched_tokens": [],
        "target_dob": f"{target_dob[0]:04d}-{target_dob[1]:02d}-{target_dob[2]:02d}" if target_dob else None,
    }

    if target_dob:
        y, m, d = target_dob
        y_str = str(y)
        d_str = f"{d:02d}"
        m_str = f"{m:02d}"
        combined_blob = " ".join(all_extracted_text).upper()

        matched_tokens = []
        if y_str in combined_blob or any(y_str in t for t in all_word_tokens):
            matched_tokens.append(y_str)
        if any(tok in all_word_tokens for tok in [d_str, f"{d}"]):
            matched_tokens.append(f"day:{d}")
        if any(tok in all_word_tokens for tok in [m_str, f"{m}"]):
            matched_tokens.append(f"month:{m}")
        if "DOB" in combined_blob or "BIRTH" in combined_blob or any("DOB" in t.upper() for t in all_word_tokens):
            matched_tokens.append("DOB_LABEL")

        if matched_tokens:
            corroboration["matched"] = True
            corroboration["matched_tokens"] = matched_tokens
            print(f"[DOC_CORROBORATION] Soft match: found tokens {matched_tokens} in live video document.", flush=True)
        else:
            corroboration["matched"] = False
            print(f"[DOC_CORROBORATION] Note: No exact DOB tokens found in live video frames (soft check; proceeding).", flush=True)

    if passed:
        print(f"[DOC_LIVENESS] Passed: detected {best_frame_words} words on best frame ({len(set(all_word_tokens))} unique words in clip).", flush=True)
        return {
            "passed": True,
            "detected_words": best_frame_words,
            "total_unique_words": len(set(all_word_tokens)),
            "corroboration": corroboration,
            "reason": None,
        }
    else:
        print(f"[DOC_LIVENESS] FAILED: insufficient text detected ({best_frame_words} words found, need >={min_words_required}).", flush=True)
        return {
            "passed": False,
            "detected_words": best_frame_words,
            "total_unique_words": len(set(all_word_tokens)),
            "corroboration": corroboration,
            "reason": f"No text-bearing physical document detected in live video (found {best_frame_words} words, required {min_words_required})",
        }
