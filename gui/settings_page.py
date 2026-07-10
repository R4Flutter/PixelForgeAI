"""
settings_page.py
----------------
User-tunable settings bound 1:1 to backend.job.Settings.

This page is presentation only: it never imports or calls the AI pipeline.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backend import license_config
from backend.entitlement import EntitlementManager
from backend.job import (
    BackgroundMode,
    ConflictPolicy,
    DeviceMode,
    FitMode,
    MAX_OUTPUT_DIM,
    MIN_OUTPUT_DIM,
    MetadataPolicy,
    OutputFormat,
    QualityPreset,
    Settings,
    UpscaleMode,
)
from backend.license import LicenseTier
from components.buttons import PrimaryButton, SecondaryButton, GhostButton
from components.cards import SectionCard
from components.icons import icon


class SettingsPage(QWidget):
    """Settings form + licence activation."""

    settings_changed = Signal()

    def __init__(self, entitlement: EntitlementManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")
        self._ent = entitlement
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 32)
        root.setSpacing(20)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        sub = QLabel("Output, quality, compute, file handling, and licence.")
        sub.setObjectName("PageSubtitle")
        root.addWidget(title)
        root.addWidget(sub)

        root.addWidget(self._build_output_card())
        root.addWidget(self._build_quality_card())
        root.addWidget(self._build_compute_card())
        root.addWidget(self._build_license_card())
        root.addStretch(1)

        self._refresh_dynamic_controls()
        self._refresh_license()

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

        self._preset = QComboBox()
        self._preset.addItem("Custom", None)
        for size in (1000, 2000, 3000, 4000, 5000, 6000, 8000):
            self._preset.addItem(f"{size} x {size}", (size, size, FitMode.FIT))
        self._preset.addItem("4000 px wide", (4000, 0, FitMode.WIDTH_ONLY))
        self._preset.currentIndexChanged.connect(self._on_preset_changed)
        form.addRow(self._field("Preset"), self._preset)

        self._width = QSpinBox()
        self._width.setRange(MIN_OUTPUT_DIM, MAX_OUTPUT_DIM)
        self._width.setSingleStep(100)
        self._width.setSuffix(" px")
        self._width.valueChanged.connect(self._on_dim_changed)
        form.addRow(self._field("Width"), self._width)

        self._height = QSpinBox()
        self._height.setRange(0, MAX_OUTPUT_DIM)
        self._height.setSingleStep(100)
        self._height.setSuffix(" px")
        self._height.setSpecialValueText("auto (keep aspect)")
        self._height.valueChanged.connect(self._on_dim_changed)
        form.addRow(self._field("Height"), self._height)

        self._fit = QComboBox()
        self._fit.addItem("Width only (keep aspect)", FitMode.WIDTH_ONLY)
        self._fit.addItem("Fit inside box (pad transparent)", FitMode.FIT)
        self._fit.addItem("Exact (stretch to W x H)", FitMode.EXACT)
        self._fit.currentIndexChanged.connect(self._on_fit_changed)
        form.addRow(self._field("Fit mode"), self._fit)

        self._conflict = QComboBox()
        self._conflict.addItem("Overwrite existing", ConflictPolicy.OVERWRITE)
        self._conflict.addItem("Skip existing", ConflictPolicy.SKIP)
        self._conflict.addItem("Auto rename", ConflictPolicy.AUTO_RENAME)
        self._conflict.currentIndexChanged.connect(self._emit_changed)
        form.addRow(self._field("Existing files"), self._conflict)

        self._bg_mode = QComboBox()
        self._bg_mode.addItem("Transparent", BackgroundMode.TRANSPARENT)
        self._bg_mode.addItem("White", BackgroundMode.WHITE)
        self._bg_mode.addItem("Custom color", BackgroundMode.CUSTOM)
        self._bg_mode.currentIndexChanged.connect(self._on_background_changed)
        form.addRow(self._field("Background"), self._bg_mode)

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

        self._dim_hint = QLabel("")
        self._dim_hint.setObjectName("FieldHint")
        self._dim_hint.setWordWrap(True)
        card.addWidget(self._dim_hint)
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
            self._width.setValue(int(s.output_width))
            self._height.setValue(int(s.output_height))
            self._set_combo(self._fit, s.fit_mode)
            self._set_combo(self._conflict, s.conflict_policy)
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
            self._select_matching_preset()
        finally:
            self._loading = False
        self._refresh_dynamic_controls()

    def get_settings(self) -> Settings:
        conflict = self._enum_data(self._conflict, ConflictPolicy.OVERWRITE)
        bg_color = self._bg_color.text().strip() or "#FFFFFF"
        return Settings(
            output_folder=self._out_folder.text().strip(),
            output_format=self._enum_data(self._fmt, OutputFormat.PNG),
            output_width=int(self._width.value()),
            output_height=int(self._height.value()),
            fit_mode=self._enum_data(self._fit, FitMode.WIDTH_ONLY),
            quality_preset=self._enum_data(self._quality, QualityPreset.HIGH),
            png_compression=int(self._png_compression.value()),
            upscale_mode=self._enum_data(self._upscale, UpscaleMode.X4),
            background_mode=self._enum_data(self._bg_mode, BackgroundMode.TRANSPARENT),
            background_color=bg_color,
            metadata_policy=self._enum_data(self._metadata, MetadataPolicy.STRIP),
            conflict_policy=conflict,
            overwrite=conflict is ConflictPolicy.OVERWRITE,
            device=self._enum_data(self._device, DeviceMode.GPU),
            batch=self._batch.isChecked(),
            jpg_quality=int(self._jpg_q.value()),
            webp_quality=int(self._webp_q.value()),
            jpg_background=bg_color,
            theme="dark",
            accent="indigo",
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

    def _on_preset_changed(self, *_args) -> None:
        data = self._preset.currentData()
        if data is not None:
            width, height, fit = data
            self._loading = True
            try:
                self._width.setValue(int(width))
                self._height.setValue(int(height))
                self._set_combo(self._fit, fit)
            finally:
                self._loading = False
        self._refresh_dynamic_controls()
        self._emit_changed()

    def _on_dim_changed(self, *_args) -> None:
        if not self._loading:
            self._preset.setCurrentIndex(0)
        self._refresh_dynamic_controls()
        self._emit_changed()

    def _on_fit_changed(self, *_args) -> None:
        if not self._loading:
            self._preset.setCurrentIndex(0)
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

        fit = self._enum_data(self._fit, FitMode.WIDTH_ONLY)
        if fit is FitMode.WIDTH_ONLY:
            self._dim_hint.setText(
                f"Final output will be {self._width.value()} px wide; "
                "height follows the source aspect ratio."
            )
        elif self._height.value() < MIN_OUTPUT_DIM:
            self._dim_hint.setText(
                f"Fit and Exact modes need height >= {MIN_OUTPUT_DIM}px."
            )
        else:
            self._dim_hint.setText(
                f"Final canvas will be {self._width.value()} x "
                f"{self._height.value()} px."
            )

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
        # Minted with the dev private key when present; hidden in a shipped
        # build (no private key bundled). Real customer keys come from
        # tools/keygen.py on the developer's machine.
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
        # The "Generate test key" button only makes sense where the private
        # signing key is available (developer machine). Hide it in builds.
        self._btn_gen.setVisible(license_config.can_mint())

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _emit_changed(self, *_args) -> None:
        if not self._loading:
            self.settings_changed.emit()

    def _select_matching_preset(self) -> None:
        current = (
            int(self._width.value()),
            int(self._height.value()),
            self._enum_data(self._fit, FitMode.WIDTH_ONLY),
        )
        for idx in range(self._preset.count()):
            if self._preset.itemData(idx) == current:
                self._preset.setCurrentIndex(idx)
                return
        self._preset.setCurrentIndex(0)

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
