"""Active liveness: randomized head-turn challenge.

Verification uses a geometric yaw proxy: horizontal offset of the eye-pair
midpoint from the detected face-box centre, normalized by half the face width.
A valid performance must start centred, reach the required sign's extremum
above PEAK_MIN mid-video, and return to centred by the end.

This is deliberately a *coarse* heuristic (see README: it is not resistant to
targeted replay/video synthesis). It is a real verifier of real submitted
pixels, and it is pluggable - swap in a pose-regression CNN for production.
"""
import os
import cv2
import numpy as np

from . import config

FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
EYE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")


def yaw_proxy(frame_bgr):
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = FACE.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    x, y, w, h = max(map(tuple, faces), key=lambda f: f[2] * f[3])
    roi = gray[y:y + int(h * 0.6), x:x + w]
    eyes = EYE.detectMultiScale(roi, 1.1, 6, minSize=(int(w * 0.12), int(w * 0.12)))
    if len(eyes) < 2:
        return None
    eyes = sorted(eyes, key=lambda e: e[0])[:2]
    mid_x = x + (eyes[0][0] + eyes[0][2] / 2 + eyes[1][0] + eyes[1][2] / 2) / 2
    return float((mid_x - (x + w / 2)) / (w / 2))


def verify_turn(frames, direction: str):
    """direction: 'left'|'right'. Positive proxy := performer's LEFT by our
    rendering/hardware-test convention; set ACTIVE_SIGN_FLIP=1 to invert."""
    proxies = [yaw_proxy(f) for f in frames]
    tracked = [p for p in proxies if p is not None]
    if len(tracked) < config.HEAD_MIN_TRACKED_FRAMES:
        return {"passed": False, "reason": "INSUFFICIENT_FACE_SIGNAL",
                "tracked_frames": len(tracked)}
    n = len(tracked)
    seg = max(1, n // 5)
    start = float(np.mean(np.abs(tracked[:seg])))
    end = float(np.mean(np.abs(tracked[-seg:])))
    peak_pos = float(np.max(tracked))
    peak_neg = float(np.min(tracked))

    want_sign = 1.0 if direction == "left" else -1.0
    flip = os.getenv("ACTIVE_SIGN_FLIP", "0") == "1"
    if flip:
        want_sign = -want_sign

    reached = peak_pos if want_sign > 0 else peak_neg
    passed = (
        start <= config.HEAD_START_MAX
        and end <= config.HEAD_END_MAX
        and want_sign * reached >= config.HEAD_PEAK_MIN
    )
    return {
        "passed": bool(passed),
        "reason": None if passed else (
            "NO_RETURN_TO_CENTER" if end > config.HEAD_END_MAX else
            "START_NOT_CENTERED" if start > config.HEAD_START_MAX else
            "TURN_NOT_PERFORMED_OR_WRONG_DIRECTION"),
        "stats": {"start_abs_mean": round(start, 4), "end_abs_mean": round(end, 4),
                  "peak_positive": round(peak_pos, 4), "peak_negative": round(peak_neg, 4)},
    }
