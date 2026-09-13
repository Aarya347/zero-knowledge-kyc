import io
import os
import time
import json
import secrets
import tempfile
import subprocess
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .sessions import (store, SessionExpired, SessionNotFound, RateLimited,
                       register_challenge, check_rate, AVAILABLE_CHALLENGES)
from .video_utils import extract_frames, pick_best_frames, extract_audio_wav, write_temp_image, largest_face
from .passive import PassiveLiveness, VendorUnavailable
from .active_head import verify_turn
from .active_speech import SpeechVerifier, SpeechModelUnavailable
from .document_liveness import verify_document_presence
from .ocr_dob import extract_dob, DobExtractionError
from .credential_schema import validate_credential_structure
from .signer_client import issue_signature, get_public_key, SignerUnavailable

app = FastAPI(title="zk-KYC issuer", version="1.0.0")

# --- CORS middleware for local frontend development ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE = {
    "passive": None,
    "passive_error": None,
    "speech": None,
    "speech_error": None,
}


@app.on_event("startup")
def _init():
    # Mandatory component: passive liveness. Absence => fail closed at request time.
    try:
        STATE["passive"] = PassiveLiveness(config.SILENT_FACE_DIR)
    except VendorUnavailable as e:
        STATE["passive"], STATE["passive_error"] = None, str(e)
    try:
        STATE["speech"] = SpeechVerifier()
        register_challenge("speak_digits")
    except SpeechModelUnavailable as e:
        STATE["speech"], STATE["speech_error"] = None, str(e)
    register_challenge("turn_head")  # opencv-only, always available


@app.exception_handler(SessionExpired)
async def _expired(request, exc):
    return JSONResponse(status_code=400, content={"error": {"code": "SESSION_EXPIRED"}})


@app.exception_handler(SessionNotFound)
async def _notfound(request, exc):
    return JSONResponse(status_code=404, content={"error": {"code": "SESSION_NOT_FOUND"}})


@app.exception_handler(RateLimited)
async def _ratelimited(request, exc):
    return JSONResponse(status_code=429, content={"error": {"code": "RATE_LIMITED"}})


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "HTTP_ERROR", "detail": exc.detail}}
        )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_SERVER_ERROR", "detail": str(exc)}}
    )


def _err(code: str, status: int = 422, **details):
    return JSONResponse(status_code=status, content={"error": {"code": code, **details}})


def _new_challenge():
    doc_phase = {
        "phase": "document_display",
        "prompt": "Hold your physical ID card steadily in front of the camera for 3-5 seconds."
    }

    if "speak_digits" in AVAILABLE_CHALLENGES and secrets.randbelow(2) == 0:
        digits = [secrets.randbelow(10) for _ in range(3)]
        liveness_phase = {
            "phase": "liveness",
            "type": "speak_digits",
            "digits": digits,
            "prompt": "Say the number: " + "-".join(map(str, digits))
        }
        return {
            "type": "speak_digits",
            "digits": digits,
            "prompt": f"Phase 1: Say the number: {'-'.join(map(str, digits))}. Phase 2: Hold your physical ID card up to the camera.",
            "phases": [liveness_phase, doc_phase]
        }

    direction = secrets.choice(["left", "right"])
    liveness_phase = {
        "phase": "liveness",
        "type": "turn_head",
        "direction": direction,
        "prompt": f"Slowly turn your head to YOUR {direction.upper()}, then back to center."
    }
    return {
        "type": "turn_head",
        "direction": direction,
        "prompt": f"Phase 1: Slowly turn your head to YOUR {direction.upper()}, then back to center. Phase 2: Hold your physical ID card up to the camera.",
        "phases": [liveness_phase, doc_phase]
    }


@app.post("/v1/sessions")
async def create_session(request: Request):
    check_rate(request.client.host)
    ch = _new_challenge()
    sid = store.create(ch)
    return {
        "session_id": sid,
        "challenge": ch,
        "expires_in_seconds": config.SESSION_TTL_SECONDS,
        "instructions": "Record clip 1 for active face challenge, and clip 2 holding your physical ID. Submit with POST /v1/sessions/{id}/submit (multipart: id_photo, liveness_video, doc_video)."
    }


@app.get("/v1/issuer-public")
async def issuer_public():
    try:
        return get_public_key()
    except SignerUnavailable as e:
        return _err("SIGNER_UNAVAILABLE", 503, detail=str(e))


