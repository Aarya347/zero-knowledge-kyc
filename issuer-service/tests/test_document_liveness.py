import numpy as np
import pytest

from synth import Identity, render_id_card, draw_face
from app.document_liveness import verify_document_presence

pytestmark = pytest.mark.timeout(300)


def test_rendered_id_card_passes_document_presence():
    """PROPERTY: Video frames showing a rendered ID card contain text and pass document presence."""
    ident = Identity(42)
    id_card = render_id_card(ident, dob=(1995, 8, 20))
    # Simulate a 5-frame video clip of the held ID card
    frames = [id_card.copy() for _ in range(5)]
    res = verify_document_presence(frames, target_dob=(1995, 8, 20))

    assert res["passed"] is True
    assert res["detected_words"] >= 3
    assert res["corroboration"]["matched"] is True
    assert "DOB_LABEL" in res["corroboration"]["matched_tokens"] or "1995" in res["corroboration"]["matched_tokens"]


def test_face_only_frames_fail_document_presence():
    """SECURITY PROPERTY / USER ERROR: If the user leaves only their face in frame
    and forgets to present their physical ID card, document presence MUST fail."""
    ident = Identity(7)
    face_img = draw_face(ident, yaw=0.0)
    # 5 frames of just a face, zero text
    frames = [face_img.copy() for _ in range(5)]
    res = verify_document_presence(frames, target_dob=(1990, 5, 14))

    assert res["passed"] is False
    assert res["detected_words"] < 3
    assert "No text-bearing physical document detected" in res["reason"]


def test_blank_and_noise_frames_fail_document_presence():
    """PROPERTY: Blank/noisy frames without text fail document presence."""
    noise_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frames = [noise_frame, blank_frame, noise_frame]
    res = verify_document_presence(frames)

    assert res["passed"] is False
    assert res["detected_words"] < 3


def test_soft_corroboration_non_matching_dob_does_not_hard_reject():
    """PROPERTY: When document text is present but DOB numbers don't match (e.g. noisy video OCR),
    document presence STILL passes (soft corroboration is non-blocking)."""
    ident = Identity(15)
    # ID card rendered with DOB 1988-12-01
    id_card = render_id_card(ident, dob=(1988, 12, 1))
    frames = [id_card.copy() for _ in range(4)]
    # Target DOB requested is 2001-01-01 (different year)
    res = verify_document_presence(frames, target_dob=(2001, 1, 1))

    assert res["passed"] is True  # Document was genuinely present
