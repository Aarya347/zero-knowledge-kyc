#!/usr/bin/env node
// usage: node scripts/verify-proof.js <proof.json> [--issuer-pub keys/issuer.public.json] [--max-skew-days 2]
"use strict";
const fs = require("fs");
const path = require("path");
const { PATHS } = require("./lib/util");
const { verifyBundle } = require("./lib/proof");

(async () => {
  const args = process.argv.slice(2);
  let proofFile = null, pubFile = PATHS.issuerPublic, skew = 2;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--issuer-pub") pubFile = path.resolve(args[++i]);
    else if (args[i] === "--max-skew-days") skew = Number(args[++i]);
    else if (!args[i].startsWith("-")) proofFile = path.resolve(args[i]);
  }
  if (!proofFile) { console.error("usage: verify-proof.js <proof.json> [--issuer-pub f] [--max-skew-days n]"); process.exit(2); }

  let bundle;
  try { bundle = JSON.parse(fs.readFileSync(proofFile, "utf8")); }
  catch { console.error("cannot parse proof file"); process.exit(2); }

  const r = await verifyBundle(bundle, { issuerPubFile: pubFile, maxSkewDays: skew });
  if (r.ok) {
    console.log("VERIFIED - valid PLONK proof; adult (18+) relative to pinned cutoff; issuer key matches trust anchor.");
    console.log(JSON.stringify({ ok: true, refPacked: bundle.publicSignals[2] }));
    process.exit(0);
  } else {
    console.error(`REJECTED reason=${r.reason}${r.details ? " detail=" + JSON.stringify(r.details) : ""}`);
    process.exit(1);
  }
})();
