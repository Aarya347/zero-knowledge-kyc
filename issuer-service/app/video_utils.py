import tempfile, os, shutil, subprocess
import cv2
import numpy as np

FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


class MediaError(Exception):
    pass


def extract_frames(path: str, max_frames: int = 150):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise MediaError("cannot open video")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    frames = []
    idx = 0
    stride = max(1, total // max_frames) if total else 1
    while True:
        ret = cap.grab()
        if not ret:
            break
        if idx % stride == 0:
            ok, frame = cap.retrieve()
            if ok:
                frames.append(frame)
        idx += 1
    cap.release()
    if len(frames) < 5:
        raise MediaError("too few decodable frames")
    return frames


def largest_face(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    return max(map(tuple, faces), key=lambda f: f[2] * f[3])


def sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def pick_best_frames(frames, k=3):
    scored = []
    for i, f in enumerate(frames):
        fc = largest_face(f)
        area = fc[2] * fc[3] if fc else 1
        scored.append((area * (1.0 + sharpness(f) / 100.0), i))
    scored.sort(reverse=True)
    picked = sorted({i for _, i in scored[:k]})
    return [frames[i] for i in picked]


def extract_audio_wav(video_path: str) -> str:
    if shutil.which("ffmpeg") is None:
        raise MediaError("ffmpeg not installed")
    fd, out = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video_path,
                        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", out],
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        os.unlink(out)
        raise MediaError("audio extraction failed: " + r.stderr.decode()[:200])
    return out


def write_temp_image(bgr_or_pil_bytes, ext=".png"):
    fd, out = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    with open(out, "wb") as fh:
        fh.write(bgr_or_pil_bytes)
    return out