@app.get("/healthz")
async def health():
    signer_ok = False
    try:
        get_public_key(timeout=1.0)
        signer_ok = True
    except SignerUnavailable:
        pass
    return {
        "passive_liveness": "ready" if STATE["passive"] else f"MISSING ({STATE['passive_error']})",
        "document_presence": "ready",
        "speech_challenge": "ready" if STATE["speech"] else f"MISSING ({STATE['speech_error']})",
        "head_turn_challenge": "ready",
        "signer": "ready" if signer_ok else "MISSING",
        "issuance_possible": bool(STATE["passive"] and signer_ok),
    }


@app.post("/v1/sessions/{sid}/submit")
async def submit(
    sid: str,
    id_photo: UploadFile = File(...),
    liveness_video: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    doc_video: Optional[UploadFile] = File(None)
):
    # --- consume session first: one-shot, atomic, replay-proof ---
    try:
        sess = store.consume(sid)
    except (SessionExpired, SessionNotFound):
        raise

    # Handle backward-compatible field names
    live_file = liveness_video if liveness_video is not None else video
    if live_file is None:
        return _err("MISSING_LIVENESS_VIDEO", 422, detail="liveness_video (or video) is required")
    if doc_video is None:
        return _err("MISSING_DOC_VIDEO", 422, detail="doc_video is required for live document presence check")

    photo_bytes = await id_photo.read()
    live_bytes = await live_file.read()
    doc_bytes = await doc_video.read()

    if len(photo_bytes) > config.MAX_IMAGE_BYTES or len(live_bytes) > config.MAX_VIDEO_BYTES or len(doc_bytes) > config.MAX_VIDEO_BYTES:
        return _err("PAYLOAD_TOO_LARGE", 413)

    with tempfile.TemporaryDirectory() as td:
        photo_path = os.path.join(td, "id.png")
        live_path = os.path.join(td, "live.mp4")
        doc_path = os.path.join(td, "doc.mp4")

        open(photo_path, "wb").write(photo_bytes)
        open(live_path, "wb").write(live_bytes)
        open(doc_path, "wb").write(doc_bytes)

        try:
            live_frames = extract_frames(live_path, max_frames=120)
        except Exception as e:
            return _err("MEDIA_UNREADABLE", 422, detail=f"liveness video unreadable: {e}")

        try:
            doc_frames = extract_frames(doc_path, max_frames=60)
        except Exception as e:
            return _err("MEDIA_UNREADABLE", 422, detail=f"doc video unreadable: {e}")

        if len(live_frames) < config.MIN_VIDEO_FRAMES:
            return _err("TOO_FEW_FRAMES", 422, min_required=config.MIN_VIDEO_FRAMES, detail="liveness video has too few frames")

        if len(doc_frames) < 3:
            return _err("TOO_FEW_FRAMES", 422, min_required=3, detail="doc video has too few frames")

        # ---- Stage 1: PASSIVE liveness on live face clip (mandatory, fail-closed) ----
        if STATE["passive"] is None:
            return _err("ISSUER_UNAVAILABLE_PASSIVE", 503,
                        detail="anti-spoofing model not installed; refusing to issue")
        passive = STATE["passive"].check_video(live_frames, k=5)
        if not passive["genuine"]:
            return _err("PASSIVE_LIVENESS_FAILED", 422, frames=passive["frames"])

        # ---- Stage 2: ACTIVE liveness against THIS session's challenge ----
        ch = sess["challenge"]
        # Read active challenge type from phases[0] or fallback to ch
        active_phase = ch["phases"][0] if "phases" in ch and len(ch["phases"]) > 0 else ch
        ch_type = active_phase.get("type", ch.get("type"))

        if ch_type == "turn_head":
            direction = active_phase.get("direction", ch.get("direction", "left"))
            active = verify_turn(live_frames, direction)
        else:
            if STATE["speech"] is None:
                return _err("ISSUER_UNAVAILABLE_SPEECH", 503)
            try:
                wav = extract_audio_wav(live_path)
            except Exception as e:
                return _err("AUDIO_UNREADABLE", 422, detail=str(e))
            digits = active_phase.get("digits", ch.get("digits", []))
            active = STATE["speech"].verify(wav, digits)
            if os.path.exists(wav):
                os.unlink(wav)
        if not active["passed"]:
            return _err("ACTIVE_LIVENESS_FAILED", 422, reason=active.get("reason"), stats=active.get("stats"), heard=active.get("heard_digits"))

        # ---- Stage 3: OCR birthdate from uploaded clear ID photo ----
        try:
            y, m, d = extract_dob(cv2.imdecode(np.frombuffer(photo_bytes, np.uint8), cv2.IMREAD_COLOR))
        except DobExtractionError as e:
            return _err("DOB_EXTRACTION_FAILED", 422, detail=str(e))

        # ---- Stage 4: DOCUMENT PRESENCE on live ID video clip ----
        doc_result = verify_document_presence(doc_frames, target_dob=(y, m, d))
        if not doc_result["passed"]:
            return _err(
                "DOCUMENT_PRESENCE_FAILED",
                422,
                detail=doc_result.get("reason"),
                detected_words=doc_result.get("detected_words")
            )

        # ---- Stage 5: SIGN (EdDSA over Poseidon(dob, secret)) ----
        try:
            sig = issue_signature(y, m, d)
        except SignerUnavailable as e:
            return _err("SIGNER_UNAVAILABLE", 503, detail=str(e))

        credential = {
            "schema": "zkkyc-credential-v1",
            "issuer_id": config.ISSUER_ID,
            "issued_at": sig["issued_at"],
            "issuer_pub": {"ax": sig["ax"], "ay": sig["ay"]},
            "subject": {"dob": {"year": int(y), "month": int(m), "day": int(d)}},
            "holder_secret": sig["secret"],
            "signature": {"R8x": sig["R8x"], "R8y": sig["R8y"], "S": sig["S"]},
        }
        validate_credential_structure(credential)  # hard guarantee: no biometric fields
        return {"status": "issued", "credential": credential}


