"use strict";
const test = require("node:test");
const assert = require("node:assert");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const { PATHS, deepFlatten } = require("../scripts/lib/util");
const { makeIssuer, issueCredential } = require("../scripts/lib/crypto");
const { generateProofBundle } = require("../scripts/lib/proof");
const { deployBoth } = require("../scripts/lib/chain");
const { ethers } = require("ethers");

const ANVIL_PK = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"; // well-known anvil dev key
const USE_SEPOLIA = !!process.env.SEPOLIA_FUNDED_PRIVATE_KEY;

async function waitAnvil(url, ms = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "eth_blockNumber", params: [], id: 1 }),
      });
      if (res.ok) return;
    } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error("anvil did not start (installed? https://getfoundry.sh)");
}

test("on-chain verifier accepts valid proof, rejects tampered proof", { skip: USE_SEPOLIA ? false : undefined, timeout: 600000 }, async () => {
  // ---- build a REAL proof from a REAL credential ----
  const issuer = await makeIssuer();
  const cred = await issueCredential(issuer, { year: 1990, month: 5, day: 14 });
  const credFile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "oc-")), "cred.json");
  fs.writeFileSync(credFile, JSON.stringify(cred));
  const origPub = PATHS.issuerPublic;
  const tmpKeys = path.dirname(credFile);
  fs.writeFileSync(path.join(tmpKeys, "issuer.public.json"), JSON.stringify({ ax: issuer.ax, ay: issuer.ay }));
  PATHS.issuerPublic = path.join(tmpKeys, "issuer.public.json");
  let bundle;
  try { bundle = await generateProofBundle(credFile); }
  finally { PATHS.issuerPublic = origPub; }

  const tampered = JSON.parse(JSON.stringify(bundle));
  const k = Object.keys(tampered.proof)[0];
  const flip = (o) => { for (const kk of Object.keys(o)) {
    if (typeof o[kk] === "string" && o[kk].length > 10) { o[kk] = (BigInt(o[kk]) + 1n).toString(); return true; }
    if (o[kk] && typeof o[kk] === "object" && flip(o[kk])) return true; } return false; };
  flip(tampered.proof);

  // ---- chain setup: Sepolia (funded key) or local anvil (auto-spawned) ----
  let anvilProc = null, rpcUrl, wallet;
  if (USE_SEPOLIA) {
    rpcUrl = process.env.SEPOLIA_RPC_URL || "https://rpc.sepolia.org";
    wallet = new ethers.Wallet(process.env.SEPOLIA_FUNDED_PRIVATE_KEY, new ethers.JsonRpcProvider(rpcUrl));
  } else {
    rpcUrl = "http://127.0.0.1:8545";
    let anvilCmd = "anvil";
    const userBinAnvil = path.join(process.env.USERPROFILE || "", "bin", "anvil.exe");
    if (fs.existsSync(userBinAnvil)) anvilCmd = userBinAnvil;
    anvilProc = spawn(anvilCmd, ["--port", "8545", "--silent"], { stdio: "ignore" });
    try { await waitAnvil(rpcUrl); } catch (e) { anvilProc.kill(); throw e; }
    const provider = new ethers.JsonRpcProvider(rpcUrl, undefined, { staticNetwork: true });
    const rich = new ethers.Wallet(ANVIL_PK, provider);
    wallet = ethers.Wallet.createRandom(provider);
    await (await rich.sendTransaction({ to: wallet.address, value: ethers.parseEther("10") })).wait();
  }

  try {
    const { record } = await deployBoth(wallet);

    const verifier = new ethers.Contract(record.verifier_address, [
      "function verifyProof(uint256[24],uint256[3]) view returns (bool)",
    ], wallet);
    const registry = new ethers.Contract(record.registry_address, [
      "function submit(uint256[24],uint256[3])",
      "event ProofSubmitted(address indexed submitter, bool valid, uint256 timestamp)",
    ], wallet);

    const okArgs = deepFlatten(bundle.proof).map(x => "0x" + x.toString(16));
    const pubs = bundle.publicSignals.map(x => "0x" + BigInt(x).toString(16));
    const badArgs = deepFlatten(tampered.proof).map(x => "0x" + x.toString(16));

    // SECURITY PROPERTY 1: valid proof verifies ON-CHAIN.
    assert.equal(await verifier.verifyProof.staticCall(okArgs, pubs), true);

    // SECURITY PROPERTY 2: tampered proof fails on-chain.
    assert.equal(await verifier.verifyProof.staticCall(badArgs, pubs), false);

    // SECURITY PROPERTY 3: public, event-logged result.
    const rc = await (await registry.submit(okArgs, pubs, { gasLimit: 1000000 })).wait();
    const ev = rc.logs.map(l => { try { return registry.interface.parseLog(l); } catch { return null; } }).find(Boolean);
    assert.equal(ev.args.valid, true);
    console.log(`on-chain verify OK - verifier=${record.verifier_address} registry=${record.registry_address} chain=${record.network_chain_id}`);
  } finally {
    if (anvilProc) anvilProc.kill();
  }
});
