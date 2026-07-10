"""
license_config.py
-------------------
Externally-tunable knobs for the licensing / trial system.

Everything here is read at runtime, so flipping a value + shipping a new build
is the only change needed to go from the offline pre-launch keys to live Lemon
Squeezy fulfilment. Until the Lemon Squeezy fields are populated, the app
validates ``PFAI``-prefixed offline keys only (see [pixelforgeai-product]).

Environment overrides
---------------------
Leaving a field blank here and setting the matching env var on the build/packaging
side lets a CI build bake in real credentials without touching source. Env vars
win over the in-file defaults.

No AI backend code is touched by this module.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Product identity                                                            #
# --------------------------------------------------------------------------- #
# Current PAID major version this build grants access to. Bump on a paid
# major release (v2, v3...). A v1 licence key does NOT unlock v2 - the edition
# is encoded into the key and checked with strict-equals in LicenseManager.
APP_EDITION = 1

# Length of the free trial, in whole days, counted from first launch.
TRIAL_DAYS = 7

# --------------------------------------------------------------------------- #
# Lemon Squeezy (fulfilment) - populated when the storefront goes live.       #
# --------------------------------------------------------------------------- #
# Checkout URL the "Buy Now" button opens in the default browser.
# Example: "https://pixelforgeai.lemonsqueezy.com/buy/abcd-1234..."
LEMON_SQUEEZY_CHECKOUT_URL = ""

# Server-side API key used to validate a customer's LS licence key online at
# activation time. Empty -> the LS online path is disabled and only offline
# PFAI keys are accepted (the pre-launch state).
LEMON_SQUEEZY_API_KEY = ""

# Store / product id used when calling the LS License API. Optional - only
# needed if you want to additionally pin activations to a specific product.
LEMON_SQUEEZY_PRODUCT_ID = ""

# LS License API base URL. Rarely changes.
LEMON_SQUEEZY_API_BASE = "https://api.lemonsqueezy.com/v1"


def _env(name: str, default: str) -> str:
    """Return the env override if set, else the default."""
    val = os.environ.get(name)
    return val.strip() if val and val.strip() else default


def checkout_url() -> str:
    return _env("PFAI_LS_CHECKOUT_URL", LEMON_SQUEEZY_CHECKOUT_URL)


def ls_api_key() -> str:
    return _env("PFAI_LS_API_KEY", LEMON_SQUEEZY_API_KEY)


def ls_api_base() -> str:
    return _env("PFAI_LS_API_BASE", LEMON_SQUEEZY_API_BASE).rstrip("/")


def ls_product_id() -> str:
    return _env("PFAI_LS_PRODUCT_ID", LEMON_SQUEEZY_PRODUCT_ID)


def ls_configured() -> bool:
    """True when the Lemon Squeezy online path is usable at all."""
    return bool(checkout_url()) and bool(ls_api_key())


# --------------------------------------------------------------------------- #
# Bundled public key location                                                  #
# --------------------------------------------------------------------------- #
def public_key_path() -> Path:
    """The Ed25519 public key bundled with the app (used to verify keys)."""
    # Frozen PyInstaller builds resolve next to the executable; in-source runs
    # resolve relative to this file.
    try:
        root = Path(__file__).resolve().parent.parent
    except NameError:
        root = Path.cwd()
    return root / "backend" / "keys" / "license_pub.pem"


# --------------------------------------------------------------------------- #
# Developer-only signing key (keygen + dev "Generate test key")                #
# --------------------------------------------------------------------------- #
# The PRIVATE half lives at tools/keys/license_priv.pem and is git-ignored. It
# is never bundled into a shipped build, so the presence of this file is a
# reliable "am I on the developer's machine?" signal: the in-app Generate test
# key button and tools/keygen.py both refuse to run without it, and frozen
# builds can't mint keys.
def private_key_path() -> Path:
    try:
        root = Path(__file__).resolve().parent.parent
    except NameError:
        root = Path.cwd()
    return root / "tools" / "keys" / "license_priv.pem"


def can_mint() -> bool:
    """True only when the master private key is present (developer machine)."""
    return private_key_path().exists()