@app.post("/v1/proofs/generate")
async def generate_proof_endpoint(request: Request):
    """
    Accepts a credential JSON body, executes scripts/generate-proof.js as a subprocess,
    and returns the generated zero-knowledge proof bundle.
    """
    try:
        body_bytes = await request.body()
        if len(body_bytes) > 100_000:
            return _err("PAYLOAD_TOO_LARGE", 413, detail="Credential payload exceeds maximum size limit (100KB)")
        cred_data = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        return _err("INVALID_JSON", 400, detail=f"Invalid JSON request body: {e}")

    try:
        validate_credential_structure(cred_data)
    except ValueError as e:
        return _err("INVALID_CREDENTIAL_SCHEMA", 422, detail=f"Malformed credential: {e}")

    # Resolve project root path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(project_root, "scripts", "generate-proof.js")

    with tempfile.TemporaryDirectory() as td:
        cred_path = os.path.join(td, "credential.json")
        proof_path = os.path.join(td, "proof.json")

        with open(cred_path, "w", encoding="utf-8") as f:
            json.dump(cred_data, f)

        cmd = ["node", script_path, cred_path, "-o", proof_path]

        try:
            res = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return _err("PROVING_TIMEOUT", 504, detail="Proof generation timed out after 120s")
        except Exception as e:
            return _err("PROVING_EXEC_ERROR", 500, detail=str(e))

        if res.returncode != 0:
            err_msg = (res.stderr or res.stdout or "Proof generation failed").strip()
            return _err("PROVING_FAILED", 422, detail=err_msg)

        if not os.path.exists(proof_path):
            return _err("PROOF_FILE_MISSING", 500, detail="Proof file was not created by prover script")

        with open(proof_path, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        return {"status": "success", "proof": bundle}


@app.post("/v1/proofs/verify")
async def verify_proof_endpoint(request: Request):
    """
    Accepts a proof bundle JSON body, executes scripts/verify-proof.js as a subprocess,
    and returns the verification result.
    """
    try:
        proof_data = await request.json()
    except Exception as e:
        return _err("INVALID_JSON", 400, detail=f"Invalid JSON request body: {e}")

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(project_root, "scripts", "verify-proof.js")

    with tempfile.TemporaryDirectory() as td:
        proof_path = os.path.join(td, "proof.json")

        with open(proof_path, "w", encoding="utf-8") as f:
            json.dump(proof_data, f)

        cmd = ["node", script_path, proof_path]

        try:
            res = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return _err("VERIFY_TIMEOUT", 504, detail="Proof verification timed out")
        except Exception as e:
            return _err("VERIFY_EXEC_ERROR", 500, detail=str(e))

        stdout = (res.stdout or "").strip()
        stderr = (res.stderr or "").strip()

        parsed_json = {}
        for line in stdout.splitlines():
            line_s = line.strip()
            if line_s.startswith("{") and line_s.endswith("}"):
                try:
                    parsed_json = json.loads(line_s)
                    break
                except Exception:
                    pass

        is_valid = (res.returncode == 0) and parsed_json.get("ok", True)
        return {
            "status": "success" if is_valid else "rejected",
            "ok": is_valid,
            "stdout": stdout,
            "details": parsed_json,
            "error": stderr if not is_valid else None
        }

