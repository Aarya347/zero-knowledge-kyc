"""THE definitive issuer acceptance test: a real human, a real webcam.
Run:  ENABLE_HARDWARE_TESTS=1 pytest -m hardware
You will be shown a challenge; perform it; then hold your physical ID card;
both clips are submitted to a locally-running issuer."""
import os
import pytest

pytestmark = [pytest.mark.hardware, pytest.mark.timeout(600)]

ENABLED = os.environ.get("ENABLE_HARDWARE_TESTS") == "1"


def _record_clip(cap, duration_seconds=8, prompt=""):
    import cv2, time
    print(f"\n>>> {prompt}")
    print(f"Recording for {duration_seconds} seconds...")
    frames = []
    fps = 25
    t_end = time.time() + duration_seconds
    while time.time() < t_end:
        ok, f = cap.read()
        if ok:
            frames.append(f)
    assert len(frames) >= 15, "not enough frames captured"
    import tempfile
    vp = tempfile.mktemp(suffix=".mp4")
    w = cv2.VideoWriter(vp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (frames[0].shape[1], frames[0].shape[0]))
    for f in frames:
        w.write(f)
    w.release()
    return vp


@pytest.mark.skipif(not ENABLED, reason="set ENABLE_HARDWARE_TESTS=1 with a webcam attached")
def test_live_human_issues_credential():
    import cv2, time, requests
    base_url = os.environ.get("ISSUER_BASE_URL", "http://127.0.0.1:8000")
    id_photo_path = os.environ["HW_ID_PHOTO_PATH"]  # a photo file of your real ID

    s = requests.Session()
    sess = s.post(base_url + "/v1/sessions", timeout=10).json()
    phases = sess["challenge"].get("phases", [sess["challenge"]])
    p1 = phases[0]
    p2 = phases[1] if len(phases) > 1 else {"prompt": "Hold ID card steadily"}

    cap = cv2.VideoCapture(0)
    assert cap.isOpened(), "webcam unavailable"

    try:
        # Phase 1: Liveness Challenge
        live_vp = _record_clip(cap, 8, f"PHASE 1: {p1['prompt']}")

        # Phase 2: Document Display
        print("\nGet ready to show your physical ID card...")
        time.sleep(2)
        doc_vp = _record_clip(cap, 5, f"PHASE 2: {p2['prompt']}")
    finally:
        cap.release()

    r = s.post(
        base_url + f"/v1/sessions/{sess['session_id']}/submit",
        files={
            "id_photo": open(id_photo_path, "rb"),
            "liveness_video": open(live_vp, "rb"),
            "doc_video": open(doc_vp, "rb"),
        },
        timeout=300
    )
    print("issuer response:", r.status_code, r.text[:400])
    assert r.status_code == 200, "live human failed issuance - inspect error code"
    assert r.json()["status"] == "issued"
