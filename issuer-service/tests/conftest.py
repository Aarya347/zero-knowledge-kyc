import os
import socket
import subprocess
import sys
import time
import pathlib

import pytest
import requests

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "issuer-service"))  # import `app` and `tests.synth`

TOKEN = "test-token-0123456789abcdef"
SIGNER_PORT = 7391
SIGNER_URL = f"http://127.0.0.1:{SIGNER_PORT}"
os.environ.setdefault("SIGNER_TOKEN", TOKEN)
os.environ.setdefault("SIGNER_URL", SIGNER_URL)


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture(scope="session")
def signer_server():
    """Starts the real Node EdDSA signer against a THROWAWAY keypair.
    This is test infrastructure only; the production issuer uses keys/."""
    keys = HERE / ".tmp-keys"
    keys.mkdir(exist_ok=True)
    priv = keys / "issuer.private.json"
    pub = keys / "issuer.public.json"
    subprocess.run(["node", str(ROOT / "scripts" / "issuer-keygen.js")], cwd=ROOT,
                   env={**os.environ, "ZKKYC_KEYS_DIR": str(keys)}, check=False)
    if not priv.exists():
        import json
        r_p = ROOT.as_posix()
        k_p = keys.as_posix()
        node_script = (
            "const{makeIssuer}=require('%s/scripts/lib/crypto');const fs=require('fs');"
            "(async()=>{const k=await makeIssuer();fs.mkdirSync('%s',{recursive:true});"
            "fs.writeFileSync('%s/issuer.private.json',JSON.stringify({private_key_hex:k.prv.toString('hex')}));"
            "fs.writeFileSync('%s/issuer.public.json',JSON.stringify({ax:k.ax,ay:k.ay}));})();"
        ) % (r_p, k_p, k_p, k_p)
        subprocess.run(["node", "-e", node_script], cwd=ROOT, check=True)
    port = _free_port()
    env = {**os.environ, "SIGNER_PORT": str(port), "SIGNER_TOKEN": TOKEN,
           "SIGNER_PRIVKEY": str(priv)}
    proc = subprocess.Popen(["node", str(ROOT / "issuer-service" / "signer" / "server.js")],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if requests.get(base + "/pubkey", headers={"x-signer-token": TOKEN}, timeout=1).ok:
                break
        except Exception:
            time.sleep(0.3)
    else:
        proc.kill()
        raise RuntimeError("signer did not start")
    yield {"base": base, "pub": json_load(pub)}
    proc.terminate(); proc.wait(timeout=10)


def json_load(p):
    import json
    return json.loads(open(p).read())


@pytest.fixture(scope="session")
def signer_env(signer_server):
    os.environ["SIGNER_URL"] = signer_server["base"]
    os.environ["SIGNER_TOKEN"] = TOKEN
    return signer_server
