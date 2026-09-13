"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");

const { PATHS, trySnark, assertExists, sha256File, cutoffPacked } = require("../scripts/lib/util");
const { makeIssuer, issueCredential } = require("../scripts/lib/crypto");
const { generateProofBundle, verifyBundle } = require("../scripts/lib/proof");

let HAVE_ARTIFACTS = true;
try {
  assertExists(PATHS.wasm, "wasm"); assertExists(PATHS.zkey, "zkey"); assertExists(PATHS.vkey, "vkey");
  assertExists(PATHS.variantZkey, "variant zkey"); assertExists(PATHS.variantVkey, "variant vkey");
} catch (e) { HAVE_ARTIFACTS = false; }

function tmpJson(obj) {
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "zkct-")), "f.json");
  fs.writeFileSync(f, JSON.stringify(obj));
  return f;
}

test("artifacts built (run bash setup.sh)", { skip: HAVE_ARTIFACTS ? false : "run bash setup.sh first" }, () => {});

test("valid adult credential: prove + verify succeeds", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const cred = await issueCredential(issuer, { year: 1990, month: 5, day: 14 });
  const bundle = await generateProofBundle(tmpJson(cred), {});
  const r = await verifyBundle(bundle, { issuerPubFile: tmpJson({ ax: issuer.ax, ay: issuer.ay }) });
  assert.equal(r.ok, true, JSON.stringify(r));
});

test("regression test: valid 20-year-old adult (DOB 2006-07-07, 18-35 age bracket) prove + verify succeeds", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const cred = await issueCredential(issuer, { year: 2006, month: 7, day: 7 });
  const bundle = await generateProofBundle(tmpJson(cred), {});
  const r = await verifyBundle(bundle, { issuerPubFile: tmpJson({ ax: issuer.ax, ay: issuer.ay }) });
  assert.equal(r.ok, true, JSON.stringify(r));
});

test("underage credential (age 17): witness generation must FAIL (circuit constraint)", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const now = new Date();
  const cred = await issueCredential(issuer, { year: now.getUTCFullYear() - 17, month: now.getUTCMonth() + 1, day: now.getUTCDate() }); // 17 years old
  await assert.rejects(() => generateProofBundle(tmpJson(cred)),
    (e) => /constraint|unsatisfi|Error in template|Assert Failed/i.test(String(e.stderr || e.message)));
});

test("underage credential: witness generation must FAIL (circuit constraint)", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const cred = await issueCredential(issuer, { year: 2012, month: 1, day: 1 }); // validly signed but underage
  await assert.rejects(() => generateProofBundle(tmpJson(cred)),
    (e) => /constraint|unsatisfi|Error in template|Assert Failed/i.test(String(e.stderr || e.message)));
});

test("tampered proof bytes: verification must FAIL", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const cred = await issueCredential(issuer, { year: 1990, month: 5, day: 14 });
  const bundle = await generateProofBundle(tmpJson(cred));
  // Flip one character inside a long numeric field of the proof.
  outer: for (const k of Object.keys(bundle.proof)) {
    const v = bundle.proof[k];
    const walk = (o) => {
      for (const kk of Object.keys(o)) {
        if (typeof o[kk] === "string" && o[kk].length > 10) {
          o[kk] = o[kk][0] === "1" ? "2" + o[kk].slice(1) : "1" + o[kk].slice(1);
          return true;
        }
        if (typeof o[kk] === "object" && o[kk] !== null && walk(o[kk])) return true;
      }
      return false;
    };
    if (typeof v === "object" && v !== null && walk(v)) break outer;
    if (typeof v === "string" && v.length > 10) {
      bundle.proof[k] = v[0] === "1" ? "2" + v.slice(1) : "1" + v.slice(1);
      break outer;
    }
  }
  const r = await verifyBundle(bundle, { issuerPubFile: tmpJson({ ax: issuer.ax, ay: issuer.ay }) });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "SNARK_VERIFY_FAILED");
});

