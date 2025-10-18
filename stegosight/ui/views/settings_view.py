"""Settings view implementation."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...utils.theming import apply_theme
from ..widgets.file_picker import FilePicker


class SettingsView(QWidget):
    """Application settings persisted using :class:`QSettings`."""

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Application Settings")
        header.setObjectName("viewTitle")
        layout.addWidget(header)

        general_box = QGroupBox("General")
        form = QFormLayout(general_box)
        self._output_picker = FilePicker(self, "Select default output", select_directory=True)
        form.addRow("Default output", self._output_picker)
        self._overwrite_checkbox = QCheckBox("Overwrite existing files")
        form.addRow(self._overwrite_checkbox)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Light", "Dark"])
        form.addRow("Theme", self._theme_combo)
        layout.addWidget(general_box)

        security_box = QGroupBox("Security")
        security_form = QFormLayout(security_box)
        self._aes_checkbox = QCheckBox("Enable AES-GCM by default")
        security_form.addRow(self._aes_checkbox)
        self._argon_memory = QSpinBox()
        self._argon_memory.setRange(32, 1024)
        security_form.addRow("Argon2 Memory", self._argon_memory)
        self._argon_time = QSpinBox()
        self._argon_time.setRange(1, 10)
        security_form.addRow("Argon2 Time", self._argon_time)
        layout.addWidget(security_box)

        footer = QHBoxLayout()
        self._save_button = QPushButton("Save")
        footer.addWidget(self._save_button)
        layout.addLayout(footer)
        layout.addStretch(1)

        self._save_button.clicked.connect(self._save_settings)

    def _load_settings(self) -> None:
        self._output_picker.path = Path(self._settings.value("output", "")) if self._settings.contains("output") else None
        self._overwrite_checkbox.setChecked(self._settings.value("overwrite", False, bool))
        theme = self._settings.value("theme", "Light")
        idx = self._theme_combo.findText(theme, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._aes_checkbox.setChecked(self._settings.value("aes", True, bool))
        self._argon_memory.setValue(int(self._settings.value("argon_memory", 64)))
        self._argon_time.setValue(int(self._settings.value("argon_time", 3)))

    def _save_settings(self) -> None:
        output = self._output_picker.path
        if output:
            self._settings.setValue("output", str(output))
        self._settings.setValue("overwrite", self._overwrite_checkbox.isChecked())
        self._settings.setValue("theme", self._theme_combo.currentText())
        self._settings.setValue("aes", self._aes_checkbox.isChecked())
        self._settings.setValue("argon_memory", self._argon_memory.value())
        self._settings.setValue("argon_time", self._argon_time.value())
        app = QApplication.instance()
        if app:
            base_path = Path(__file__).resolve().parents[2]
            apply_theme(app, self._theme_combo.currentText().lower(), base_path)
