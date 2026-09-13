pragma circom 2.0.0;

include "../node_modules/circomlib/circuits/comparators.circom";
include "../node_modules/circomlib/circuits/bitify.circom";
include "../node_modules/circomlib/circuits/poseidon.circom";
include "../node_modules/circomlib/circuits/eddsaposeidon.circom";

template AgeCredentialVariant() {
    signal input ax;
    signal input ay;
    signal input refPacked;
    signal input year;
    signal input month;
    signal input day;
    signal input secret;
    signal input pad;        // EXTRA private input: changes the R1CS/VK
    signal input S;
    signal input R8x;
    signal input R8y;

    component ycMin = LessEqThan(11); ycMin.in[0] <== 1900; ycMin.in[1] <== year;  ycMin.out === 1;
    component ycMax = LessEqThan(11); ycMax.in[0] <== year;  ycMax.in[1] <== 2100; ycMax.out === 1;
    component mcMin = LessEqThan(4);  mcMin.in[0] <== 1;    mcMin.in[1] <== month; mcMin.out === 1;
    component mcMax = LessEqThan(4);  mcMax.in[0] <== month; mcMax.in[1] <== 12;   mcMax.out === 1;
    component dcMin = LessEqThan(5);  dcMin.in[0] <== 1;    dcMin.in[1] <== day;   dcMin.out === 1;
    component dcMax = LessEqThan(5);  dcMax.in[0] <== day;   dcMax.in[1] <== 31;   dcMax.out === 1;
    component refMax = LessEqThan(27); refMax.in[0] <== refPacked; refMax.in[1] <== 99991231; refMax.out === 1;

    component secBits = Num2Bits(250); secBits.in <== secret;
    component padBit = IsZero(); padBit.in <== pad; padBit.out === 1 - pad; // pad*(pad-1)==0, satisfiable

    signal birthPacked;
    birthPacked <== (year + 18) * 10000 + month * 100 + day;
    component adult = LessEqThan(27);
    adult.in[0] <== birthPacked;
    adult.in[1] <== refPacked;
    adult.out === 1;

    component msgHash = Poseidon(4);
    msgHash.inputs[0] <== year; msgHash.inputs[1] <== month;
    msgHash.inputs[2] <== day;  msgHash.inputs[3] <== secret;

    component sig = EdDSAPoseidonVerifier();
    sig.enabled <== 1; sig.Ax <== ax; sig.Ay <== ay;
    sig.S <== S; sig.R8x <== R8x; sig.R8y <== R8y; sig.M <== msgHash.out;
}

component main {public [ax, ay, refPacked]} = AgeCredentialVariant();
