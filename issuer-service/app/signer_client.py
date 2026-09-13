import requests

from . import config


class SignerUnavailable(Exception):
    pass


def get_public_key(timeout=2.0) -> dict:
    try:
        r = requests.get(config.SIGNER_URL + "/pubkey",
                         headers={"x-signer-token": config.SIGNER_TOKEN}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise SignerUnavailable(str(e))


def issue_signature(year: int, month: int, day: int, timeout=10.0) -> dict:
    try:
        r = requests.post(config.SIGNER_URL + "/issue",
                          json={"year": year, "month": month, "day": day},
                          headers={"x-signer-token": config.SIGNER_TOKEN}, timeout=timeout)
        if r.status_code != 200:
            raise SignerUnavailable(f"signer responded {r.status_code}: {r.text[:200]}")
        return r.json()
    except SignerUnavailable:
        raise
    except Exception as e:
        raise SignerUnavailable(str(e))
