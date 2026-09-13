#!/usr/bin/env node
// usage: node scripts/generate-proof.js <credential.json> [-o out.proof.json]
"use strict";
const fs = require("fs");
const path = require("path");
const { ROOT } = require("./lib/util");
const { generateProofBundle } = require("./lib/proof");

(async () => {
  const args = process.argv.slice(2);
  const credIdx = args.findIndex(a => !a.startsWith("-"));
  if (credIdx === -1) { console.error("usage: generate-proof.js <credential.json> [-o out.proof.json]"); process.exit(2); }
  const credFile = path.resolve(args[credIdx]);
  const oIdx = args.indexOf("-o");
  const outFile = oIdx !== -1 ? path.resolve(args[oIdx + 1])
                              : path.join(ROOT, "proofs", path.basename(credFile, ".json") + ".proof.json");

  try {
    const bundle = await generateProofBundle(credFile);
    fs.mkdirSync(path.dirname(outFile), { recursive: true });
    fs.writeFileSync(outFile, JSON.stringify(bundle, null, 2));
    console.log(`PROOF WRITTEN: ${outFile}`);
    console.log(`public signals (ax, ay, refPacked): ${bundle.publicSignals.join(", ")}`);
    process.exit(0);
  } catch (e) {
    console.error(`PROOF GENERATION FAILED: ${e.message}`);
    process.exit(1);
  }
})();
