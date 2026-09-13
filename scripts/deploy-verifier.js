#!/usr/bin/env node
// Generates a FRESH wallet, prints its address (+ mnemonic - TESTNET ONLY),
// waits for you to fund it from a Sepolia faucet, then deploys the
// snarkjs-generated verifier plus the event registry.
//
// Env:
//   SEPOLIA_RPC_URL   (default: https://rpc.sepolia.org)
//   DEPLOYER_PRIVATE_KEY  (optional: reuse an existing funded key)
"use strict";
const { ethers } = require("ethers");
const { deployBoth } = require("./lib/chain");

const RPC = process.env.SEPOLIA_RPC_URL || "https://rpc.sepolia.org";
const FAUCETS = [
  "https://cloud.google.com/application/web3/faucet/ethereum/sepolia",
  "https://sepolia-faucet.pk910.de/",
  "https://www.alchemy.com/faucets/ethereum-sepolia",
];

(async () => {
  const wallet = process.env.DEPLOYER_PRIVATE_KEY
    ? new ethers.Wallet(process.env.DEPLOYER_PRIVATE_KEY, new ethers.JsonRpcProvider(RPC))
    : new ethers.Wallet.createRandom(new ethers.JsonRpcProvider(RPC));

  console.log("==========================================================");
  console.log("NETWORK      :", RPC, "(chainId pending...)");
  console.log("DEPLOYER ADDR:", wallet.address);
  if (!process.env.DEPLOYER_PRIVATE_KEY && wallet.mnemonic) {
    console.log("MNEMONIC     :", wallet.mnemonic.phrase);
    console.log("!! TESTNET-ONLY WALLET. NEVER reuse for mainnet funds. !!");
  }
  console.log("Fund this address with free Sepolia ETH from any faucet:");
  for (const f of FAUCETS) console.log("  -", f);
  console.log("Waiting for balance >= 0.02 ETH (Ctrl-C to abort)...");
  console.log("==========================================================");

  const need = ethers.parseEther("0.02");
  let shown = 0n;
  for (;;) {
    shown = await wallet.provider.getBalance(wallet.address);
    if (shown >= need) break;
    process.stdout.write(`\rbalance: ${ethers.formatEther(shown)} ETH   `);
    await new Promise(r => setTimeout(r, 15000));
  }
  console.log(`\nfunded with ${ethers.formatEther(shown)} ETH - deploying...`);

  const { record, file } = await deployBoth(wallet);
  console.log("DEPLOYED.");
  console.log(JSON.stringify(record, null, 2));
  console.log("saved to", file);
  console.log(`Etherscan: https://sepolia.etherscan.io/address/${record.registry_address}`);
})().catch(e => { console.error("DEPLOY FAILED:", e.message); process.exit(1); });
