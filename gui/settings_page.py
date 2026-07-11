from __future__ import annotations

import math
import random
import time
from typing import List, Optional

from PySide6.QtCore import (
    Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve,
    Property, QPointF, QRectF, QElapsedTimer,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScroller,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backend import license_config
from backend.entitlement import EntitlementManager
from backend.job import (
    BackgroundMode,
    DeviceMode,
    MetadataPolicy,
    OutputFormat,
    QualityPreset,
    Settings,
    UpscaleMode,
)
from backend.license import LicenseTier
from components.buttons import GhostButton, PrimaryButton, SecondaryButton
from components.cards import SectionCard
from components.icons import icon

_COLOR_ACTIVE = "#7C5CFF"
_COLOR_CARD = "#12141C"
_COLOR_PLAN_CARD = "#181B28"
_COLOR_BORDER = "#1E2230"
_COLOR_TEXT_PRIMARY = "#F4F5FB"
_COLOR_TEXT_SECONDARY = "#C4C8D6"
_COLOR_TEXT_MUTED = "#6B7186"
_COLOR_SUCCESS = "#22C55E"
_COLOR_WARNING = "#FBBF24"


class _ConfettiOverlay(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._particles: list[dict] = []
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def burst(self) -> None:
        self._particles.clear()
        w, h = self.parent().width() if self.parent() else 400, 40
        cx, cy = w / 2, h / 2
        for _ in range(60):
            angle = random.uniform(0, 360)
            speed = random.uniform(3, 8)
            colors = [_COLOR_ACTIVE, _COLOR_SUCCESS, _COLOR_WARNING, "#A78BFA", "#F472B6"]
            self._particles.append({
                "x": cx, "y": cy,
                "vx": math.cos(math.radians(angle)) * speed,
                "vy": math.sin(math.radians(angle)) * speed - 4,
                "life": 1.0, "decay": 0.008 + random.random() * 0.012,
                "color": random.choice(colors),
                "size": 2 + random.random() * 4,
            })
        self._timer.start()
        self.raise_()
        self.show()
        self.update()

    def _tick(self) -> None:
        dead = True
        w, h = self.width(), self.height()
        for p in self._particles:
            p["x"] += p["vx"]
            p["vy"] += 0.15
            p["y"] += p["vy"]
            p["life"] -= p["decay"]
            if p["life"] > 0:
                dead = False
        if dead:
            self._timer.stop()
            self.hide()
        self.update()

    def paintEvent(self, event) -> None:
        if not self._particles:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for pt in self._particles:
            if pt["life"] <= 0:
                continue
            alpha = int(255 * pt["life"])
            c = QColor(pt["color"])
            c.setAlpha(alpha)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            s = pt["size"] * pt["life"]
            p.drawEllipse(QPointF(pt["x"], pt["y"]), s, s)
        p.end()


class _PricingToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(52, 28)
        self._checked = False
        self._hover = 0.0
        self._thumb_pos = 0.0
        self._anim: QPropertyAnimation | None = None
        self.setCursor(Qt.PointingHandCursor)
        self._confetti = _ConfettiOverlay(self)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool) -> None:
        self._checked = checked
        target = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"thumb_pos", self)
        self._anim.setDuration(250)
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.start()
        if checked:
            QTimer.singleShot(100, self._confetti.burst)

    def _get_thumb(self) -> float:
        return self._thumb_pos

    def _set_thumb(self, v: float) -> None:
        self._thumb_pos = v
        self.update()

    thumb_pos = Property(float, _get_thumb, _set_thumb)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.set_checked(self._checked)
            self.toggled.emit(self._checked)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        bg = _tk(_COLOR_ACTIVE) if self._checked else _tk("#2B3042")
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(0, 0, w, h, r, r)

        thumb_x = 2 + (w - h) * self._thumb_pos
        thumb_y = 2
        ts = h - 4
        p.setBrush(_tk("#FFFFFF"))
        p.drawEllipse(QPointF(thumb_x + ts / 2, thumb_y + ts / 2), ts / 2, ts / 2)

        if self._checked:
            c = QColor(_COLOR_SUCCESS)
            c.setAlpha(30)
            p.setBrush(c)
            p.drawEllipse(QPointF(thumb_x + ts / 2, thumb_y + ts / 2), ts, ts)

        p.end()


