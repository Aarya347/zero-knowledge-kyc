#!/usr/bin/env node
"use strict";
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const { getEddsa, getPoseidon } = require("../../scripts/lib/crypto");

const PORT = Number(process.env.SIGNER_PORT || 7391);
const TOKEN = process.env.SIGNER_TOKEN;
const PRIV_FILE = process.env.SIGNER_PRIVKEY || "keys/issuer.private.json";
if (!TOKEN || TOKEN.length < 16) { console.error("SIGNER_TOKEN env required (>=16 chars)"); process.exit(1); }

let EDDSA, POSEIDON, PRV, PUB;

function safeEqual(a, b) {
  const ha = crypto.createHash("sha256").update(a).digest();
  const hb = crypto.createHash("sha256").update(b).digest();
  return crypto.timingSafeEqual(ha, hb);
}

(async () => {
  EDDSA = await getEddsa();
  POSEIDON = await getPoseidon();
  PRV = Buffer.from(JSON.parse(fs.readFileSync(PRIV_FILE, "utf8")).private_key_hex, "hex");
  PUB = EDDSA.prv2pub(PRV).map(x => EDDSA.F.toObject(x).toString());
  console.log(`signer ready on 127.0.0.1:${PORT}; issuer ax=${PUB[0].slice(0, 12)}...`);

  const server = http.createServer(async (req, res) => {
    res.setHeader("content-type", "application/json");
    if (!safeEqual(req.headers["x-signer-token"] || "", TOKEN)) {
      res.writeHead(401); return res.end(JSON.stringify({ error: "unauthorized" }));
    }
    if (req.method === "GET" && req.url === "/pubkey") {
      res.writeHead(200); return res.end(JSON.stringify({ ax: PUB[0], ay: PUB[1] }));
    }
    if (req.method === "POST" && req.url === "/issue") {
      let body = "";
      req.on("data", c => { body += c; if (body.length > 4096) req.destroy(); });
      req.on("end", async () => {
        let j; try { j = JSON.parse(body); } catch { res.writeHead(400); return res.end(JSON.stringify({ error: "bad json" })); }
        const { year, month, day } = j;
        const okShape = [year, month, day].every(v => Number.isInteger(v));
        const okRange = okShape && year >= 1900 && year <= 2100 && month >= 1 && month <= 12 && day >= 1 && day <= 31;
        if (!okRange) { res.writeHead(422); return res.end(JSON.stringify({ error: "invalid dob" })); }
        try {
          const secret = BigInt("0x" + crypto.randomBytes(31).toString("hex"));
          const msgFe = POSEIDON([BigInt(year), BigInt(month), BigInt(day), secret]);
          const msg = POSEIDON.F.toObject(Array.isArray(msgFe) ? msgFe[0] : msgFe);
          const sig = EDDSA.signPoseidon(PRV, EDDSA.F.e(msg));
          res.writeHead(200);
          res.end(JSON.stringify({
            ax: PUB[0], ay: PUB[1],
            R8x: EDDSA.F.toObject(sig.R8[0]).toString(),
            R8y: EDDSA.F.toObject(sig.R8[1]).toString(),
            S: sig.S.toString(),
            secret: secret.toString(),
            issued_at: new Date().toISOString(),
          }));
        } catch (e) { res.writeHead(500); res.end(JSON.stringify({ error: String(e.message || e) })); }
      });
      return;
    }
    res.writeHead(404); res.end(JSON.stringify({ error: "not found" }));
  });
  server.listen(PORT, "127.0.0.1");
})();
