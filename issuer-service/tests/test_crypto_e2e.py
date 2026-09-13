import json
import os
import pathlib
import subprocess
import tempfile

import pytest
import requests

from synth import Identity  # noqa: F401  (documents intent; media not needed here)

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
pytestmark = pytest.mark.timeout(1800)


def _run_node(script, *args, expect=0):
    r = subprocess.run(["node", str(ROOT / "scripts" / script), *[str(a) for a in args]],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ})
    assert r.returncode == expect, f"{script} rc={r.returncode}\nstdout:{r.stdout}\nstderr:{r.stderr}"
    return r


def test_issue_verify_prove_verify_chain(signer_env):
    base = signer_env["base"]
    tok = os.environ["SIGNER_TOKEN"]

    pub = requests.get(base + "/pubkey", headers={"x-signer-token": tok}).json()
    sig = requests.post(base + "/issue", json={"year": 1990, "month": 5, "day": 14},
                        headers={"x-signer-token": tok}).json()

    cred = {
        "schema": "zkkyc-credential-v1",
        "issuer_id": "did:zkkyc:test",
        "issued_at": sig["issued_at"],
        "issuer_pub": {"ax": sig["ax"], "ay": sig["ay"]},
        "subject": {"dob": {"year": 1990, "month": 5, "day": 14}},
        "holder_secret": sig["secret"],
        "signature": {"R8x": sig["R8x"], "R8y": sig["R8y"], "S": sig["S"]},
    }
    with tempfile.TemporaryDirectory() as td:
        keys_dir = pathlib.Path(td) / "keys"
        keys_dir.mkdir()
        (keys_dir / "issuer.public.json").write_text(json.dumps(pub))
        cred_file = pathlib.Path(td) / "cred.json"
        cred_file.write_text(json.dumps(cred))

        # 1) third-party signature verification
        _run_node("verify-issuer-signature.js", cred_file, "--issuer-pub", keys_dir / "issuer.public.json")

        # 2) tamper => must fail
        bad = dict(cred); bad["subject"] = {"dob": {"year": 1980, "month": 5, "day": 14}}
        bad_file = pathlib.Path(td) / "bad.json"; bad_file.write_text(json.dumps(bad))
        _run_node("verify-issuer-signature.js", bad_file, "--issuer-pub",
                  keys_dir / "issuer.public.json", expect=1)

        # 3) prove (real snarkjs PLONK) - requires built artifacts from setup.sh
        zkey = ROOT / "build" / "main" / "age_credential.zkey"
        if not zkey.exists():
            pytest.fail("build artifacts missing; run bash setup.sh first")

        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from lib import util, proof as proof_lib
        orig = util.PATHS["issuerPublic"]
        util.PATHS["issuerPublic"] = str(keys_dir / "issuer.public.json")
        try:
            bundle = proof_lib.generateProofBundle(str(cred_file))
        finally:
            util.PATHS["issuerPublic"] = orig
        proof_file = pathlib.Path(td) / "proof.json"
        proof_file.write_text(json.dumps(bundle))

        # 4) verify with pinned issuer + freshness policy
        r = _run_node("verify-proof.js", proof_file, "--issuer-pub", keys_dir / "issuer.public.json")
        assert "VERIFIED" in r.stdout

        # 5) underage dob cannot even generate a witness (circuit constraint)
        sig_u = requests.post(base + "/issue", json={"year": 2012, "month": 1, "day": 1},
                              headers={"x-signer-token": tok}).json()
        cred_u = dict(cred)
        cred_u.update(subject={"dob": {"year": 2012, "month": 1, "day": 1}},
                      holder_secret=sig_u["secret"],
                      signature={"R8x": sig_u["R8x"], "R8y": sig_u["R8y"], "S": sig_u["S"]},
                      issued_at=sig_u["issued_at"])
        cu = pathlib.Path(td) / "under.json"; cu.write_text(json.dumps(cred_u))
        try:
            proof_lib.generateProofBundle(str(cu))
            raised = False
        except Exception:
            raised = True
        assert raised, "underage credential unexpectedly produced a valid witness!"
