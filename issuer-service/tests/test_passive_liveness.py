import os
import pytest

from synth import Identity, render_flat_photo
from app.passive import PassiveLiveness, VendorUnavailable
from app import config

pytestmark = pytest.mark.timeout(600)


@pytest.fixture(scope="module")
def passive():
    try:
        return PassiveLiveness(config.SILENT_FACE_DIR)
    except VendorUnavailable as e:
        pytest.fail(f"passive liveness vendor missing - run setup.sh. ({e})")


def test_printed_photo_style_attack_rejected(passive):
    """SECURITY PROPERTY: a flat, print/screen-like facial image is classified
    as an ATTACK by the real MiniFASNet ensemble. This is a real model verdict,
    not a canned one."""
    import cv2
    img = cv2.imread(render_flat_photo(Identity(51)))
    genuine, label, score = passive.check_frame(img)
    print("attack-sample verdict:", {"label": label, "score": score})
    assert genuine is False


def test_real_genuine_samples_accepted_if_provided(passive):
    """Genuine-acceptance CANNOT be honestly demonstrated with synthetic media:
    renders ARE screen replays. Supply real captured selfies via
    LIVENESS_REAL_SAMPLES_DIR (jpg/png of a real person, camera-captured) to run
    this assertion. Until then this test skips - see README limitations."""
    d = os.environ.get("LIVENESS_REAL_SAMPLES_DIR")
    if not d or not os.path.isdir(d):
        pytest.skip("LIVENESS_REAL_SAMPLES_DIR not set - genuine-accept rate untested "
                    "without real capture data (deliberate, see README)")
    import cv2, glob
    files = glob.glob(os.path.join(d, "*.jpg")) + glob.glob(os.path.join(d, "*.png"))
    assert files, "sample dir empty"
    for f in files:
        genuine, label, score = passive.check_frame(cv2.imread(f))
        assert genuine is True, f"{f} misclassified as attack (label={label}, score={score})"


def test_fail_closed_when_vendor_missing():
    """SECURITY PROPERTY: a broken installation disables issuance rather than
    silently passing everyone."""
    with pytest.raises(VendorUnavailable):
        PassiveLiveness("/nonexistent/vendor/path")
