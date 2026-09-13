import pytest

from synth import Identity, render_turn_video, render_static_video, render_speech_video
from app.video_utils import extract_frames, extract_audio_wav
from app.active_head import verify_turn
from app.active_speech import SpeechVerifier

pytestmark = pytest.mark.timeout(600)


def test_correct_left_turn_passes():
    frames = extract_frames(render_turn_video(Identity(31), "left"))
    r = verify_turn(frames, "left")
    assert r["passed"] is True, r


def test_wrong_direction_rejected():
    """SECURITY PROPERTY: performing RIGHT when LEFT was challenged fails."""
    frames = extract_frames(render_turn_video(Identity(32), "right"))
    r = verify_turn(frames, "left")
    assert r["passed"] is False


def test_no_motion_rejected():
    """SECURITY PROPERTY: a static video satisfies no head-turn challenge."""
    frames = extract_frames(render_static_video(Identity(33)))
    r = verify_turn(frames, "right")
    assert r["passed"] is False


@pytest.fixture(scope="module")
def speech():
    try:
        return SpeechVerifier()
    except Exception as e:
        pytest.skip(f"vosk model unavailable: {e}")


def test_correct_digits_pass(speech):
    import shutil
    if shutil.which("espeak-ng") is None:
        pytest.skip("espeak-ng not installed")
    path = render_speech_video(Identity(41), [4, 7, 2])
    wav = extract_audio_wav(path)
    r = speech.verify(wav, [4, 7, 2])
    assert r["passed"] is True, r


def test_wrong_order_rejected(speech):
    """SECURITY PROPERTY: digits spoken out of order fail the challenge."""
    import shutil
    if shutil.which("espeak-ng") is None:
        pytest.skip("espeak-ng not installed")
    path = render_speech_video(Identity(42), [2, 7, 4])
    wav = extract_audio_wav(path)
    r = speech.verify(wav, [4, 7, 2])
    assert r["passed"] is False, r


def test_unrelated_audio_rejected(speech):
    import shutil
    if shutil.which("espeak-ng") is None:
        pytest.skip("espeak-ng not installed")
    path = render_speech_video(Identity(43), [1, 1, 1])
    wav = extract_audio_wav(path)
    r = speech.verify(wav, [4, 7, 2])
    assert r["passed"] is False, r
