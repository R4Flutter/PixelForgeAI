"""
about.py
--------
Version / developer / support page. Also hosts a (placeholder) "Check for
updates" button wired to ``backend.updater.UpdateChecker``.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from backend.updater import (
    APP_NAME, APP_PUBLISHER, APP_SUPPORT_EMAIL, APP_VERSION, APP_WEBSITE,
    UpdateChecker,
)
from components.buttons import PrimaryButton, GhostButton
from components.cards import SectionCard
from components.icons import pixmap


class AboutPage(QWidget):
    """Static about / update page."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 32)
        root.setSpacing(20)

        head = QHBoxLayout()
        head.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(pixmap("logo", 56, color="#6366F1", accent="#A5B4FC"))
        head.addWidget(logo, alignment=Qt.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        name = QLabel(APP_NAME)
        name.setObjectName("PageTitle")
        ver = QLabel(f"Version {APP_VERSION}")
        ver.setObjectName("PageSubtitle")
        who = QLabel(f"by {APP_PUBLISHER}")
        who.setObjectName("Hint")
        titles.addWidget(name)
        titles.addWidget(ver)
        titles.addWidget(who)
        head.addLayout(titles)
        head.addStretch(1)
        root.addLayout(head)

        card = SectionCard("About")
        blurb = QLabel(
            "PixelForgeAI prepares print-ready image assets in one click: "
            "background removal, AI upscaling for photos, and print-safe "
            "resizing to a transparent 4000×4000 PNG. Built for print-on-demand, "
            "Etsy, Shopify, and Amazon sellers."
        )
        blurb.setWordWrap(True)
        blurb.setObjectName("FieldLabel")
        card.addWidget(blurb)
        root.addWidget(card)

        links = SectionCard("Support & links")
        self._site = QLabel(f'Website  <span style="color:#A5B4FC;">{APP_WEBSITE}</span>')
        self._mail = QLabel(f'Support  <span style="color:#A5B4FC;">{APP_SUPPORT_EMAIL}</span>')
        for w in (self._site, self._mail):
            w.setObjectName("FieldLabel")
            w.setWordWrap(True)
            links.addWidget(w)
        root.addWidget(links)

        upd = SectionCard("Updates")
        self._upd_status = QLabel("Up to date.")
        self._upd_status.setObjectName("FieldLabel")
        self._upd_status.setWordWrap(True)
        upd.addWidget(self._upd_status)
        actions = QHBoxLayout()
        self._btn_check = PrimaryButton("Check for updates")
        self._btn_check.clicked.connect(self._check_updates)
        actions.addWidget(self._btn_check)
        actions.addStretch(1)
        upd.addLayout(actions)
        root.addWidget(upd)

        root.addStretch(1)

        foot = QLabel(f"© 2026 {APP_PUBLISHER}. All rights reserved.")
        foot.setObjectName("FooterCopy")
        foot.setAlignment(Qt.AlignCenter)
        root.addWidget(foot)

    # ------------------------------------------------------------------ #
    def _check_updates(self) -> None:
        self._btn_check.setEnabled(False)
        self._upd_status.setText("Checking…")
        info = UpdateChecker().check()
        self._btn_check.setEnabled(True)
        if info.up_to_date:
            self._upd_status.setText(
                f"You're up to date — version {info.current_version}."
            )
        else:
            self._upd_status.setText(
                f"Update available: {info.latest_version} "
                f"(you have {info.current_version})."
            )