class _PlanCard(QWidget):
    MIN_H = 420

    def __init__(self, name: str, price: int, yearly_price: int,
                 features: List[str], is_popular: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._name = name
        self._price = price
        self._yearly_price = yearly_price
        self._features = features
        self._is_popular = is_popular
        self._hover = 0.0
        self._press = 0.0
        self._is_monthly = True
        self._anim_hover: QPropertyAnimation | None = None
        self._price_display = float(price)
        self._price_target = float(price)
        self._price_anim: QPropertyAnimation | None = None

        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(200)
        self.setFixedHeight(self.MIN_H)
        self.setMouseTracking(True)

    def set_monthly(self, monthly: bool) -> None:
        self._is_monthly = monthly
        self._price_target = float(self._price if monthly else self._yearly_price)
        self._price_anim = QPropertyAnimation(self, b"price_val", self)
        self._price_anim.setDuration(400)
        self._price_anim.setStartValue(self._price_display)
        self._price_anim.setEndValue(self._price_target)
        self._price_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._price_anim.start()

    def _get_price(self) -> float:
        return self._price_display

    def _set_price(self, v: float) -> None:
        self._price_display = v
        self.update()

    price_val = Property(float, _get_price, _set_price)

    def _get_hover(self) -> float:
        return self._hover

    def _set_hover(self, v: float) -> None:
        self._hover = v
        self.update()

    hover_amount = Property(float, _get_hover, _set_hover)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._anim_hover = QPropertyAnimation(self, b"hover_amount", self)
        self._anim_hover.setDuration(200)
        self._anim_hover.setStartValue(self._hover)
        self._anim_hover.setEndValue(1.0)
        self._anim_hover.setEasingCurve(QEasingCurve.OutCubic)
        self._anim_hover.start()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._anim_hover = QPropertyAnimation(self, b"hover_amount", self)
        self._anim_hover.setDuration(200)
        self._anim_hover.setStartValue(self._hover)
        self._anim_hover.setEndValue(0.0)
        self._anim_hover.setEasingCurve(QEasingCurve.OutCubic)
        self._anim_hover.start()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press = 1.0
            self.update()
            QTimer.singleShot(100, self._release_press)

    def _release_press(self) -> None:
        self._press = 0.0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = 14
        press_scale = 1.0 - self._press * 0.02

        bg = QColor(_COLOR_PLAN_CARD)
        if self._hover > 0:
            hr, hg, hb, _ = bg.getRgb()
            factor = 1.0 + self._hover * 0.06
            bg = QColor(min(255, int(hr * factor)), min(255, int(hg * factor)),
                        min(255, int(hb * factor)))

        border_color = _COLOR_ACTIVE if self._is_popular else _COLOR_BORDER
        border_w = 2 if self._is_popular else 1

        p.save()
        p.translate(w / 2, h / 2)
        p.scale(press_scale, press_scale)
        p.translate(-w / 2, -h / 2)

        p.setPen(QPen(QColor(border_color), border_w))
        p.setBrush(bg)
        p.drawRoundedRect(0, 0, w - 1, h - 1, r, r)

        if self._is_popular:
            badge = QPainterPath()
            badge.moveTo(w - 60, 0)
            badge.lineTo(w, 0)
            badge.lineTo(w - 10, 26)
            badge.lineTo(w - 70, 26)
            badge.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(_COLOR_ACTIVE))
            p.drawPath(badge)
            p.setPen(QColor("#FFFFFF"))
            bf = QFont()
            bf.setFamilies(["Inter", "Segoe UI", "sans-serif"])
            bf.setPointSize(8)
            bf.setWeight(QFont.DemiBold)
            p.setFont(bf)
            p.drawText(QRectF(w - 65, 0, 60, 26), Qt.AlignCenter, "POPULAR")

        px = 18

        p.setPen(QColor(_COLOR_TEXT_MUTED))
        nf = QFont()
        nf.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        nf.setPointSize(10)
        nf.setWeight(QFont.DemiBold)
        p.setFont(nf)
        p.drawText(QRectF(px, 22, w - 36, 16), Qt.AlignLeft | Qt.AlignVCenter, self._name)

        p.setPen(QColor(_COLOR_TEXT_PRIMARY))
        price_f = QFont()
        price_f.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        price_f.setPointSize(34)
        price_f.setWeight(QFont.Bold)
        p.setFont(price_f)
        price_text = f"${int(self._price_display)}"
        p.drawText(QRectF(px, 52, w - 36, 42), Qt.AlignLeft | Qt.AlignVCenter, price_text)

        p.setPen(QColor(_COLOR_TEXT_MUTED))
        period_f = QFont()
        period_f.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        period_f.setPointSize(10)
        p.setFont(period_f)
        period = "/mo" if self._is_monthly else "/yr"
        mw = p.fontMetrics().horizontalAdvance(price_text)
        p.drawText(QRectF(px + mw + 4, 52, 60, 42), Qt.AlignLeft | Qt.AlignVCenter, period)

        p.setPen(QColor(_COLOR_TEXT_MUTED))
        sub_f = QFont()
        sub_f.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        sub_f.setPointSize(8)
        p.setFont(sub_f)
        p.drawText(QRectF(px, 96, w - 36, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   "billed " + ("monthly" if self._is_monthly else "annually"))

        feat_y = 124
        p.setPen(QColor(_COLOR_TEXT_SECONDARY))
        ff = QFont()
        ff.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        ff.setPointSize(9)
        p.setFont(ff)

        for i, feat in enumerate(self._features):
            fy = feat_y + i * 24
            c = QColor(_COLOR_SUCCESS)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(px + 6, fy + 7), 3.5, 3.5)
            p.setPen(QColor(_COLOR_TEXT_SECONDARY))
            p.drawText(QRectF(px + 18, fy, w - 54, 22), Qt.AlignLeft | Qt.AlignVCenter, feat)

        btn_y = h - 58
        btn_h = 40
        btn_r = 10

        if self._is_popular:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(_COLOR_ACTIVE))
            p.drawRoundedRect(QRectF(px, btn_y, w - 36, btn_h), btn_r, btn_r)
            p.setPen(QColor("#FFFFFF"))
        else:
            p.setPen(QPen(QColor(_COLOR_BORDER), 1))
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(px, btn_y, w - 36, btn_h), btn_r, btn_r)
            p.setPen(QColor(_COLOR_TEXT_PRIMARY))

        btn_f = QFont()
        btn_f.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        btn_f.setPointSize(10)
        btn_f.setWeight(QFont.DemiBold)
        p.setFont(btn_f)
        btn_label = "Start Free Trial" if self._is_popular else "Get Started"
        p.drawText(QRectF(px, btn_y, w - 36, btn_h), Qt.AlignCenter, btn_label)

        if self._hover > 0:
            c = QColor(_COLOR_ACTIVE)
            c.setAlpha(int(10 * self._hover))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(0, 0, w - 1, h - 1, r, r)

        p.restore()
        p.end()


