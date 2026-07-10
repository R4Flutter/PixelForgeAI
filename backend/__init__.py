"""
PixelForgeAI - Backend integration layer.

This package contains ONLY integration glue that talks to the existing,
untouched AI pipeline (``scripts/``). It deliberately never reimplements any
AI logic - it imports the existing functions and orchestrates them.

Modules
-------
job             - immutable job/settings dataclasses + persistence (JSON state).
connector       - the orchestrator: patches ``pipeline.CFG`` and calls
                  ``pipeline.process_single_image`` per image, with pause /
                  cancel / resume and a final format-conversion post-pass
                  (PNG/JPG/WebP).
worker          - ``QThread`` wrapper that runs the connector off the UI thread
                  and emits progress/status/log signals bound to Qt slots.
log_bridge      - a non-invasive ``logging`` handler that observes the AI's own
                  log records (PIPELINE / UPSCALE / REMOVE_BG / scripts.resize)
                  and forwards them to the UI - NO changes to the AI scripts.
license         - Ed25519-signed offline licence activation + a machine-bound
                  (HMAC-sealed) activation record. Forged keys are impossible;
                  the binary carries only the public half.
trial           - 7-day, machine-locked, anti-reset free trial (anchor +
                  witness, fail-closed on tamper).
entitlement     - licence + trial -> one unlock state (LICENSED / TRIAL /
                  LOCKED) the UI and the worker consult.
license_crypto  - Ed25519 key codec (verify-only public key bundled).
license_config  - external licensing knobs (edition, trial days, Lemon
                  Squeezy, key paths).
storage_crypto  - machine-bound HMAC-sealed JSON storage (anti-tamper, stdlib).
updater         - placeholder auto-update architecture.
state           - application settings persistence (load/save JSON).
"""

from __future__ import annotations

__all__ = [
    "job",
    "connector",
    "worker",
    "log_bridge",
    "license",
    "trial",
    "entitlement",
    "license_crypto",
    "license_config",
    "storage_crypto",
    "updater",
    "state",
]
