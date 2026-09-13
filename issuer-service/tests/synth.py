import os
import shutil
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SKINS = [(140, 170, 215), (110, 140, 195), (95, 120, 180), (160, 185, 225)]
HAIRS = [(30, 30, 60), (20, 45, 80), (40, 60, 40), (10, 10, 10)]
NAMES = ["ALEX MORGAN", "SAM RIVERA", "JORDAN LEE", "CASEY KIM"]

rng_global = np.random.default_rng(1234)


class Identity:
    def __init__(self, seed: int):
        r = np.random.default_rng(seed)
        self.seed = seed
        self.skin = SKINS[r.integers(len(SKINS))]
        self.hair = HAIRS[r.integers(len(HAIRS))]
        self.name = NAMES[r.integers(len(NAMES))]
        self.eye_gap = float(r.uniform(0.38, 0.46))
        self.mouth_w = float(r.uniform(0.24, 0.34))


def draw_face(identity: Identity, yaw: float, size: int = 420, rng=None) -> np.ndarray:
    rng = rng or np.random.default_rng(identity.seed)
    W = H = size
    img = np.full((H, W, 3), (95, 130, 175), dtype=np.uint8)
    img += rng.integers(-3, 4, img.shape, dtype=np.int16).astype(np.uint8)
    cx, cy = W // 2, int(H * 0.52)
    shrink = 1.0 - 0.30 * abs(yaw)
    fw, fh = int(W * 0.42 * shrink), int(H * 0.52)
    cv2.ellipse(img, (cx, cy), (fw, fh), 0, 0, 360, identity.skin, -1)
    cv2.ellipse(img, (cx, cy - int(fh * 0.55)), (int(fw * 1.04), int(fh * 0.62)),
                0, 180, 360, identity.hair, -1)
    dx = int(yaw * W * 0.16)
    ey = cy - int(fh * 0.22)
    gap = int(fw * identity.eye_gap)
    for s in (-1, 1):
        ex = cx + s * gap + dx
        cv2.ellipse(img, (ex, ey), (int(fw * 0.17), int(fh * 0.11)), 0, 0, 360, (250, 250, 250), -1)
        pdx = int(-yaw * fw * 0.05)
        cv2.circle(img, (ex + pdx, ey), max(2, int(fw * 0.075)), (15, 15, 15), -1)
        cv2.rectangle(img, (ex - int(fw * 0.20), ey - int(fh * 0.20)),
                      (ex + int(fw * 0.20), ey - int(fh * 0.13)), identity.hair, -1)
    nx = cx + int(dx * 1.6)
    shade = tuple(int(c * 0.75) for c in identity.skin)
    cv2.line(img, (nx, cy - int(fh * 0.05)), (nx + (int(np.sign(dx or 1) * fw * 0.07) if dx else 0),
                                              cy + int(fh * 0.16)), shade, 3)
    mw = int(fw * identity.mouth_w)
    cv2.ellipse(img, (cx + dx, cy + int(fh * 0.44)), (mw, int(fh * 0.08)), 0, 0, 180, (70, 70, 140), -1)
    return img


def render_id_card(identity: Identity, dob=(1990, 5, 14)) -> np.ndarray:
    face = draw_face(identity, 0.0)
    card = Image.new("RGB", (640, 900), (235, 235, 240))
    d = ImageDraw.Draw(card)
    try:
        font = ImageFont.load_default(size=34)
        small = ImageFont.load_default(size=26)
    except TypeError:
        font = ImageFont.load_default(); small = font
    d.rectangle([40, 40, 600, 860], fill=(255, 255, 255), outline=(60, 60, 60), width=3)
    d.text((70, 80), "REPUBLIC OF TESTLAND", fill=(20, 20, 20), font=font)
    d.text((70, 130), "NATIONAL IDENTITY CARD", fill=(60, 60, 60), font=small)
    pil_face = Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB)).resize((260, 260))
    card.paste(pil_face, (340, 200))
    d.text((70, 220), f"NAME: {identity.name}", fill=(10, 10, 10), font=small)
    d.text((70, 280), "DOB: {:04d}-{:02d}-{:02d}".format(*dob), fill=(10, 10, 10), font=font)
    d.text((70, 350), "DOC NO: TL-%08d" % identity.seed, fill=(10, 10, 10), font=small)
    d.text((70, 800), "NOT A REAL DOCUMENT", fill=(120, 30, 30), font=small)
    return cv2.cvtColor(np.array(card), cv2.COLOR_RGB2BGR)


def _video_writer(path, fps, size):
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not vw.isOpened():
        raise RuntimeError("VideoWriter failed")
    return vw


def render_turn_video(identity: Identity, direction: str, fps=25, seconds=3.6) -> str:
    """Yaw profile 0 -> +/-1 -> 0 with easing and jitter."""
    sign = 1.0 if direction == "left" else -1.0
    n = int(fps * seconds)
    path = tempfile.mktemp(suffix=".mp4")
    vw = _video_writer(path, fps, (420, 420))
    rng = np.random.default_rng(identity.seed)
    for i in range(n):
        t = i / (n - 1)
        yaw = sign * np.sin(np.pi * t) ** 2 * (0.98 + 0.02 * rng.standard_normal())
        vw.write(draw_face(identity, float(yaw), rng=rng))
    vw.release()
    return path


def render_static_video(identity: Identity, fps=25, seconds=3.6) -> str:
    n = int(fps * seconds)
    path = tempfile.mktemp(suffix=".mp4")
    vw = _video_writer(path, fps, (420, 420))
    rng = np.random.default_rng(identity.seed)
    for _ in range(n):
        vw.write(draw_face(identity, float(rng.uniform(-0.02, 0.02)), rng=rng))
    vw.release()
    return path


_ESPEAK_DIGITS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
                  5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}


def render_speech_video(identity: Identity, digits, fps=25, seconds=4.0) -> str:
    if shutil.which("espeak-ng") is None or shutil.which("ffmpeg") is None:
        raise RuntimeError("espeak-ng/ffmpeg required for speech fixtures")
    phrase = " ".join(_ESPEAK_DIGITS[d] for d in digits)
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(["espeak-ng", "-w", wav, "-s", "110", phrase], check=True,
                   capture_output=True)
    video_only = render_static_video(identity, fps=fps, seconds=seconds)
    out = tempfile.mktemp(suffix=".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video_only, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-shortest", out], check=True,
                   capture_output=True)
    os.unlink(video_only); os.unlink(wav)
    return out


def render_flat_photo(identity: Identity) -> str:
    """Printed-photo / screen-replay surrogate: flattened shading kills the
    3-D cues passive liveness relies on."""
    frame = draw_face(identity, 0.0).astype(np.float32)
    blur = cv2.GaussianBlur(frame, (0, 0), 12)
    flat = frame / (blur + 1e-3) * 128.0
    flat = np.clip(flat, 0, 255).astype(np.uint8)
    path = tempfile.mktemp(suffix=".jpg")
    cv2.imwrite(path, flat, [cv2.IMWRITE_JPEG_QUALITY, 55])
    return path
