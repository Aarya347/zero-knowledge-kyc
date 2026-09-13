#!/usr/bin/env node
// Anyone can submit anyone's proof. Usage:
//   node scripts/submit-proof.js <proof.json> \
//        [--deployment deployments/chain-11155111.json] [--rpc URL] [--pk KEY]
// Performs: free local static-call check -> on-chain tx -> prints Etherscan link.
"use strict";
const fs = require("fs");
const path = require("path");
const { ethers } = require("ethers");
const { deepFlatten, ROOT } = require("./lib/util");

(async () => {
  const args = process.argv.slice(2);
  let proofFile = null, depFile = path.join(ROOT, "deployments", "chain-11155111.json");
  let rpc = process.env.SEPOLIA_RPC_URL || "https://rpc.sepolia.org";
  let pk = process.env.PRIVATE_KEY;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--deployment") depFile = path.resolve(args[++i]);
    else if (args[i] === "--rpc") rpc = args[++i];
    else if (args[i] === "--pk") pk = args[++i];
    else if (!args[i].startsWith("-")) proofFile = path.resolve(args[i]);
  }
  if (!proofFile || !fs.existsSync(depFile)) {
    console.error("usage: submit-proof.js <proof.json> [--deployment deployments/chain-CHAINID.json] [--rpc u] [--pk k]");
    process.exit(2);
  }
  const bundle = JSON.parse(fs.readFileSync(proofFile, "utf8"));
  const dep = JSON.parse(fs.readFileSync(depFile, "utf8"));

  const proofArgs = deepFlatten(bundle.proof).map(x => "0x" + x.toString(16));
  const pubArgs = bundle.publicSignals.map(x => "0x" + BigInt(x).toString(16));

  const provider = new ethers.JsonRpcProvider(rpc);
  const verifier = new ethers.Contract(dep.verifier_address, [
    "function verifyProof(uint256[24],uint256[3]) view returns (bool)",
  ], provider);

  let localOk;
  try { localOk = await verifier.verifyProof.staticCall(proofArgs, pubArgs); }
  catch (e) { localOk = false; }
  console.log(`LOCAL STATIC-CALL CHECK: ${localOk ? "VALID" : "INVALID (will revert on-chain)"}`);
  if (!localOk) process.exit(1);

  if (!pk) { console.error("Set PRIVATE_KEY (submitter) to send the recording transaction."); process.exit(2); }
  const registry = new ethers.Contract(dep.registry_address, [
    "function submit(uint256[24],uint256[3])",
    "event ProofSubmitted(address indexed submitter, bool valid, uint256 timestamp)",
  ], new ethers.Wallet(pk, provider));

  const tx = await registry.submit(proofArgs, pubArgs);
  console.log("tx:", tx.hash);
  const rc = await tx.wait();
  const ev = rc.logs.map(l => { try { return registry.interface.parseLog(l); } catch { return null; } })
                     .find(Boolean);
  console.log(`ON-CHAIN RESULT: ${ev && ev.args.valid ? "VALID" : "INVALID"}`);
  console.log(`Etherscan tx: https://sepolia.etherscan.io/tx/${tx.hash}`);
  console.log(`Etherscan contract: https://sepolia.etherscan.io/address/${dep.registry_address}#events`);
  process.exit(ev && ev.args.valid ? 0 : 1);
})();
