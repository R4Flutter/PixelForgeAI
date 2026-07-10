"""
trial_expired.py
---------------
Professional "Trial expired" activation dialog shown when the 7-day trial has
ended and no licence is active. Lets the customer enter a key (or click Buy
Now) without leaving the app. On successful activation, the dialog accepts and
the caller proceeds with whatever the user was trying to do.

Pure presentation: it talks to the shared ``EntitlementManager`` only.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from backend import license_config
from backend.entitlement import EntitlementManager
from components.buttons import PrimaryButton, GhostButton
from components.cards import SectionCard


class TrialExpiredDialog(QDialog):
    def __init__(self, entitlement: EntitlementManager, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")
        self.setWindowTitle("Trial ended — PixelForgeAI")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._ent = entitlement

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(14)

        title = QLabel("Your 7-day trial has ended")
        title.setObjectName("PageTitle")
        v.addWidget(title)

        body = QLabel(
            "Thanks for trying PixelForgeAI. To keep turning artwork into "
            "print-ready 4000×4000 transparent PNGs, activate with your "
            "licence key."
        )
        body.setObjectName("PageSubtitle")
        body.setWordWrap(True)
        v.addWidget(body)

        self._status = QLabel("")
        self._status.setObjectName("FieldHint")
        self._status.setWordWrap(True)
        v.addWidget(self._status)

        card = SectionCard("Activate licence")

        self._key = QLineEdit()
        self._key.setPlaceholderText("PFAI1.<payload>.<signature>")
        self._owner = QLineEdit()
        self._owner.setPlaceholderText("Licensed to (name / email)")

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)
        form.addRow(self._field("License key"), self._key)
        form.addRow(self._field("Owner"), self._owner)
        card.addLayout(form)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self._btn_activate = PrimaryButton("  Activate")
        self._btn_activate.clicked.connect(self._activate)

        checkout = license_config.checkout_url()
        if checkout:
            self._btn_buy = PrimaryButton("  Buy now — $49 lifetime")
            self._btn_buy.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(checkout))
            )
        else:
            self._btn_buy = GhostButton("  Buy now — available soon")
            self._btn_buy.setEnabled(False)
            self._btn_buy.setToolTip("Storefront not live yet; contact the seller for a key.")

        self._btn_close = GhostButton("Close")
        self._btn_close.clicked.connect(self.reject)

        actions.addWidget(self._btn_activate)
        actions.addWidget(self._btn_buy)
        actions.addStretch(1)
        actions.addWidget(self._btn_close)
        card.addLayout(actions)

        v.addWidget(card)

    # ------------------------------------------------------------------ #
    def _activate(self) -> None:
        key = self._key.text().strip()
        owner = self._owner.text().strip()
        if not key:
            self._status.setText("Enter your licence key first.")
            self._status.setStyleSheet("color:#F87171;")
            return
        if self._ent.activate(key, owner):
            self.accept()
        else:
            self._status.setText(
                "That key couldn’t be verified. Make sure it’s a PixelForgeAI "
                "V1 key and hasn’t been mistyped."
            )
            self._status.setStyleSheet("color:#F87171;")

    @staticmethod
    def _field(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("FieldLabel")
        return lbl
