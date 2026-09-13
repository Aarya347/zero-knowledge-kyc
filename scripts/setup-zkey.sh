#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
snark() {
  node "$ROOT/node_modules/snarkjs/cli.js" "$@"
}
POT="$ROOT/build/pot/pot15_final.ptau"

snark plonk setup "$ROOT/build/main/age_credential.r1cs" "$POT" "$ROOT/build/main/age_credential.zkey"
snark zkey export verificationkey "$ROOT/build/main/age_credential.zkey" "$ROOT/build/main/vkey.json"

snark plonk setup "$ROOT/build/variant/age_credential_variant.r1cs" "$POT" "$ROOT/build/variant/age_credential_variant.zkey"
snark zkey export verificationkey "$ROOT/build/variant/age_credential_variant.zkey" "$ROOT/build/variant/vkey.json"

# Auto-generated on-chain verifier (NOT hand-written).
mkdir -p "$ROOT/contracts"
snark zkey export solidityverifier "$ROOT/build/main/age_credential.zkey" "$ROOT/contracts/PlonkVerifier.sol.raw"

# Normalize pragma so a single pinned modern solc compiles whatever snarkjs emitted,
# and pin the contract name for the registry wrapper. Execution correctness of the
# normalized file is itself proven by test/onchain.test.js on a real EVM.
sed -E 's/^pragma solidity .*;/pragma solidity ^0.8.20;/' "$ROOT/contracts/PlonkVerifier.sol.raw" \
  | sed -E 's/^contract (Verifier|PlonkVerifier)/contract PlonkVerifier/' \
  > "$ROOT/contracts/PlonkVerifier.sol"
rm "$ROOT/contracts/PlonkVerifier.sol.raw"
grep -q "^contract PlonkVerifier" "$ROOT/contracts/PlonkVerifier.sol"
echo "zkey + verifier contract ready"
