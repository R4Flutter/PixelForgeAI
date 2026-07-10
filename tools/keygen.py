"""
keygen.py
---------
Offline Ed25519 licence-key generator for PixelForgeAI.

This runs on the **developer's machine only**. It loads the master PRIVATE key
from ``tools/keys/license_priv.pem`` (git-ignored, never shipped) and signs
licence payloads. The shipped app holds only the public key, so it can verify
these keys but cannot forge them.

Examples
--------
    python tools/keygen.py --owner "Jane Buyer <jane@example.com>"
    python tools/keygen.py --owner "jane@example.com" --machine-locked
    python tools/keygen.py --verify PFAI1.<body>.<sig>

Until Lemon Squeezy fulfilment is wired (``backend/license_config.py``), this is
how V1 lifetime keys are minted. Never commit the private key.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import license_config, license_crypto, storage_crypto  # noqa: E402


def mint(owner: str, edition: int, machine_id: str | None) -> str:
    priv = license_crypto.load_private_key(license_config.private_key_path())
    payload = {"o": owner, "t": "lifetime", "iat": int(time.time())}
    if machine_id:
        payload["mid"] = machine_id
    return license_crypto.encode_key(edition, payload, priv)


def verify(key: str) -> int:
    pub = license_crypto.load_public_key(license_config.public_key_path())
    edition, payload = license_crypto.decode_key(key, pub)
    mid = payload.get("mid")
    print(f"OK   edition={edition}  tier={payload.get('t')}  "
          f"owner={payload.get('o')!r}  iat={payload.get('iat')}"
          + (f"  machine_locked={mid!r}" if mid else ""))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Mint / verify PixelForgeAI licence keys.")
    ap.add_argument("--owner", help="Customer name/email burned into the key payload.")
    ap.add_argument("--edition", type=int, default=license_config.APP_EDITION,
                    help="Major version this key grants (default: current build).")
    ap.add_argument("--machine-locked", action="store_true",
                    help="Lock the key to THIS machine's fingerprint (platform.node()).")
    ap.add_argument("--for-machine", help="Lock the key to a specific machine-id string.")
    ap.add_argument("--verify", help="Verify and dump an existing key instead of minting.")
    args = ap.parse_args()

    if args.verify:
        try:
            return verify(args.verify)
        except license_crypto.InvalidKey as exc:
            print(f"INVALID: {exc}", file=sys.stderr)
            return 1

    if not args.owner:
        print("error: --owner is required to mint a key", file=sys.stderr)
        return 2
    if not license_config.can_mint():
        print(
            f"error: private key not found at {license_config.private_key_path()}\n"
            "       keygen runs only on the developer's machine.",
            file=sys.stderr,
        )
        return 3

    mid = args.for_machine or (
        storage_crypto.machine_id() if args.machine_locked else None
    )
    key = mint(args.owner, args.edition, mid)
    print(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
