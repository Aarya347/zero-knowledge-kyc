// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./PlonkVerifier.sol";

/// Emits a permanent public record of every proof submission.
/// The actual verification is performed exclusively by the snarkjs-generated
/// PlonkVerifier - this contract adds no cryptographic logic of its own.
contract ProofRegistry {
    PlonkVerifier public immutable verifier;

    event ProofSubmitted(address indexed submitter, bool valid, uint256 timestamp);

    constructor(address verifierAddress) {
        require(verifierAddress != address(0), "zero verifier");
        verifier = PlonkVerifier(verifierAddress);
    }

    function submit(uint256[24] calldata proof, uint256[3] calldata pubSignals) external {
        bool ok = verifier.verifyProof(proof, pubSignals);
        emit ProofSubmitted(msg.sender, ok, block.timestamp);
    }
}
