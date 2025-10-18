"""Reusable file picker widget with drag-and-drop support."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)


class FilePicker(QWidget):
    """Simple widget that allows picking files or folders."""

    pathChanged = pyqtSignal(Path)

    def __init__(
        self,
        parent: QWidget | None = None,
        dialog_title: str = "Select file",
        filters: Iterable[str] | None = None,
        select_directory: bool = False,
    ) -> None:
        super().__init__(parent)
        self._dialog_title = dialog_title
        self._filters = ";;".join(filters) if filters else "All files (*)"
        self._select_directory = select_directory

        self._line_edit = QLineEdit(self)
        self._line_edit.setReadOnly(True)
        self._browse_button = QPushButton("Browse…", self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._line_edit)
        layout.addWidget(self._browse_button)

        self._browse_button.clicked.connect(self._open_dialog)
        self.setAcceptDrops(True)

    def _open_dialog(self) -> None:
        if self._select_directory:
            path = QFileDialog.getExistingDirectory(self, self._dialog_title)
        else:
            path, _ = QFileDialog.getOpenFileName(self, self._dialog_title, filter=self._filters)
        if path:
            self.path = Path(path)

    @property
    def path(self) -> Path | None:
        text = self._line_edit.text()
        return Path(text) if text else None

    @path.setter
    def path(self, value: Path | None) -> None:
        if value is None:
            self._line_edit.clear()
        else:
            self._line_edit.setText(str(value))
            self.pathChanged.emit(value)

    # drag and drop events
    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        if not urls:
            return
        local_path = urls[0].toLocalFile()
        if local_path:
            self.path = Path(local_path)
