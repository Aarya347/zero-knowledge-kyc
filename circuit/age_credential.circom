pragma circom 2.0.0;

include "../node_modules/circomlib/circuits/comparators.circom";
include "../node_modules/circomlib/circuits/bitify.circom";
include "../node_modules/circomlib/circuits/poseidon.circom";
include "../node_modules/circomlib/circuits/eddsaposeidon.circom";

// Proves TWO facts about private data:
//  1. The holder's (private) birthdate is at least 18 years before a PUBLIC
//     cutoff date `refPacked` (packed as Y*10000 + M*100 + D).
//  2. The issuer whose BabyJubJub public key is (ax, ay) produced a valid
//     EdDSA-Poseidon signature over Poseidon(year, month, day, secret).
// Because the signed message commits to the birthdate, a valid signature over
// one birthdate cannot be reused to claim a different one, and a self-signed
// credential fails unless (ax, ay) equals the issuer's pinned key (checked by
// the verifier software against its trust anchor).
template AgeCredential() {
    // ---------- public ----------
    signal input ax;         // issuer pubkey X
    signal input ay;         // issuer pubkey Y
    signal input refPacked;  // cutoff date; verifier policy pins its value

    // ---------- private ----------
    signal input year;       // birth year   [1900, 2100]
    signal input month;      // birth month  [1, 12]
    signal input day;        // birth day    [1, 31]
    signal input secret;     // holder secret bound into the signed message
    signal input S;          // EdDSA signature scalar
    signal input R8x;        // EdDSA nonce point
    signal input R8y;

    // ---------- input sanitation (packing injectivity + comparator validity) ----------
    component ycMin = LessEqThan(11); ycMin.in[0] <== 1900; ycMin.in[1] <== year;  ycMin.out === 1;
    component ycMax = LessEqThan(11); ycMax.in[0] <== year;  ycMax.in[1] <== 2100; ycMax.out === 1;
    component mcMin = LessEqThan(4);  mcMin.in[0] <== 1;    mcMin.in[1] <== month; mcMin.out === 1;
    component mcMax = LessEqThan(4);  mcMax.in[0] <== month; mcMax.in[1] <== 12;   mcMax.out === 1;
    component dcMin = LessEqThan(5);  dcMin.in[0] <== 1;    dcMin.in[1] <== day;   dcMin.out === 1;
    component dcMax = LessEqThan(5);  dcMax.in[0] <== day;   dcMax.in[1] <== 31;   dcMax.out === 1;
    // Bound the public date too: LessEqThan is only sound for inputs < 2^27.
    component refMax = LessEqThan(27); refMax.in[0] <== refPacked; refMax.in[1] <== 99991231; refMax.out === 1;

    // Canonical holder secret (also excludes field-equivalent non-canonical reps)
    component secBits = Num2Bits(250); secBits.in <== secret;

    // ---------- age predicate ----------
    // (Y+18, M, D) <= (refY, refM, refD)  <=>  packed comparison, since M<100, D<100.
    // Leap-day rule falls out deterministically: a Feb-29 birthdate reaches
    // majority on Mar-1 of non-leap years (2/29 > 2/28 in packed form).
    signal birthPacked;
    birthPacked <== (year + 18) * 10000 + month * 100 + day;

    component adult = LessEqThan(27);
    adult.in[0] <== birthPacked;
    adult.in[1] <== refPacked;
    adult.out === 1;

    // ---------- signature over the exact birthdate being claimed ----------
    component msgHash = Poseidon(4);
    msgHash.inputs[0] <== year;
    msgHash.inputs[1] <== month;
    msgHash.inputs[2] <== day;
    msgHash.inputs[3] <== secret;

    component sig = EdDSAPoseidonVerifier();
    sig.enabled <== 1;
    sig.Ax  <== ax;
    sig.Ay  <== ay;
    sig.S   <== S;
    sig.R8x <== R8x;
    sig.R8y <== R8y;
    sig.M   <== msgHash.out;
}

component main {public [ax, ay, refPacked]} = AgeCredential();
