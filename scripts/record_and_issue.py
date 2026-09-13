#!/usr/bin/env python3
"""Interactive: create a session, show the 2-phase challenge, record your webcam
(Phase 1: active face challenge, Phase 2: live ID card display), submit to the
running issuer, and print the verdict.
Usage: python scripts/record_and_issue.py http://127.0.0.1:8000 /path/to/id_photo.jpg
"""
import sys
import time
import json
import tempfile

import cv2
import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PHOTO = sys.argv[2] if len(sys.argv) > 2 else None
if not PHOTO:
    sys.exit("usage: record_and_issue.py <issuer-base-url> <id-photo-path>")

# --- sanity check the issuer is actually up before wasting the user's time ---
try:
    health = requests.get(BASE + "/healthz", timeout=5).json()
except Exception as e:
    sys.exit(f"cannot reach issuer at {BASE}: {e}\n"
             f"(start the signer + `uvicorn app.main:app` first - see README)")
print("issuer capability report:")
for k, v in health.items():
    print(f"  {k:20s} {v}")
if not health.get("issuance_possible"):
    print("\nWARNING: issuer reports issuance_possible=false. "
          "This run will very likely fail at a specific stage below - that's "
          "the honest fail-closed behavior, not a bug.")

sess = requests.post(BASE + "/v1/sessions", timeout=10).json()
if "session_id" not in sess:
    sys.exit(f"could not create session: {json.dumps(sess)}")

phases = sess["challenge"].get("phases", [sess["challenge"]])
p1 = phases[0]
p2 = phases[1] if len(phases) > 1 else {"prompt": "Hold your physical ID card up to the camera."}

cap = cv2.VideoCapture(0)
assert cap.isOpened(), "webcam unavailable"
fps = 25


def _record(prompt, duration_sec, min_frames=15):
    print(f"\n*** {prompt} ***")
    print(f"Recording starts in 3 seconds ({duration_sec}s clip)...")
    for sec in range(3, 0, -1):
        print(f"  {sec}...")
        time.sleep(1)
    frames = []
    t_end = time.time() + duration_sec
    while time.time() < t_end:
        ok, f = cap.read()
        if ok:
            frames.append(f)
            cv2.imshow(f"{prompt} (ESC to finish early)", f)
            if cv2.waitKey(1) == 27:
                break
    cv2.destroyAllWindows()
    assert len(frames) >= min_frames, f"not enough frames captured ({len(frames)} < {min_frames})"
    vp = tempfile.mktemp(suffix=".mp4")
    w = cv2.VideoWriter(vp, cv2.VideoWriter_fourcc(*"mp4v"), fps,
                        (frames[0].shape[1], frames[0].shape[0]))
    if not w.isOpened():
        sys.exit("failed to open VideoWriter - check OpenCV/ffmpeg mp4v support")
    for f in frames:
        w.write(f)
    w.release()
    return vp, len(frames)


try:
    live_vp, n1 = _record(f"PHASE 1 (Face Liveness): {p1['prompt']}", 8, min_frames=20)
    print(f"Recorded liveness clip: {n1} frames")

    doc_vp, n2 = _record(f"PHASE 2 (Document Presence): {p2['prompt']}", 5, min_frames=10)
    print(f"Recorded document clip: {n2} frames")
finally:
    cap.release()
    cv2.destroyAllWindows()

print("\nSubmitting verification to issuer (passive liveness, active challenge, OCR, and document presence)...")
with open(PHOTO, "rb") as photo_fh, open(live_vp, "rb") as live_fh, open(doc_vp, "rb") as doc_fh:
    r = requests.post(
        BASE + f"/v1/sessions/{sess['session_id']}/submit",
        files={
            "id_photo": (PHOTO, photo_fh, "image/jpeg"),
            "liveness_video": (live_vp, live_fh, "video/mp4"),
            "doc_video": (doc_vp, doc_fh, "video/mp4"),
        },
        timeout=300,
    )

print(f"\nissuer response: HTTP {r.status_code}")
try:
    body = r.json()
except ValueError:
    sys.exit(f"non-JSON response: {r.text[:500]}")

if r.status_code == 200 and body.get("status") == "issued":
    cred_path = tempfile.mktemp(suffix=".credential.json")
    with open(cred_path, "w") as fh:
        json.dump(body["credential"], fh, indent=2)
    print("CREDENTIAL ISSUED.")
    print(f"  written to: {cred_path}")
    print("  Next steps:")
    print(f"    node scripts/verify-issuer-signature.js {cred_path}")
    print(f"    node scripts/generate-proof.js {cred_path} -o proofs/mine.proof.json")
    print("    node scripts/verify-proof.js proofs/mine.proof.json")
    sys.exit(0)
else:
    err = body.get("error", body)
    print("ISSUANCE FAILED.")
    print(f"  code: {err.get('code', '<unknown>')}")
    for k, v in err.items():
        if k != "code":
            print(f"  {k}: {v}")
    sys.exit(1)
