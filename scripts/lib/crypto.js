"use strict";
const fs = require("fs");
const crypto = require("crypto");
const circomlibjs = require("circomlibjs");
const { PATHS } = require("./util");

let eddsaCache = null, poseidonCache = null;

async function getEddsa() {
  if (!eddsaCache) eddsaCache = await circomlibjs.buildEddsa();
  return eddsaCache;
}
async function getPoseidon() {
  if (!poseidonCache) poseidonCache = await circomlibjs.buildPoseidon();
  return poseidonCache;
}

// Returns the BabyJubJub-field Poseidon hash as a plain BigInt.
async function poseidonHash(fields) {
  const P = await getPoseidon();
  const out = P(fields.map(BigInt));
  return P.F.toObject(Array.isArray(out) ? out[0] : out);
}

async function makeIssuer() {
  const E = await getEddsa();
  const prv = crypto.randomBytes(32);
  const pub = E.prv2pub(prv);                       // [field, field]
  return {
    prv,
    ax: E.F.toObject(pub[0]).toString(),
    ay: E.F.toObject(pub[1]).toString(),
  };
}

async function issuerFromFiles(privFile = PATHS.issuerPrivate, pubFile = PATHS.issuerPublic) {
  const prvHex = JSON.parse(fs.readFileSync(privFile, "utf8")).private_key_hex;
  const pub = JSON.parse(fs.readFileSync(pubFile, "utf8"));
  return { prv: Buffer.from(prvHex, "hex"), ax: pub.ax, ay: pub.ay };
}

// Credential message: Poseidon(year, month, day, holderSecret)
async function credentialMessage(dob, secretDec) {
  return poseidonHash([dob.year, dob.month, dob.day, secretDec]);
}

async function signMessage(issuer, msgBig) {
  const E = await getEddsa();
  const F = E.F;
  const sig = E.signPoseidon(issuer.prv, F.e(msgBig));
  return {
    R8x: F.toObject(sig.R8[0]).toString(),
    R8y: F.toObject(sig.R8[1]).toString(),
    S: sig.S.toString(),
  };
}

async function verifySignature(msgBig, sig, ax, ay) {
  const E = await getEddsa();
  const F = E.F;
  return E.verifyPoseidon(
    F.e(msgBig),
    { R8: [F.e(BigInt(sig.R8x)), F.e(BigInt(sig.R8y))], S: BigInt(sig.S) },
    [F.e(BigInt(ax)), F.e(BigInt(ay))]
  );
}

async function issueCredential(issuer, dob, { issuerId = "did:zkkyc:local", issuedAt } = {}) {
  const secret = BigInt("0x" + crypto.randomBytes(31).toString("hex")); // 248-bit holder secret
  const msg = await credentialMessage(dob, secret);
  const signature = await signMessage(issuer, msg);
  return {
    schema: "zkkyc-credential-v1",
    issuer_id: issuerId,
    issued_at: issuedAt || new Date().toISOString(),
    issuer_pub: { ax: issuer.ax, ay: issuer.ay },
    subject: { dob: { year: dob.year, month: dob.month, day: dob.day } },
    holder_secret: secret.toString(),
    signature,
  };
}

module.exports = { getEddsa, getPoseidon, poseidonHash, makeIssuer, issuerFromFiles,
  credentialMessage, signMessage, verifySignature, issueCredential };
