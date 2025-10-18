"""Theme helpers for STEGOSIGHT."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from PyQt6.QtCore import QFile, QTextStream
from PyQt6.QtWidgets import QApplication


THEMES: dict[Literal["light", "dark"], str] = {
    "light": "assets/light.qss",
    "dark": "assets/dark.qss",
}


def apply_theme(app: QApplication, theme: Literal["light", "dark"], base_path: Path) -> None:
    """Load and apply a QSS theme relative to *base_path*."""

    relative_path = THEMES.get(theme)
    if not relative_path:
        return
    qss_path = base_path / "ui" / relative_path
    if not qss_path.exists():
        return
    file = QFile(str(qss_path))
    if not file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
        return
    stream = QTextStream(file)
    app.setStyleSheet(stream.readAll())
    file.close()
