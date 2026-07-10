"""
license_crypto.py
------------------
Asymmetric signing primitives for offline license keys.

The application bundles ONLY the public half of an Ed25519 keypair
(``backend/keys/license_pub.pem``). Keys can therefore be *verified* inside the
shipped binary but never *minted* by it. The matching private key lives on the
developer's machine and is used by ``tools/keygen.py`` to issue customer
licences. Reverse-engineering the binary exposes the public key only, which is
useless for forging keys.

Payload codec
-------------
A licence payload is a small JSON document. It is serialised, signed with
Ed25519, and encoded as a single pasteable string::

    PFAI<EDITION>.<payload_b64url>.<signature_b64url>

``cryptography`` is the only non-stdlib dependency and ships pre-built wheels
for Windows, so it builds cleanly into the PyInstaller bundle.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_KEY_PREFIX = "PFAI"
# ``.`` is the JWT-style separator: it is NOT in the base64url alphabet
# ([A-Za-z0-9_-], '=' stripped), so neither the payload nor the 64-byte
# signature can ever contain it - which means ``split(_KEY_DIVIDER)`` is
# unambiguous. Using ``-`` here (the earlier value) was a latent bug, since
# base64url emits both ``-`` and ``_`` and ``split("-")`` would shatter a key
# whose signature happened to contain a dash.
_KEY_DIVIDER = "."


# --------------------------------------------------------------------------- #
# base64url helpers (no padding -> paste-friendly)                            #
# --------------------------------------------------------------------------- #
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


# --------------------------------------------------------------------------- #
# Key (de)serialisation                                                        #
# --------------------------------------------------------------------------- #
def load_public_key(pem_path: Path) -> Ed25519PublicKey:
    """Load the bundled Ed25519 public key from a PEM file."""
    pem = Path(pem_path).read_bytes()
    return serialization.load_pem_public_key(pem)  # type: ignore[return-value]


def load_private_key(pem_path: Path) -> Ed25519PrivateKey:
    """Load the master Ed25519 private key (keygen tooling only)."""
    pem = Path(pem_path).read_bytes()
    return serialization.load_pem_private_key(pem, password=None)  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Licence key encode / decode                                                 #
# --------------------------------------------------------------------------- #
def encode_key(edition: int, payload: Dict[str, Any], private_key: Ed25519PrivateKey) -> str:
    """Serialise + sign ``payload`` into a pasteable licence key string."""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = private_key.sign(body)
    return f"{_KEY_PREFIX}{edition}{_KEY_DIVIDER}{_b64url_encode(body)}{_KEY_DIVIDER}{_b64url_encode(signature)}"


def decode_key(
    key: str, public_key: Ed25519PublicKey
) -> Tuple[int, Dict[str, Any]]:
    """Verify ``key``'s signature and return ``(edition, payload)``.

    Raises ``InvalidKey`` if the format is wrong, the signature does not match,
    or the edition prefix is missing. Never returns for a forged key.
    """
    key = (key or "").strip()
    parts = key.split(_KEY_DIVIDER)
    if len(parts) != 3:
        raise InvalidKey("Malformed key - expected three dot-separated segments")
    prefix, payload_b64, sig_b64 = parts

    if not prefix.startswith(_KEY_PREFIX):
        raise InvalidKey("Unknown key prefix")
    edition_str = prefix[len(_KEY_PREFIX):]
    if not edition_str.isdigit():
        raise InvalidKey("Missing or non-numeric edition")
    edition = int(edition_str)

    try:
        body = _b64url_decode(payload_b64)
        signature = _b64url_decode(sig_b64)
    except (ValueError, base64.binascii.Error) as exc:
        raise InvalidKey(f"Undecodable key body: {exc}") from exc

    try:
        public_key.verify(signature, body)
    except InvalidSignature as exc:
        raise InvalidKey("Invalid signature - key is forged or corrupted") from exc

    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidKey(f"Payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidKey("Payload is not an object")
    return edition, payload


class InvalidKey(Exception):
    """Raised when a licence key fails format or signature verification."""
