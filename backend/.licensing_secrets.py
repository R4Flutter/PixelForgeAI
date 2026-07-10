"""
secrets_keys.py
---------------
Hidden constants for PixelForgeAI license signing + tamper sealing.

These are *not* cryptographic state-of-the-art; they are an honest, offline,
deterministic scheme good enough for a one-time-payment V1 lifetime license,
where the seller mints signed keys (backend/keygen.py) until Lemon Squeezy's
license API takes over the validation side (see LemonSqueezyValidator in
backend/license.py). The public surface (LicenseEngine / LicenseInfo) is
designed so swapping the validator does not touch the UI.

Key format
----------
Raw payload (6 bytes):
    edition : 1 byte   major version the key entitles (e.g. 1 for V1.x)
    tier    : 1 byte   entitlement flag (1 = lifetime; reserved for future tiers)
    nonce   : 4 bytes  uniqueness (so two keys for the same owner differ)

Auth tag (6 bytes):
    sig = HMAC-SHA256(EDITION_SECRET, payload)[:6]

Token = payload(6) || sig(6) = 12 bytes -> 24 hex chars.
Displayed as:
    PFAI-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
(PFAI prefix + six 4-hex groups.)

Validation:
    * signature matches  -> key was minted with EDITION_SECRET (authentic)
    * edition == 1        -> key is for the CURRENT major (V1). Keys minted for
                             V2 do NOT activate V1 (paid upgrades build on this).
"""
from __future__ import annotations

# Bundled minting secret. Rotating it invalidates every previously issued key.
# For a future paid major (V2.x), mint with a NEW edition byte (2) using the
# same secret — the edition check rejects V2 keys on V1 apps and vice versa.
EDITION_SECRET = "pixelforgeai-v1-lifetime-39bf4d8a"

# The major version THIS running application belongs to. Keys whose edition
# byte differs from this value are rejected as "for another version".
CURRENT_MAJOR_VERSION = 1

# Tamper seal secret used to sign the on-disk trial + activation records so a
# hand-edited file is detected and rejected. Independent from the key secret.
TAMPER_SECRET = "pixelforgeai-seal-7c2a91f0b3"

# Key envelope.
KEY_PREFIX = "PFAI"
NONCE_BYTES = 4
PAYLOAD_BYTES = 6        # edition(1) + tier(1) + nonce(4)
SIGN_BYTES = 6           # truncated HMAC-SHA256
TOKEN_BYTES = PAYLOAD_BYTES + SIGN_BYTES    # 12
TOKEN_HEX_LEN = TOKEN_BYTES * 2             # 24
GROUP_LEN = 4
GROUP_COUNT = TOKEN_HEX_LEN // GROUP_LEN    # 6

# Entitlement tiers stored in the key byte 1. V1 only ships LIFETIME; the byte
# is reserved so future subscription / seat tiers can be added without breaking
# existing keys (an unknown tier on an older app is rejected, not mis-honored).
TIER_LIFETIME = 1
