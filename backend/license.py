"""
license.py
----------
Licence activation for PixelForgeAI: Ed25519-signed offline keys plus a
machine-bound, tamper-sealed activation record.

Key layer (license_crypto.py)
  Keys are signed with the developer's Ed25519 PRIVATE key (tools/keygen.py).
  The shipped app bundles only the PUBLIC key (backend/keys/license_pub.pem),
  so a customer can *verify* a key but never *forge* one. The key encodes an
  edition (major version); a V1 key grants V1.x only — V2 keys are rejected on
  a V1 build, which is how paid major upgrades are gated.

Storage layer (storage_crypto.py)
  The activation record is HMAC-sealed and keyed with this machine's
  fingerprint, so the file cannot be hand-edited or copied machine-to-machine.
  Editing it invalidates the HMAC and the app fails *closed* (treats itself as
  not activated). The fat moat is the asymmetric key layer above; this layer
  only defeats casual local tampering.

This module does NOT touch the AI pipeline. Whether processing is *allowed* is
decided by backend.entitlement, which consults both the licence (paid) and the
trial (backend.trial).
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional

from backend import license_config, license_crypto, storage_crypto
from backend.state import paths


class LicenseTier(str, Enum):
    FREE = "free"
    PRO = "pro"

    @property
    def label(self) -> str:
        return {"free": "Free", "pro": "Pro"}[self.value]


@dataclass
class LicenseInfo:
    tier: LicenseTier = LicenseTier.FREE
    key: str = ""
    owner: str = ""
    edition: int = 1            # major version this key grants
    activated_at: float = 0.0   # epoch seconds; 0 == never
    expires_at: float = 0.0    # 0 == no expiry (lifetime)
    machine_id: str = ""       # machine the activation is bound to

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tier"] = self.tier.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LicenseInfo":
        data = dict(data or {})
        try:
            data["tier"] = LicenseTier(data.get("tier", "free"))
        except ValueError:
            data["tier"] = LicenseTier.FREE
        try:
            data["edition"] = int(data.get("edition", 1) or 1)
        except (TypeError, ValueError):
            data["edition"] = 1
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    @property
    def is_pro(self) -> bool:
        if self.tier is not LicenseTier.PRO:
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True


# Edition-byte → tier label, kept narrow: V1 ships LIFETIME only. Unknown tiers
# on an older app are rejected (not mis-honored) so future subscription tiers
# can be added without breaking already-issued lifetime keys.
_TIER_LIFETIME = "lifetime"


class LicenseManager:
    """Verifies Ed25519 keys and persists a machine-bound activation record."""

    def __init__(self) -> None:
        self._info: LicenseInfo = LicenseInfo()
        self._pub = self._load_public_key()
        self.reload()

    # ------------------------------------------------------------------ #
    # Public surface (kept compatible with the old LicenseStore so the
    # GUI only swaps the class name).
    # ------------------------------------------------------------------ #
    @property
    def info(self) -> LicenseInfo:
        return self._info

    @property
    def tier(self) -> LicenseTier:
        return self._info.tier if self._info.is_pro else LicenseTier.FREE

    @property
    def is_pro(self) -> bool:
        return self.tier is LicenseTier.PRO

    def activate(self, key: str, owner: str = "") -> bool:
        """Verify ``key`` and, if valid, persist the activation. Returns True
        on success, False for any verification failure (never raises)."""
        if self._pub is None:
            return False
        key = (key or "").strip()
        try:
            edition, payload = license_crypto.decode_key(key, self._pub)
        except license_crypto.InvalidKey:
            return False

        if edition != license_config.APP_EDITION:
            return False
        tier = payload.get("t")
        if tier not in (None, _TIER_LIFETIME):
            return False
        # Optional machine-lock: a key minted with "mid" only activates on the
        # machine it was minted for. Default V1 keys carry no "mid" and are
        # unbound, so the same key re-activates a reinstall / new machine.
        key_mid = payload.get("mid")
        if key_mid and key_mid != storage_crypto.machine_id():
            return False

        owner = (owner or payload.get("o") or "").strip()
        self._info = LicenseInfo(
            tier=LicenseTier.PRO,
            key=key,
            owner=owner,
            edition=edition,
            activated_at=time.time(),
            expires_at=0.0,
            machine_id=storage_crypto.machine_id(),
        )
        self._save()
        return True

    def deactivate(self) -> None:
        self._info = LicenseInfo()
        self._save()

    def reload(self) -> None:
        """Re-read the activation record from disk (after a fresh activation
        performed through the dialog, for example)."""
        self._info = self._load()

    def mint_test_key(self, owner: str = "") -> Optional[str]:
        """Mint a real signed key using the dev private key, if present.

        Returns ``None`` in a shipped build (no private key bundled), which the
        UI uses to hide the button. Never raises.
        """
        try:
            if not license_config.can_mint():
                return None
            priv = license_crypto.load_private_key(license_config.private_key_path())
        except OSError:
            return None
        payload = {"o": owner or "dev", "t": _TIER_LIFETIME, "iat": int(time.time())}
        return license_crypto.encode_key(license_config.APP_EDITION, payload, priv)

    # ------------------------------------------------------------------ #
    # Persistence (HMAC-sealed, machine-bound)
    # ------------------------------------------------------------------ #
    def _load(self) -> LicenseInfo:
        try:
            blob = paths().license_file.read_text(encoding="utf-8")
        except OSError:
            return LicenseInfo()
        data = storage_crypto.verify_blob(
            blob, storage_crypto.license_secret(), storage_crypto.machine_id()
        )
        if not data:
            # Missing, corrupt, edited, or copied from another machine →
            # fail closed: treat as not activated. The customer simply
            # re-enters their (unbound) key.
            return LicenseInfo()
        return LicenseInfo.from_dict(data)

    def _save(self) -> None:
        blob = storage_crypto.sign_blob(
            self._info.to_dict(),
            storage_crypto.license_secret(),
            storage_crypto.machine_id(),
        )
        storage_crypto.write_atomically(paths().license_file, blob)

    def _load_public_key(self):
        try:
            return license_crypto.load_public_key(license_config.public_key_path())
        except OSError:
            # No bundled public key → verification is impossible. Every key
            # is rejected; the app runs as unlicensed (trial still applies).
            return None
