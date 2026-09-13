#!/usr/bin/env node
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { ROOT } = require("./lib/util");
const { makeIssuer } = require("./lib/crypto");

(async () => {
  const force = process.argv.includes("--force");
  const dir = path.join(ROOT, "keys");
  fs.mkdirSync(dir, { recursive: true });
  for (const f of ["issuer.private.json", "issuer.public.json"]) {
    if (fs.existsSync(path.join(dir, f)) && !force) {
      console.error(`refusing to overwrite keys/${f} (use --force)`); process.exit(1);
    }
  }
  const { prv, ax, ay } = await makeIssuer();
  fs.writeFileSync(path.join(dir, "issuer.private.json"),
    JSON.stringify({ private_key_hex: prv.toString("hex") }, null, 2), { mode: 0o600 });
  fs.writeFileSync(path.join(dir, "issuer.public.json"),
    JSON.stringify({ ax, ay }, null, 2));
  const fp = crypto.createHash("sha256").update(`${ax},${ay}`).digest("hex").slice(0, 32);
  console.log(`issuer keypair written to keys/. Public key fingerprint: sha256:${fp}`);
})();
