"""
trial.py
--------
The 7-day, machine-locked, anti-reset free trial.

Two HMAC-sealed copies of the trial's start timestamp are kept on disk:

  * an *anchor* at ``paths().trial_lock`` (visible and obvious), and
  * a *witness* at ``paths().trial_witness`` (under ``cache/`` with a neutral
    name, so casually deleting the obvious licence/trial files does not reset
    the trial — the witness still remembers the start time).

Both blobs are keyed with ``storage_crypto.machine_id()``, so a blob copied
from another machine does not validate (the trial is machine-locked). The two
copies let us detect tampering and *fail closed*:

  * both valid            → ``started_at = min(anchor, witness)`` (the earliest
                             start wins, which resists any rollback to a later
                             start time → the safe/shorter-remaining direction)
  * exactly one present    → tampering detected → the trial is *expired*
                             (never silently reset)
  * neither present        → first launch → the clock starts and both are written

This module does NOT touch the AI pipeline. The connector / UI consult
``backend.entitlement`` for the combined unlock decision.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from backend import license_config, storage_crypto
from backend.state import paths


@dataclass(frozen=True)
class TrialStatus:
    started: bool            # has the trial been initialised at least once?
    active: bool             # within the trial window right now
    expired: bool            # past the window (or tampered -> fail closed)
    days_remaining: int      # whole days left (0 once expired)


class TrialManager:
    def __init__(self) -> None:
        self._secret = storage_crypto.trial_secret()
        self._mid = storage_crypto.machine_id()
        self._days = license_config.TRIAL_DAYS

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def ensure_started(self) -> TrialStatus:
        """First-launch initialisation. If no record exists yet, start the
        clock now. Idempotent: subsequent calls just return the current
        status. Always returns the authoritative status."""
        anchor = self._read(paths().trial_lock)
        witness = self._read(paths().trial_witness)
        if anchor is None and witness is None:
            started_at = time.time()
            payload = {"started_at": started_at, "trial_days": self._days}
            self._write(paths().trial_lock, payload)
            self._write(paths().trial_witness, payload)
            return self._status_from(started_at)
        return self._compute(anchor, witness)

    def status(self) -> TrialStatus:
        """Pure read of the current trial state (no side effects)."""
        return self._compute(self._read(paths().trial_lock),
                             self._read(paths().trial_witness))

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _compute(self, anchor: Optional[dict], witness: Optional[dict]) -> TrialStatus:
        if anchor is None and witness is None:
            # Not started yet → treat as active with the full window; the
            # EntitlementManager calls ensure_started() at startup, which
            # persists it before anything asks to process.
            return TrialStatus(False, True, False, self._days)
        if anchor is None or witness is None:
            # Exactly one present → tampering → fail closed (expired).
            return TrialStatus(True, False, True, 0)
        started_at = min(float(anchor.get("started_at", 0)),
                         float(witness.get("started_at", 0)))
        return self._status_from(started_at)

    def _status_from(self, started_at: float) -> TrialStatus:
        expires_at = started_at + self._days * 86_400
        remaining = expires_at - time.time()
        if remaining <= 0:
            return TrialStatus(True, False, True, 0)
        # Whole days remaining, rounded up so "just under 2 days left" reads
        # as 2, not 1 — matches what a customer expects to see.
        days = max(1, int(-(-remaining // 86_400)))
        return TrialStatus(True, True, False, days)

    def _read(self, path) -> Optional[dict]:
        try:
            blob = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return storage_crypto.verify_blob(blob, self._secret, self._mid)

    def _write(self, path, payload: dict) -> None:
        blob = storage_crypto.sign_blob(payload, self._secret, self._mid)
        storage_crypto.write_atomically(path, blob)
