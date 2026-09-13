"use strict";
const fs = require("fs");
const path = require("path");
const os = require("os");
const { PATHS, snark, assertExists, sha256File, cutoffPacked, daysBetweenPacked } = require("./util");
const { credentialMessage, verifySignature } = require("./crypto");

function checkProverArtifacts() {
  assertExists(PATHS.wasm, "compiled circuit wasm");
  assertExists(PATHS.zkey, "proving key (.zkey)");
  assertExists(PATHS.vkey, "verification key (vkey.json)");
}

// Prove from a credential file.
async function generateProofBundle(credentialFile, { outDir = path.join(os.tmpdir(), `zkkyc-${Date.now()}`), issuerPubFile = null } = {}) {
  checkProverArtifacts();
  const cred = JSON.parse(fs.readFileSync(credentialFile, "utf8"));

  if (issuerPubFile) {
    const issuerPub = JSON.parse(fs.readFileSync(issuerPubFile, "utf8"));
    if (BigInt(cred.issuer_pub.ax) !== BigInt(issuerPub.ax) ||
        BigInt(cred.issuer_pub.ay) !== BigInt(issuerPub.ay)) {
      throw new Error("ISSUER_KEY_MISMATCH: credential was not signed by the locally-pinned issuer key");
    }
  }

  const msg = await credentialMessage(cred.subject.dob, cred.holder_secret);
  if (!(await verifySignature(msg, cred.signature, cred.issuer_pub.ax, cred.issuer_pub.ay))) {
    throw new Error("BAD_CREDENTIAL_SIGNATURE: EdDSA verification failed before proving");
  }

  const refPacked = cutoffPacked();
  const input = {
    ax: cred.issuer_pub.ax, ay: cred.issuer_pub.ay, refPacked: String(refPacked),
    year: String(cred.subject.dob.year), month: String(cred.subject.dob.month), day: String(cred.subject.dob.day),
    secret: cred.holder_secret,
    S: cred.signature.S, R8x: cred.signature.R8x, R8y: cred.signature.R8y,
  };

  fs.mkdirSync(outDir, { recursive: true });
  try {
    const inputJson = path.join(outDir, "input.json");
    const wtns = path.join(outDir, "witness.wtns");
    const proofJson = path.join(outDir, "proof.json");
    const publicJson = path.join(outDir, "public.json");
    fs.writeFileSync(inputJson, JSON.stringify(input));

    const w = await snark(["wtns", "calculate", PATHS.wasm, inputJson, wtns]); // throws if constraints unsatisfied
    void w;
    await snark(["plonk", "prove", PATHS.zkey, wtns, proofJson, publicJson]);

    const proof = JSON.parse(fs.readFileSync(proofJson, "utf8"));
    const publicSignals = JSON.parse(fs.readFileSync(publicJson, "utf8"));
    if (publicSignals.length !== 3) throw new Error(`unexpected public signal count ${publicSignals.length}`);

    const bundle = {
      schema: "zkkyc-proof-v1",
      snark: "plonk",
      proof,
      publicSignals,
      meta: {
        refPacked: String(refPacked),
        generated_at: new Date().toISOString(),
        vkey_sha256: sha256File(PATHS.vkey),
        circuit_sha256: sha256File(path.join(require("./util").ROOT, "circuit/age_credential.circom")),
      },
    };
    return bundle;
  } finally {
    try { fs.rmSync(outDir, { recursive: true, force: true }); } catch (_) {}
  }
}

// Full verifier-side policy: trust anchor, freshness, VK integrity, then the
// actual SNARK verification. Returns { ok, reason?, details }.
async function verifyBundle(bundle, { issuerPubFile = PATHS.issuerPublic, maxSkewDays = 2, nowMs = Date.now(),
                                      vkeyFile = PATHS.vkey } = {}) {
  const fail = (reason, details) => ({ ok: false, reason, details });
  if (!bundle || bundle.schema !== "zkkyc-proof-v1" || bundle.snark !== "plonk")
    return fail("BAD_BUNDLE_FORMAT");
  if (!Array.isArray(bundle.publicSignals) || bundle.publicSignals.length !== 3)
    return fail("BAD_PUBLIC_SIGNALS", "expected [ax, ay, refPacked]");

  const issuerPub = JSON.parse(fs.readFileSync(issuerPubFile, "utf8"));
  if (BigInt(bundle.publicSignals[0]) !== BigInt(issuerPub.ax) ||
      BigInt(bundle.publicSignals[1]) !== BigInt(issuerPub.ay))
    return fail("ISSUER_KEY_MISMATCH", "proof commits to a different issuer public key than the pinned trust anchor");

  if (bundle.meta?.refPacked !== String(bundle.publicSignals[2]))
    return fail("META_TAMPERED", "meta.refPacked disagrees with public signals");

  const expected = cutoffPacked(nowMs);
  const drift = daysBetweenPacked(Number(bundle.publicSignals[2]), expected);
  if (drift > maxSkewDays)
    return fail("REF_DATE_STALE", { drift_days: drift, max_allowed: maxSkewDays });

  if (sha256File(vkeyFile) !== bundle.meta?.vkey_sha256)
    return fail("VK_MISMATCH", "verification key differs from the one used at proof generation");

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "zkkyc-vfy-"));
  const pf = path.join(tmp, "proof.json"), uf = path.join(tmp, "public.json");
  fs.writeFileSync(pf, JSON.stringify(bundle.proof));
  fs.writeFileSync(uf, JSON.stringify(bundle.publicSignals));
  const r = await require("./util").trySnark(["plonk", "verify", vkeyFile, uf, pf]);
  fs.rmSync(tmp, { recursive: true, force: true });
  if (!r.ok) return fail("SNARK_VERIFY_FAILED", r.stderr?.slice(0, 400));
  return { ok: true };
}

module.exports = { generateProofBundle, verifyBundle, checkProverArtifacts };
