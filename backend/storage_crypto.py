"""
storage_crypto.py
-------------------
Symmetric, machine-bound HMAC-signed JSON storage for local state.

This is *anti-tamper*, not secrecy: the persisted blob is an install timestamp
or a licence record, never a secret value. The HMAC (a) detects any edit to
the bytes and (b) is keyed with the machine fingerprint so a blob copied from
another machine does not validate. That defeats casual bypass
("open it in Notepad and bump the date" / "mail trial.lock to a friend") while
staying stdlib-only.

Threat model (deliberate, for a USD-49 desktop app): a determined attacker who
extracts the per-binary secret from the shipped code can forge local state.
The real moat is the **asymmetric** licence-key layer in ``license_crypto.py``
- the binary holds only the public key, so forged *keys* are impossible.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import platform
from pathlib import Path
from typing import Dict, Optional

# Per-binary secrets. Not meaningfully secret under static analysis, but they
# sit above "edit the JSON by hand". Distinct salts keep trial and licence
# storage non-interchangeable.
_LICENSE_STORAGE_SECRET = b"pfai-storage-v1-9f3a7e2c1b4d9a"
_TRIAL_STORAGE_SECRET = b"pfai-trial-v1-2c7e1a93f40b8d6c5e"

LICENSE_STORAGE_BLOB = "license_v1"
TRIAL_STORAGE_BLOB = "trial_v1"


def machine_id() -> str:
    """Best-effort stable per-machine fingerprint. ``""`` if unavailable.

    Used only to bind HMAC blobs to the machine that produced them and (when
    a key is minted that way) to machine-lock a licence. Stable across reboots
    for the overwhelming majority of installs; if it ever drifts, the user
    simply re-enters the same (unbound, by default) licence key.
    """
    return str(platform.node() or "").strip()


def _hmac_key(secret: bytes, mid: str) -> bytes:
    return hashlib.sha256(secret + (mid or "").encode("utf-8")).digest()


def sign_blob(payload: Dict, secret: bytes, mid: str) -> str:
    """Encode ``payload`` as ``base64url(json).base64url(hmac)``."""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    mac = hmac.new(_hmac_key(secret, mid), body, hashlib.sha256).digest()
    return f"{_b64(body)}.{_b64(mac)}"


def verify_blob(blob: str, secret: bytes, mid: str) -> Optional[Dict]:
    """Return the payload dict if the HMAC is valid, else ``None``.

    Never raises: a missing/short/malformed blob collapses to ``None`` so the
    caller can apply its own "corrupt -> fail-closed" policy.
    """
    if not blob or not isinstance(blob, str):
        return None
    parts = blob.split(".")
    if len(parts) != 2:
        return None
    try:
        body = _unb64(parts[0])
        given_mac = _unb64(parts[1])
    except Exception:
        return None
    expected_mac = hmac.new(_hmac_key(secret, mid), body, hashlib.sha256).digest()
    if not hmac.compare_digest(given_mac, expected_mac):
        return None
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def license_secret() -> bytes:
    return _LICENSE_STORAGE_SECRET


def trial_secret() -> bytes:
    return _TRIAL_STORAGE_SECRET


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def write_atomically(path: Path, contents: str) -> None:
    """Write ``contents`` to ``path`` via a temp file + atomic replace.

    Never raises: a write failure (read-only dir, disk full) is swallowed so
    the app still runs from in-memory state - it just cannot persist this
    update. Callers that *must* know should check the return (we don't, to
    keep the GUI launch path crash-free).
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(contents, encoding="utf-8")
        import os as _os
        _os.replace(tmp, path)
    except OSError:
        pass