test("proof against WRONG verification key must FAIL", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const cred = await issueCredential(issuer, { year: 1990, month: 5, day: 14 });
  const bundle = await generateProofBundle(tmpJson(cred));
  const r = await verifyBundle(bundle, {
    issuerPubFile: tmpJson({ ax: issuer.ax, ay: issuer.ay }),
    vkeyFile: PATHS.variantVkey,                 // different R1CS => different VK
  });
  assert.equal(r.ok, false);
  assert.match(r.reason, /VK_MISMATCH|SNARK_VERIFY_FAILED/);
  // And at the raw snark layer too (policy checks bypassed):
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "vkraw-"));
  fs.writeFileSync(path.join(tmp, "p.json"), JSON.stringify(bundle.proof));
  fs.writeFileSync(path.join(tmp, "u.json"), JSON.stringify(bundle.publicSignals));
  const raw = await trySnark(["plonk", "verify", PATHS.variantVkey,
    path.join(tmp, "u.json"), path.join(tmp, "p.json")]);
  assert.equal(raw.ok, false);
});

test("forged / self-signed credential: mathematically valid proof, REJECTED by trust anchor", { skip: !HAVE_ARTIFACTS }, async () => {
  const attacker = await makeIssuer();                       // attacker's OWN key
  const cred = await issueCredential(attacker, { year: 1990, month: 5, day: 14 });
  const bundle = await generateProofBundle(tmpJson(cred));   // proving works (signature IS valid for attacker key)
  // Raw SNARK layer: passes. This is EXPECTED - cryptography cannot know who is trustworthy;
  // the trust anchor is the pinned issuer key:
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "forge-"));
  fs.writeFileSync(path.join(tmp, "p.json"), JSON.stringify(bundle.proof));
  fs.writeFileSync(path.join(tmp, "u.json"), JSON.stringify(bundle.publicSignals));
  const raw = await trySnark(["plonk", "verify", PATHS.vkey, path.join(tmp, "u.json"), path.join(tmp, "p.json")]);
  assert.equal(raw.ok, true, "sanity: forged-issuer proof is SNARK-valid (trust is external)");
  // Policy layer (what every verifier must run): rejected:
  const honestIssuer = await makeIssuer();
  const r = await verifyBundle(bundle, { issuerPubFile: tmpJson({ ax: honestIssuer.ax, ay: honestIssuer.ay }) });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "ISSUER_KEY_MISMATCH");
});

test("signature over a DIFFERENT message than claimed inputs: witness must FAIL", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const { poseidonHash, signMessage } = require("../scripts/lib/crypto");
  const otherMsg = await poseidonHash([1990, 5, 14, 42]);    // signed message...
  const sig = await signMessage(issuer, otherMsg);
  const cred = {                                             // ...but different claimed secret
    schema: "zkkyc-credential-v1", issuer_id: "x", issued_at: new Date().toISOString(),
    issuer_pub: { ax: issuer.ax, ay: issuer.ay },
    subject: { dob: { year: 1990, month: 5, day: 14 } },
    holder_secret: "43",
    signature: sig,
  };
  await assert.rejects(() => generateProofBundle(tmpJson(cred)),
    (e) => /constraint|unsatisfi|Mx|BAD_CREDENTIAL_SIGNATURE|Error in template|Assert Failed/i.test(String(e.stderr || e.message)));
});

test("tampered public inputs (refPacked): raw verification must FAIL", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const cred = await issueCredential(issuer, { year: 1990, month: 5, day: 14 });
  const bundle = await generateProofBundle(tmpJson(cred));
  bundle.publicSignals[2] = String(Number(bundle.publicSignals[2]) + 1);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "pub-"));
  fs.writeFileSync(path.join(tmp, "p.json"), JSON.stringify(bundle.proof));
  fs.writeFileSync(path.join(tmp, "u.json"), JSON.stringify(bundle.publicSignals));
  const raw = await trySnark(["plonk", "verify", PATHS.vkey, path.join(tmp, "u.json"), path.join(tmp, "p.json")]);
  assert.equal(raw.ok, false);
});

test("stale cutoff date rejected by freshness policy (±2 days)", { skip: !HAVE_ARTIFACTS }, async () => {
  const issuer = await makeIssuer();
  const cred = await issueCredential(issuer, { year: 1990, month: 5, day: 14 });
  const bundle = await generateProofBundle(tmpJson(cred));
  const future = Date.now() + 40 * 86400000;                  // verifier clock 40 days later
  const r = await verifyBundle(bundle, {
    issuerPubFile: tmpJson({ ax: issuer.ax, ay: issuer.ay }), nowMs: future,
  });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "REF_DATE_STALE");
});
