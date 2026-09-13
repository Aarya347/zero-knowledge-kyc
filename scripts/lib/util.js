"use strict";
const { execFile } = require("child_process");
const { promisify } = require("util");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ROOT = path.resolve(__dirname, "..", "..");
const SNARK_CLI = path.join(ROOT, "node_modules", "snarkjs", "cli.js");

const PATHS = {
  root: ROOT,
  wasm: path.join(ROOT, "build/main/age_credential_js/age_credential.wasm"),
  variantWasm: path.join(ROOT, "build/variant/age_credential_variant_js/age_credential_variant.wasm"),
  zkey: path.join(ROOT, "build/main/age_credential.zkey"),
  variantZkey: path.join(ROOT, "build/variant/age_credential_variant.zkey"),
  vkey: path.join(ROOT, "build/main/vkey.json"),
  variantVkey: path.join(ROOT, "build/variant/vkey.json"),
  issuerPrivate: path.join(ROOT, "keys/issuer.private.json"),
  issuerPublic: path.join(ROOT, "keys/issuer.public.json"),
};

async function snark(args, opts = {}) {
  return promisify(execFile)(process.execPath, [SNARK_CLI, ...args],
    { cwd: ROOT, maxBuffer: 1 << 26, ...opts });
}

async function trySnark(args) {
  try { await snark(args); return { ok: true }; }
  catch (e) { return { ok: false, stderr: String(e.stderr || e.message) }; }
}

function assertExists(p, what) {
  if (!fs.existsSync(p)) {
    throw new Error(`${what} not found at ${p}. Run: bash setup.sh`);
  }
}

function sha256File(p) {
  return crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
}

// Flatten nested proof JSON into an ordered uint[24] for the Solidity verifier.
function deepFlatten(proof) {
  const g1Keys = ["A", "B", "C", "Z", "T1", "T2", "T3", "Wxi", "Wxiw"];
  const scalarKeys = ["eval_a", "eval_b", "eval_c", "eval_s1", "eval_s2", "eval_zw"];
  const out = [];
  for (const k of g1Keys) {
    if (Array.isArray(proof[k])) {
      out.push(BigInt(proof[k][0]));
      out.push(BigInt(proof[k][1]));
    }
  }
  for (const k of scalarKeys) {
    if (proof[k] !== undefined) {
      out.push(BigInt(proof[k]));
    }
  }
  return out;
}

function packedDate(y, m, d) { return y * 10000 + m * 100 + d; }
function unpackDate(p) { return { y: Math.floor(p / 10000), m: Math.floor((p % 10000) / 100), d: p % 100 }; }

// Reference date = today in UTC, packed as YYYYMMDD.
// The circuit itself evaluates (birthYear + 18, birthMonth, birthDay) <= refPacked.
function cutoffPacked(nowMs = Date.now()) {
  const n = new Date(nowMs);
  return packedDate(n.getUTCFullYear(), n.getUTCMonth() + 1, n.getUTCDate());
}

function daysBetweenPacked(a, b) {
  const ua = unpackDate(a), ub = unpackDate(b);
  const ta = Date.UTC(ua.y, ua.m - 1, ua.d), tb = Date.UTC(ub.y, ub.m - 1, ub.d);
  return Math.round(Math.abs(tb - ta) / 86400000);
}

module.exports = { ROOT, PATHS, snark, trySnark, assertExists, sha256File,
  deepFlatten, packedDate, unpackDate, cutoffPacked, daysBetweenPacked };
