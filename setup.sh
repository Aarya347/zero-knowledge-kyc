#!/usr/bin/env bash
# One-shot bootstrap. Idempotent. Fails loudly; never fakes success.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "== [1/9] tool checks =="
node --version >/dev/null || { echo "Node >=18 required"; exit 1; }
python3 --version >/dev/null || { echo "python3 required"; exit 1; }
if ! command -v circom >/dev/null; then
  echo "circom not found. Install:"
  echo "  cargo install --git https://github.com/iden3/circom --tag v2.1.6"
  echo "  or grab a release binary: https://github.com/iden3/circom/releases"
  exit 1
fi
circom --version

echo "== [2/9] npm deps =="
npm install

echo "== [3/9] compile circuits =="
bash scripts/compile.sh

echo "== [4/9] Powers of Tau (public ceremony file) =="
mkdir -p build/pot
POT=build/pot/pot15_final.ptau
if [ ! -s "$POT" ]; then
  # Circuit gate count is asserted < 2^15 by setup-zkey.sh.
  for URL in \
    "https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_15.ptau" \
    "https://storage.googleapis.com/zkevm/ptau/powersOfTau28_hez_final_15.ptau" ; do
    echo "trying $URL"
    if curl -fL --retry 3 --connect-timeout 20 -o "$POT.part" "$URL"; then mv "$POT.part" "$POT"; break; fi
    rm -f "$POT.part"
  done
fi
[ -s "$POT" ] || { echo "Could not download PoT. See README §trusted-setup."; exit 1; }
echo "PoT sha256: $(sha256sum "$POT" | cut -d' ' -f1)"
echo ">> Cross-check this digest against the perpetualpowersoftau transcript yourself."

echo "== [5/9] zkey / vkey / solidity verifier =="
bash scripts/setup-zkey.sh

echo "== [6/9] issuer keys =="
if [ ! -f keys/issuer.private.json ]; then
  mkdir -p keys && node scripts/issuer-keygen.js
else
  echo "keys exist, keeping them"
fi
chmod 600 keys/issuer.private.json || true

echo "== [7/9] python env =="
python3 -m venv .venv
if [ -d .venv/Scripts ]; then
  [ -d .venv/bin ] || cmd.exe /c "mklink /J .venv\\bin .venv\\Scripts" 2>/dev/null || true
  cp -f .venv/Scripts/python3.exe .venv/Scripts/python.exe 2>/dev/null || true
  cp -f .venv/Scripts/pip3.exe .venv/Scripts/pip.exe 2>/dev/null || true
  for cmd in python pip pytest uvicorn; do
    echo '#!/bin/sh' > .venv/Scripts/$cmd
    echo 'exec "$(dirname "$0")/'"$cmd"'.exe" "$@"' >> .venv/Scripts/$cmd
    chmod +x .venv/Scripts/$cmd
  done
fi
.venv/bin/python -m pip install --upgrade pip wheel || true
.venv/bin/pip install -r issuer-service/requirements.txt
if [ -d .venv/Scripts ]; then
  cp -f .venv/Scripts/python3.exe .venv/Scripts/python.exe 2>/dev/null || true
  cp -f .venv/Scripts/pip3.exe .venv/Scripts/pip.exe 2>/dev/null || true
  for cmd in python pip pytest uvicorn; do
    echo '#!/bin/sh' > .venv/Scripts/$cmd
    echo 'exec "$(dirname "$0")/'"$cmd"'.exe" "$@"' >> .venv/Scripts/$cmd
    chmod +x .venv/Scripts/$cmd
  done
fi

echo "== [8/9] vendored models =="
mkdir -p vendor models /tmp
if [ ! -d vendor/Silent-Face-Anti-Spoofing ]; then
  git clone --depth 1 --no-checkout https://github.com/minivision-ai/Silent-Face-Anti-Spoofing vendor/Silent-Face-Anti-Spoofing
  ( cd vendor/Silent-Face-Anti-Spoofing && git checkout HEAD -- src resources test.py README.md )
fi
ls vendor/Silent-Face-Anti-Spoofing/resources/anti_spoof_models/*.pth >/dev/null \
  || { echo "Silent-Face models missing from clone"; exit 1; }
if [ ! -d models/vosk-model-small-en-us-0.15 ]; then
  curl -fL --retry 3 -o /tmp/vosk.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
  unzip -q -o /tmp/vosk.zip -d models/
fi

echo "== [9/9] warm-up / capability report =="
.venv/bin/python -m app.warmup 2>/dev/null || ( cd issuer-service && ../.venv/bin/python -m app.warmup )

echo
echo "SETUP COMPLETE."
echo "System deps you must have via your package manager if not already present:"
echo "  tesseract-ocr, ffmpeg, (optional) anvil: https://getfoundry.sh"
command -v tesseract >/dev/null || echo "WARNING: tesseract binary not found (OCR tests/API will fail-closed)."
command -v ffmpeg    >/dev/null || echo "WARNING: ffmpeg not found (speech challenges disabled)."
