ALLOWED_TOP = {"schema", "issuer_id", "issued_at", "issuer_pub", "subject", "holder_secret", "signature"}
ALLOWED_NESTED = {
    "issuer_pub": {"ax", "ay"},
    "subject": {"dob"},
    "dob": {"year", "month", "day"},
    "signature": {"R8x", "R8y", "S"},
}
FORBIDDEN_KEY_HINTS = ("photo", "image", "video", "embed", "face", "frame", "selfie", "biomet", "iris", "voice")


def validate_credential_structure(cred: dict):
    """Structural privacy guard: the credential may NEVER carry biometric data.
    Raises ValueError on any deviation. Used before returning a credential."""
    if cred.get("schema") != "zkkyc-credential-v1":
        raise ValueError("bad schema")
    extra = set(cred.keys()) - ALLOWED_TOP
    if extra:
        raise ValueError(f"forbidden top-level fields: {sorted(extra)}")
    for key in cred.keys():
        lk = key.lower()
        if any(h in lk for h in FORBIDDEN_KEY_HINTS):
            raise ValueError(f"forbidden field name: {key}")
    for parent, allowed in ALLOWED_NESTED.items():
        if parent in cred:
            node = cred[parent]
            if isinstance(node, dict):
                bad = set(node.keys()) - allowed
                if bad:
                    raise ValueError(f"forbidden fields in {parent}: {sorted(bad)}")
    dob = cred["subject"]["dob"]
    if not all(isinstance(dob[k], int) for k in ("year", "month", "day")):
        raise ValueError("dob fields must be integers")
    return True