class _SubscriptionCard(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 24)
        root.setSpacing(14)

        header = QLabel("SUBSCRIPTION")
        header.setObjectName("SectionLabel")
        root.addWidget(header)

        desc = QLabel("Choose the plan that works for you. All plans include full access to the AI pipeline.")
        desc.setObjectName("FieldHint")
        desc.setWordWrap(True)
        root.addWidget(desc)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(10)
        toggle_row.addStretch(1)

        self._toggle = _PricingToggle()
        toggle_row.addWidget(self._toggle)

        self._toggle_label = QLabel("Annual billing  \u2014  Save 20%")
        self._toggle_label.setStyleSheet(f"color: {_COLOR_ACTIVE}; font-size: 10px; font-weight: 600;")
        toggle_row.addWidget(self._toggle_label)
        toggle_row.addStretch(1)
        root.addLayout(toggle_row)

        plans_row = QHBoxLayout()
        plans_row.setSpacing(16)

        self._plans_data = [
            ("Starter", 19, 15,
             ["Up to 10 projects", "Basic analytics", "48-hour support",
              "Limited API access", "Community access"]),
            ("Professional", 49, 39,
             ["Unlimited projects", "Advanced analytics", "24-hour support",
              "Full API access", "Priority support", "Team collaboration",
              "Custom integrations"]),
            ("Enterprise", 99, 79,
             ["Everything in Pro", "Custom solutions", "Dedicated manager",
              "1-hour support", "SSO / SAML", "Custom contracts",
              "SLA agreement"]),
        ]

        self._plan_cards: List[_PlanCard] = []
        for i, (name, price, yprice, features) in enumerate(self._plans_data):
            is_popular = name == "Professional"
            card = _PlanCard(name, price, yprice, features, is_popular=is_popular)
            self._plan_cards.append(card)
            plans_row.addWidget(card, 1)

        root.addLayout(plans_row)

        self._toggle.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool) -> None:
        for card in self._plan_cards:
            card.set_monthly(not checked)
        self._toggle_label.setText(
            "Annual billing  \u2014  Save 20%" if checked else "Monthly billing"
        )


