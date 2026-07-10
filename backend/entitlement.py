"""
entitlement.py
---------------
The single source of truth for "is this installation allowed to process?"

It combines the paid *licence* (backend.license) with the time-boxed *trial*
(backend.trial) into one small state the UI and the worker consult. The trial
grants the *full* feature set for 7 days — there is no separate "Free" tier —
so the only two meaningful outcomes are:

  * ``LICENSED``  — a paid V1 licence is active.
  * ``TRIAL``     — within the 7-day window (full features, time-boxed).
  * ``LOCKED``    — the trial has expired and no licence is active;
                    processing is disabled until a key is entered.

This module does NOT touch the AI pipeline. The worker asks ``is_unlocked``
before it starts a job (defense in depth); the UI asks ``evaluate`` to decide
which screen and footer to show.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.license import LicenseInfo, LicenseManager, LicenseTier
from backend.trial import TrialManager, TrialStatus


class EntitlementState(str, Enum):
    LICENSED = "licensed"
    TRIAL = "trial"
    LOCKED = "locked"


@dataclass(frozen=True)
class Entitlement:
    state: EntitlementState
    trial_days_remaining: int = 0
    owner: str = ""
    edition: int = 0


class EntitlementManager:
    """Combines licence + trial behind one facade the UI talks to."""

    def __init__(self) -> None:
        self.license = LicenseManager()
        self.trial = TrialManager()
        self.trial.ensure_started()

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #
    def evaluate(self) -> Entitlement:
        if self.license.is_pro:
            info = self.license.info
            return Entitlement(EntitlementState.LICENSED, 0, info.owner, info.edition)
        st = self.trial.status()
        if st.active and not st.expired:
            return Entitlement(EntitlementState.TRIAL, st.days_remaining)
        return Entitlement(EntitlementState.LOCKED, 0)

    @property
    def is_unlocked(self) -> bool:
        return self.evaluate().state is not EntitlementState.LOCKED

    def trial_status(self) -> TrialStatus:
        return self.trial.status()

    # ------------------------------------------------------------------ #
    # Facade over the licence store (so the GUI doesn't reach through)
    # ------------------------------------------------------------------ #
    @property
    def is_pro(self) -> bool:
        return self.license.is_pro

    @property
    def info(self) -> LicenseInfo:
        return self.license.info

    def activate(self, key: str, owner: str = "") -> bool:
        ok = self.license.activate(key, owner)
        if ok:
            self.license.reload()
        return ok

    def deactivate(self) -> None:
        self.license.deactivate()
        self.license.reload()

    def mint_test_key(self, owner: str = "") -> Optional[str]:
        return self.license.mint_test_key(owner)

    def reload(self) -> None:
        self.license.reload()
