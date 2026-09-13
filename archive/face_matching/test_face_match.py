import pytest

from synth import Identity, render_id_card, draw_face
from app.video_utils import write_temp_image
from app.face_match import FaceMatcher

pytestmark = pytest.mark.timeout(1200)


@pytest.fixture(scope="module")
def matcher():
    return FaceMatcher()


def _tmp_png(bgr):
    return write_temp_image(__import__("cv2").imencode(".png", bgr)[1].tobytes())


def test_same_identity_matches(matcher):
    """PROPERTY: the same rendered identity, under mild pose/lighting variation,
    is accepted by the face-match stage."""
    import cv2
    ident = Identity(11)
    ref = _tmp_png(render_id_card(ident))
    probe = _tmp_png(draw_face(ident, 0.15))
    verified, dist = matcher.same_person(ref, cv2.imread(probe))
    print("same-identity distance:", dist)
    assert verified is True


def test_different_identity_rejected(matcher):
    """SECURITY PROPERTY: a different face does NOT satisfy face-match.
    (Attack simulation: impostor presents someone else's ID + own video.)"""
    import cv2
    a, b = Identity(5), Identity(50)
    ref = _tmp_png(render_id_card(a))
    probe = _tmp_png(draw_face(b, 0.05))
    verified, dist = matcher.same_person(ref, cv2.imread(probe))
    print("cross-identity distance:", dist)
    assert verified is False

