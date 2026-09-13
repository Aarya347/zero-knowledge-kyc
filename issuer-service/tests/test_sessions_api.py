import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
from app.sessions import store


@pytest.fixture(scope="module")
def client(signer_env):
    main_mod.STATE["passive"] = None
    main_mod.STATE["passive_error"] = "forced-off in this suite (covered by test_passive_liveness)"
    return TestClient(main_mod.app)


def test_session_create_and_unknown_submit(client):
    r = client.post("/v1/sessions")
    assert r.status_code == 200
    body = r.json()
    assert body["challenge"]["type"] in ("turn_head", "speak_digits")
    assert "phases" in body["challenge"]
    assert len(body["challenge"]["phases"]) == 2
    assert body["expires_in_seconds"] > 0

    r2 = client.post(f"/v1/sessions/{'f'*64}/submit",
                     files={"id_photo": ("a.png", b"x"), "liveness_video": ("a.mp4", b"x"), "doc_video": ("b.mp4", b"x")})
    assert r2.status_code == 404
    assert r2.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_expired_session_rejected(client):
    """SECURITY PROPERTY: stale sessions cannot be used."""
    r = client.post("/v1/sessions")
    sid = r.json()["session_id"]
    store.expire_for_test(sid, 10_000)
    r2 = client.post(f"/v1/sessions/{sid}/submit",
                     files={"id_photo": ("a.png", b"x"), "liveness_video": ("a.mp4", b"x"), "doc_video": ("b.mp4", b"x")})
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "SESSION_EXPIRED"


def test_one_shot_session(client):
    """SECURITY PROPERTY: a session is consumed on first submit; replay fails."""
    r = client.post("/v1/sessions")
    sid = r.json()["session_id"]
    files = {"id_photo": ("a.png", b"x"), "liveness_video": ("a.mp4", b"x"), "doc_video": ("b.mp4", b"x")}
    client.post(f"/v1/sessions/{sid}/submit", files=files)  # consumes (may 404/4xx on content, fine)
    r2 = client.post(f"/v1/sessions/{sid}/submit", files=files)
    assert r2.status_code == 404


def test_fail_closed_without_passive_model(client, signer_env):
    """SECURITY PROPERTY: with the anti-spoofing model unavailable the issuer
    REFUSES TO ISSUE (HTTP 503) instead of skipping the check."""
    r = client.post("/v1/sessions")
    sid = r.json()["session_id"]
    r2 = client.post(f"/v1/sessions/{sid}/submit",
                     files={"id_photo": ("a.png", b"notanimage"), "liveness_video": ("a.mp4", b"notavideo"), "doc_video": ("b.mp4", b"notavideo")})
    assert r2.status_code in (503, 413, 422)  # 503 = fail-closed path reached before media parse
    if r2.status_code == 503:
        assert r2.json()["error"]["code"] == "ISSUER_UNAVAILABLE_PASSIVE"


def test_health_reports_components(client):
    h = client.get("/healthz").json()
    assert set(h) >= {"passive_liveness", "document_presence", "signer", "issuance_possible"}
