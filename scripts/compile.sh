#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/build/main" "$ROOT/build/variant"
( cd "$ROOT" && circom circuit/age_credential.circom \
  --r1cs --wasm --sym --output build/main )
( cd "$ROOT" && circom circuit/age_credential_variant.circom \
  --r1cs --wasm --sym --output build/variant )

# Gate-count guard: must satisfy the PoT size we download (2^15).
INFO=$(node "$ROOT/node_modules/snarkjs/cli.js" r1cs info "$ROOT/build/main/age_credential.r1cs")
echo "$INFO"
CONSTRAINTS=$(echo "$INFO" | grep -oP '# of Constraints:\s*\K\d+')
[ "${CONSTRAINTS:-0}" -lt 32768 ] || { echo "Circuit too big for pot15 ($CONSTRAINTS >= 32768)"; exit 1; }
