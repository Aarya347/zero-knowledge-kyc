#!/usr/bin/env node
// Independent third-party check that a credential is signed by the issuer.
// Also enforces the credential privacy schema: no biometric fields may exist.
"use strict";
const fs = require("fs");
const { credentialMessage, verifySignature } = require("./lib/crypto");
const { PATHS } = require("./lib/util");

const ALLOWED_TOP = new Set(["schema", "issuer_id", "issued_at", "issuer_pub", "subject", "holder_secret", "signature"]);
const FORBIDDEN_HINTS = /(photo|image|video|embed|face|frame|selfie|biomet|iris|voice)/i;

(async () => {
  const file = process.argv[2];
  const pubFile = process.argv.includes("--issuer-pub")
    ? process.argv[process.argv.indexOf("--issuer-pub") + 1] : PATHS.issuerPublic;
  if (!file) { console.error("usage: verify-issuer-signature.js <credential.json> [--issuer-pub f]"); process.exit(2); }

  const cred = JSON.parse(fs.readFileSync(file, "utf8"));
  if (cred.schema !== "zkkyc-credential-v1") { console.error("FAIL: unknown schema"); process.exit(1); }

  for (const k of Object.keys(cred)) if (!ALLOWED_TOP.has(k)) { console.error(`FAIL: unexpected field '${k}'`); process.exit(1); }
  if (FORBIDDEN_HINTS.test(JSON.stringify(Object.keys(cred)))) { console.error("FAIL: forbidden biometric-related field present"); process.exit(1); }

  const pub = JSON.parse(fs.readFileSync(pubFile, "utf8"));
  if (BigInt(cred.issuer_pub.ax) !== BigInt(pub.ax) || BigInt(cred.issuer_pub.ay) !== BigInt(pub.ay)) {
    console.error("FAIL: issuer_pub in credential does not match pinned issuer key"); process.exit(1);
  }
  const { year, month, day } = cred.subject.dob;
  if (!(Number.isInteger(year) && Number.isInteger(month) && Number.isInteger(day))) {
    console.error("FAIL: malformed dob"); process.exit(1);
  }
  const msg = await credentialMessage({ year, month, day }, cred.holder_secret);
  const ok = await verifySignature(msg, cred.signature, cred.issuer_pub.ax, cred.issuer_pub.ay);
  console.log(ok ? "CREDENTIAL SIGNATURE VALID" : "CREDENTIAL SIGNATURE INVALID");
  process.exit(ok ? 0 : 1);
})();
