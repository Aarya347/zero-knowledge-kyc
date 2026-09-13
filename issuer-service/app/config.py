import os

SIGNER_URL = os.environ.get("SIGNER_URL", "http://127.0.0.1:7391")
SIGNER_TOKEN = os.environ.get("SIGNER_TOKEN", "")
SILENT_FACE_DIR = os.environ.get(
    "SILENT_FACE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "Silent-Face-Anti-Spoofing"))
VOSK_MODEL_DIR = os.environ.get(
    "VOSK_MODEL_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "models", "vosk-model-small-en-us-0.15"))

SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "300"))
MAX_VIDEO_BYTES = 60 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_VIDEO_FRAMES = 30
RATE_LIMIT_PER_HOUR = 20

# Head-turn geometric estimator calibration (see README caveats)
HEAD_START_MAX = float(os.environ.get("HEAD_START_MAX", "0.08"))
HEAD_PEAK_MIN = float(os.environ.get("HEAD_PEAK_MIN", "0.15"))
HEAD_END_MAX = float(os.environ.get("HEAD_END_MAX", "0.10"))
HEAD_MIN_TRACKED_FRAMES = 10

ISSUER_ID = os.environ.get("ISSUER_ID", "did:zkkyc:issuer-1")

# Date-format precedence when the ID shows an ambiguous numeric date.
ID_DATE_FORMAT = os.environ.get("ID_DATE_FORMAT", "dmy")  # dmy | mdy | ymd

# ID Document Face Preprocessing settings
PREPROCESS_ID_FACE = os.environ.get("PREPROCESS_ID_FACE", "true").lower() in ("true", "1", "yes")
DEBUG_PREPROCESSING = os.environ.get("DEBUG_PREPROCESSING", "false").lower() in ("true", "1", "yes")
DEBUG_DIR = os.environ.get("DEBUG_DIR", "")