def _tk(hex_color: str) -> QColor:
    return QColor(hex_color)


class SettingsPage(QWidget):

    settings_changed = Signal()

    def __init__(self, entitlement: EntitlementManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")
        self._ent = entitlement
        self._loading = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            "  background: transparent; width: 6px; margin: 2px 2px 2px 0;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: #262A37; border-radius: 3px; min-height: 30px;"
            "  margin: 0;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "  background: #383E54;"
            "}"
            "QScrollBar::handle:vertical:pressed {"
            "  background: #4F5364;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0; border: none;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "  background: transparent; border: none;"
            "}"
        )

        try:
            QScroller.grabGesture(scroll.viewport(), QScroller.LeftMouseButtonGesture)
            scroller = QScroller.scroller(scroll.viewport())
            prop = scroller.scrollerProperties()
            prop.setScrollMetric(QScroller.ScrollMetric.MaximumVelocity, 0.7)
            prop.setScrollMetric(QScroller.ScrollMetric.DraggingAcceleration, 0.6)
            prop.setScrollMetric(QScroller.ScrollMetric.ScrollingAcceleration, 0.6)
            prop.setScrollMetric(QScroller.ScrollMetric.SnapTime, 0.2)
            scroller.setScrollerProperties(prop)
        except Exception:
            pass

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        root = QVBoxLayout(inner)
        root.setContentsMargins(40, 32, 40, 32)
        root.setSpacing(20)

        header = QLabel("Settings")
        header.setObjectName("PageTitle")
        root.addWidget(header)

        sub = QLabel("Output, quality, pipeline flow, compute, advanced options, and licence.")
        sub.setObjectName("PageSubtitle")
        root.addWidget(sub)

        root.addWidget(self._build_flow_card())
        root.addWidget(self._build_output_card())
        root.addWidget(self._build_quality_card())
        root.addWidget(self._build_compute_card())
        root.addWidget(self._build_advanced_card())
        root.addWidget(self._build_subscription_card())
        root.addWidget(self._build_license_card())
        root.addStretch(1)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll, 1)

        self._refresh_dynamic_controls()
        self._refresh_license()

    # ------------------------------------------------------------------ #
    # Pipeline Flow
    # ------------------------------------------------------------------ #
    def _build_flow_card(self) -> SectionCard:
        card = SectionCard("Pipeline Flow")
        desc = QLabel(
            "Choose which stages run when you start processing. "
            "Unchecked stages are skipped entirely."
        )
        desc.setObjectName("FieldHint")
        desc.setWordWrap(True)
        card.addWidget(desc)

        flow_row = QHBoxLayout()
        flow_row.setSpacing(8)

        self._stage_checks: dict[str, QCheckBox] = {}
        stage_defs = [
            ("Remove Background", "person_remove", "Removes backgrounds from photos"),
            ("AI Upscale", "auto_awesome", "Upscales resolution up to 8x"),
            ("Resize", "photo_size_select_large", "Resizes to exact dimensions"),
            ("Output", "save", "Saves the final result to disk"),
        ]
        for name, ic, tip in stage_defs:
            box = QWidget()
            box.setObjectName("StageCheck")
            box.setStyleSheet(f"""
                #StageCheck {{
                    background-color: {_COLOR_CARD};
                    border: 1px solid {_COLOR_BORDER};
                    border-radius: 12px;
                    padding: 14px 16px;
                }}
                #StageCheck:hover {{
                    border-color: #383E54;
                }}
            """)
            box.setCursor(Qt.PointingHandCursor)
            blay = QVBoxLayout(box)
            blay.setContentsMargins(14, 12, 14, 12)
            blay.setSpacing(4)

            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {_COLOR_TEXT_PRIMARY};
                    font-size: 13px;
                    font-weight: 600;
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 20px;
                    height: 20px;
                    border-radius: 5px;
                    border: 2px solid #383E54;
                    background-color: transparent;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {_COLOR_ACTIVE};
                    border-color: {_COLOR_ACTIVE};
                }}
                QCheckBox::indicator:hover {{
                    border-color: {_COLOR_ACTIVE};
                }}
            """)
            cb.toggled.connect(self._emit_changed)
            cb.toggled.connect(self._on_stage_toggled)
            blay.addWidget(cb)
            self._stage_checks[name] = cb

            tip_lbl = QLabel(tip)
            tip_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
            blay.addWidget(tip_lbl)

            box.mousePressEvent = lambda e, c=cb: (
                c.setChecked(not c.isChecked()) if e.button() == Qt.LeftButton else None
            )

            flow_row.addWidget(box)

        card.addLayout(flow_row)
        return card

    def _on_stage_toggled(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #
    def _build_output_card(self) -> SectionCard:
        card = SectionCard("Output")

        self._out_folder = QLineEdit()
        self._out_folder.setPlaceholderText("output/final (default)")
        self._out_folder.textChanged.connect(self._emit_changed)
        browse = SecondaryButton("  Browse")
        browse.setIcon(icon("folder_open", 16))
        browse.clicked.connect(self._browse_output)
        row = QHBoxLayout()
        row.addWidget(self._out_folder, 1)
        row.addWidget(browse)
        card.addLayout(row)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft)

        self._fmt = QComboBox()
        self._fmt.addItem("PNG", OutputFormat.PNG)
        self._fmt.addItem("JPG", OutputFormat.JPG)
        self._fmt.addItem("WebP", OutputFormat.WEBP)
        self._fmt.addItem("TIFF", OutputFormat.TIFF)
        self._fmt.currentIndexChanged.connect(self._on_format_changed)
        form.addRow(self._field("Format"), self._fmt)

        self._open_output = QCheckBox("Open output folder after completion")
        self._open_output.toggled.connect(self._emit_changed)
        form.addRow("", self._open_output)

        self._bg_mode = QComboBox()
        self._bg_mode.addItem("Transparent", BackgroundMode.TRANSPARENT)
        self._bg_mode.addItem("White", BackgroundMode.WHITE)
        self._bg_mode.addItem("Custom color", BackgroundMode.CUSTOM)
        self._bg_mode.currentIndexChanged.connect(self._on_background_changed)
        form.addRow(self._field("Background fill"), self._bg_mode)

        self._bg_color_label = self._field("Background color")
        self._bg_color = QLineEdit("#FFFFFF")
        self._bg_color.setMaxLength(7)
        self._bg_color.textChanged.connect(self._emit_changed)
        form.addRow(self._bg_color_label, self._bg_color)

        self._metadata = QComboBox()
        self._metadata.addItem("Strip metadata", MetadataPolicy.STRIP)
        self._metadata.addItem("Preserve metadata", MetadataPolicy.PRESERVE)
        self._metadata.currentIndexChanged.connect(self._emit_changed)
        form.addRow(self._field("Metadata"), self._metadata)

        card.addLayout(form)
        return card

    # ------------------------------------------------------------------ #
    # Quality
    # ------------------------------------------------------------------ #
    def _build_quality_card(self) -> SectionCard:
        card = SectionCard("Quality")
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft)

        self._quality = QComboBox()
        self._quality.addItem("Low", QualityPreset.LOW)
        self._quality.addItem("Medium", QualityPreset.MEDIUM)
        self._quality.addItem("High", QualityPreset.HIGH)
        self._quality.addItem("Ultra", QualityPreset.ULTRA)
        self._quality.addItem("Lossless", QualityPreset.LOSSLESS)
        self._quality.currentIndexChanged.connect(self._emit_changed)
        form.addRow(self._field("Output quality"), self._quality)

        self._png_label = self._field("PNG compression")
        self._png_compression = QSpinBox()
        self._png_compression.setRange(0, 9)
        self._png_compression.setValue(6)
        self._png_compression.valueChanged.connect(self._emit_changed)
        form.addRow(self._png_label, self._png_compression)

        self._jpg_label = self._field("JPG quality")
        self._jpg_q = QSpinBox()
        self._jpg_q.setRange(1, 100)
        self._jpg_q.setValue(95)
        self._jpg_q.setSuffix("%")
        self._jpg_q.valueChanged.connect(self._emit_changed)
        form.addRow(self._jpg_label, self._jpg_q)

        self._webp_label = self._field("WebP quality")
        self._webp_q = QSpinBox()
        self._webp_q.setRange(1, 100)
        self._webp_q.setValue(90)
        self._webp_q.setSuffix("%")
        self._webp_q.valueChanged.connect(self._emit_changed)
        form.addRow(self._webp_label, self._webp_q)

        card.addLayout(form)
        return card

    # ------------------------------------------------------------------ #
    # Compute
    # ------------------------------------------------------------------ #
    def _build_compute_card(self) -> SectionCard:
        card = SectionCard("Compute")
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft)

        self._upscale = QComboBox()
        self._upscale.addItem("Auto", UpscaleMode.AUTO)
        self._upscale.addItem("Off", UpscaleMode.OFF)
        self._upscale.addItem("2x", UpscaleMode.X2)
        self._upscale.addItem("4x", UpscaleMode.X4)
        self._upscale.addItem("8x", UpscaleMode.X8)
        self._upscale.currentIndexChanged.connect(self._emit_changed)
        form.addRow(self._field("Upscaling"), self._upscale)

        self._device = QComboBox()
        self._device.addItem("GPU (best-effort CUDA)", DeviceMode.GPU)
        self._device.addItem("CPU", DeviceMode.CPU)
        self._device.currentIndexChanged.connect(self._emit_changed)
        form.addRow(self._field("Device"), self._device)

        self._batch = self._toggle("Batch mode")
        self._batch.setChecked(True)
        form.addRow("", self._batch)

        hint = QLabel(
            "Device selection is a best-effort hint. GPU requires compatible "
            "CUDA/ONNX runtimes; CPU remains the fallback."
        )
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)
        card.addWidget(hint)
        card.addLayout(form)
        return card

    # ------------------------------------------------------------------ #
    # Advanced
    # ------------------------------------------------------------------ #
    def _build_advanced_card(self) -> SectionCard:
        card = SectionCard("Advanced")
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft)

        self._timeout = QSpinBox()
        self._timeout.setRange(10, 3600)
        self._timeout.setValue(120)
        self._timeout.setSuffix(" s")
        self._timeout.setToolTip("Maximum seconds allowed per image before aborting")
        self._timeout.valueChanged.connect(self._emit_changed)
        form.addRow(self._field("Timeout per image"), self._timeout)

        self._retry = QSpinBox()
        self._retry.setRange(0, 10)
        self._retry.setValue(0)
        self._retry.setToolTip("Number of retry attempts when an image fails")
        self._retry.valueChanged.connect(self._emit_changed)
        form.addRow(self._field("Retry attempts"), self._retry)

        self._parallel = QSpinBox()
        self._parallel.setRange(1, 8)
        self._parallel.setValue(1)
        self._parallel.setSuffix(" job(s)")
        self._parallel.setToolTip("Maximum images to process concurrently")
        self._parallel.valueChanged.connect(self._emit_changed)
        form.addRow(self._field("Parallel jobs"), self._parallel)

        self._auto_clean = self._toggle("Auto-clean temporary files")
        self._auto_clean.setChecked(True)
        self._auto_clean.setToolTip("Delete intermediate files after processing completes")
        form.addRow("", self._auto_clean)

        card.addLayout(form)
        return card

    # ------------------------------------------------------------------ #
    # Licence
    # ------------------------------------------------------------------ #
    def _build_license_card(self) -> SectionCard:
        card = SectionCard("Licence")

        self._lic_status = QLabel("Free tier")
        self._lic_status.setObjectName("StageLabel")
        card.addWidget(self._lic_status)

        self._lic_key = QLineEdit()
        self._lic_key.setPlaceholderText("PFAI1.<payload>.<signature>")
        self._lic_owner = QLineEdit()
        self._lic_owner.setPlaceholderText("Licensed to (name / email)")

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow(self._field("License key"), self._lic_key)
        form.addRow(self._field("Owner"), self._lic_owner)
        card.addLayout(form)

        actions = QHBoxLayout()
        self._btn_activate = PrimaryButton("Activate")
        self._btn_activate.clicked.connect(self._activate)
        self._btn_deactivate = GhostButton("Deactivate")
        self._btn_deactivate.clicked.connect(self._deactivate)
        self._btn_gen = GhostButton("Generate test key")
        self._btn_gen.setToolTip("Create a valid offline PRO key for testing.")
        self._btn_gen.clicked.connect(self._generate_test_key)
        actions.addWidget(self._btn_activate)
        actions.addWidget(self._btn_deactivate)
        actions.addStretch(1)
        actions.addWidget(self._btn_gen)
        card.addLayout(actions)
        return card

    # ------------------------------------------------------------------ #
    # Public bind / read
    # ------------------------------------------------------------------ #
    def set_settings(self, s: Settings) -> None:
        self._loading = True
        try:
            self._out_folder.setText(s.output_folder or "")
            self._set_combo(self._fmt, s.output_format)
            self._set_combo(self._bg_mode, s.background_mode)
            self._bg_color.setText(s.background_color or "#FFFFFF")
            self._set_combo(self._metadata, s.metadata_policy)
            self._set_combo(self._quality, s.quality_preset)
            self._png_compression.setValue(int(s.png_compression))
            self._jpg_q.setValue(int(s.jpg_quality))
            self._webp_q.setValue(int(s.webp_quality))
            self._set_combo(self._upscale, s.upscale_mode)
            self._set_combo(self._device, s.device)
            self._batch.setChecked(bool(s.batch))
            self._open_output.setChecked(bool(s.open_output_folder))

            for name, cb in self._stage_checks.items():
                cb.setChecked(name in (s.enabled_stages or ()))

            self._timeout.setValue(int(s.timeout_per_image))
            self._retry.setValue(int(s.retry_attempts))
            self._parallel.setValue(int(s.max_parallel))
            self._auto_clean.setChecked(bool(s.auto_clean_temp))
        finally:
            self._loading = False
        self._refresh_dynamic_controls()

    def get_settings(self) -> Settings:
        bg_color = self._bg_color.text().strip() or "#FFFFFF"
        return Settings(
            output_folder=self._out_folder.text().strip(),
            output_format=self._enum_data(self._fmt, OutputFormat.PNG),
            quality_preset=self._enum_data(self._quality, QualityPreset.HIGH),
            png_compression=int(self._png_compression.value()),
            upscale_mode=self._enum_data(self._upscale, UpscaleMode.X4),
            background_mode=self._enum_data(self._bg_mode, BackgroundMode.TRANSPARENT),
            background_color=bg_color,
            metadata_policy=self._enum_data(self._metadata, MetadataPolicy.STRIP),
            device=self._enum_data(self._device, DeviceMode.GPU),
            batch=self._batch.isChecked(),
            jpg_quality=int(self._jpg_q.value()),
            webp_quality=int(self._webp_q.value()),
            jpg_background=bg_color,
            theme="dark",
            accent="indigo",
            open_output_folder=self._open_output.isChecked(),
            enabled_stages=tuple(
                name for name, cb in self._stage_checks.items() if cb.isChecked()
            ),
            timeout_per_image=int(self._timeout.value()),
            retry_attempts=int(self._retry.value()),
            max_parallel=int(self._parallel.value()),
            auto_clean_temp=self._auto_clean.isChecked(),
        )

    # ------------------------------------------------------------------ #
    # Dynamic behavior
    # ------------------------------------------------------------------ #
    def _on_format_changed(self, *_args) -> None:
        self._refresh_dynamic_controls()
        self._emit_changed()

    def _on_background_changed(self, *_args) -> None:
        self._refresh_dynamic_controls()
        self._emit_changed()

    def _refresh_dynamic_controls(self) -> None:
        fmt = self._enum_data(self._fmt, OutputFormat.PNG)
        self._png_label.setVisible(fmt is OutputFormat.PNG)
        self._png_compression.setVisible(fmt is OutputFormat.PNG)
        self._jpg_label.setVisible(fmt is OutputFormat.JPG)
        self._jpg_q.setVisible(fmt is OutputFormat.JPG)
        self._webp_label.setVisible(fmt is OutputFormat.WEBP)
        self._webp_q.setVisible(fmt is OutputFormat.WEBP)

        bg_mode = self._enum_data(self._bg_mode, BackgroundMode.TRANSPARENT)
        show_color = bg_mode is BackgroundMode.CUSTOM or fmt is OutputFormat.JPG
        self._bg_color_label.setVisible(show_color)
        self._bg_color.setVisible(show_color)

    # ------------------------------------------------------------------ #
    # Subscription
    # ------------------------------------------------------------------ #
    def _build_subscription_card(self) -> _SubscriptionCard:
        return _SubscriptionCard()

    # ------------------------------------------------------------------ #
    # Licence actions
    # ------------------------------------------------------------------ #
    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Output folder", "")
        if folder:
            self._out_folder.setText(folder)
            self._emit_changed()

    def _activate(self) -> None:
        key = self._lic_key.text().strip()
        owner = self._lic_owner.text().strip()
        if self._ent.activate(key, owner):
            self._refresh_license()
            self._emit_changed()
        else:
            self._lic_status.setText("Invalid key - use a PixelForgeAI V1 licence key")
            self._lic_status.setStyleSheet("color:#F87171;")

    def _deactivate(self) -> None:
        self._ent.deactivate()
        self._lic_key.clear()
        self._refresh_license()
        self._emit_changed()

    def _generate_test_key(self) -> None:
        key = self._ent.mint_test_key(self._lic_owner.text().strip() or "dev")
        if key:
            self._lic_key.setText(key)

    def _refresh_license(self) -> None:
        if self._ent.is_pro:
            info = self._ent.info
            self._lic_status.setText(f"Licence: {LicenseTier.PRO.label}")
            self._lic_status.setStyleSheet("color:#22C55E;")
            if info.key and not self._lic_key.text():
                self._lic_key.setText(info.key)
            if info.owner and not self._lic_owner.text():
                self._lic_owner.setText(info.owner)
        else:
            st = self._ent.trial_status()
            if st.active and not st.expired:
                self._lic_status.setText(f"Trial · {st.days_remaining}d left (no licence)")
                self._lic_status.setStyleSheet("color:#8A90A6;")
            elif st.expired:
                self._lic_status.setText("Trial expired - activate a licence")
                self._lic_status.setStyleSheet("color:#F87171;")
            else:
                self._lic_status.setText("Licence: Free tier")
                self._lic_status.setStyleSheet("color:#8A90A6;")
        self._btn_gen.setVisible(license_config.can_mint())

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _emit_changed(self, *_args) -> None:
        if not self._loading:
            self.settings_changed.emit()

    @staticmethod
    def _set_combo(combo: QComboBox, value) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == value:
                combo.setCurrentIndex(idx)
                return
        combo.setCurrentIndex(0)

    @staticmethod
    def _enum_data(combo: QComboBox, default):
        data = combo.currentData()
        if data is None:
            return default
        enum_type = type(default)
        if isinstance(data, enum_type):
            return data
        try:
            return enum_type(data)
        except ValueError:
            return default

    def _field(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("FieldLabel")
        return lbl

    def _toggle(self, text: str) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setObjectName("Toggle")
        cb.stateChanged.connect(self._emit_changed)
        return cb
