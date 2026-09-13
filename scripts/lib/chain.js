"use strict";
const fs = require("fs");
const path = require("path");
const solc = require("solc");
const { ROOT } = require("./util");

const CONTRACTS = path.join(ROOT, "contracts");
const DEPLOYMENTS = path.join(ROOT, "deployments");

function compileContract(fileName, contractName) {
  const sources = {};
  for (const f of fs.readdirSync(CONTRACTS)) {
    if (f.endsWith(".sol")) {
      sources[f] = { content: fs.readFileSync(path.join(CONTRACTS, f), "utf8") };
    }
  }
  const input = {
    language: "Solidity",
    sources,
    settings: {
      optimizer: { enabled: true, runs: 200 },
      outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } },
    },
  };
  function findImports(importPath) {
    const p = path.resolve(CONTRACTS, importPath);
    if (fs.existsSync(p)) return { contents: fs.readFileSync(p, "utf8") };
    return { error: "File not found: " + importPath };
  }
  const out = JSON.parse(solc.compile(JSON.stringify(input), { import: findImports }));
  if (out.errors?.some(e => e.severity === "error")) {
    throw new Error("solc errors:\n" + out.errors.filter(e => e.severity === "error").map(e => e.formattedMessage).join("\n"));
  }
  const c = out.contracts[fileName][contractName];
  return { abi: c.abi, bytecode: "0x" + c.evm.bytecode.object };
}

async function deployBoth(wallet) {
  const { ethers } = require("ethers");
  const signer = (wallet instanceof ethers.NonceManager) ? wallet : new ethers.NonceManager(wallet);
  const verifier = compileContract("PlonkVerifier.sol", "PlonkVerifier");
  const registry = compileContract("ProofRegistry.sol", "ProofRegistry");
  const vf = new ethers.ContractFactory(verifier.abi, verifier.bytecode, signer);
  const v = await vf.deploy();
  await v.waitForDeployment();

  const rf = new ethers.ContractFactory(registry.abi, registry.bytecode, signer);
  const r = await rf.deploy(await v.getAddress());
  await r.waitForDeployment();

  const record = {
    network_chain_id: Number((await wallet.provider.getNetwork()).chainId),
    verifier_address: await v.getAddress(),
    registry_address: await r.getAddress(),
    deployer: wallet.address,
    deployed_at: new Date().toISOString(),
  };
  fs.mkdirSync(DEPLOYMENTS, { recursive: true });
  const file = path.join(DEPLOYMENTS, `chain-${record.network_chain_id}.json`);
  fs.writeFileSync(file, JSON.stringify(record, null, 2));
  return { record, file, verifierAbi: verifier.abi, registryAbi: registry.abi };
}

module.exports = { compileContract, deployBoth, DEPLOYMENTS };
