"""Extract view implementation."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.stego_engine import IStegoEngine
from ...core.types import OperationResult
from ...utils.threading import Worker, WorkerConfig
from ..widgets.file_picker import FilePicker


class ExtractView(QWidget):
    """UI for extracting payloads."""

    operationFinished = pyqtSignal(OperationResult)

    def __init__(self, engine: IStegoEngine, thread_pool: QThreadPool | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._progress_dialog: Optional[QProgressDialog] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Extract hidden payloads")
        header.setObjectName("viewTitle")
        layout.addWidget(header)

        input_box = QGroupBox("Stego File")
        form = QFormLayout(input_box)
        self._file_picker = FilePicker(self, "Select stego file")
        form.addRow("Stego file", self._file_picker)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password", self._password_edit)
        layout.addWidget(input_box)

        self._output_text = QPlainTextEdit()
        self._output_text.setReadOnly(True)
        layout.addWidget(self._output_text)

        button_layout = QHBoxLayout()
        self._extract_button = QPushButton("Extract")
        button_layout.addWidget(self._extract_button)
        layout.addLayout(button_layout)
        layout.addStretch(1)

        self._extract_button.clicked.connect(self._handle_extract)

    def _handle_extract(self) -> None:
        stego_file = self._file_picker.path
        if not stego_file:
            return
        password = self._password_edit.text() or None
        config = WorkerConfig(
            fn=self._engine.extract,
            args=(stego_file, password),
        )
        worker = Worker(config)
        worker.signals.result.connect(self._on_extract_result)
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.finished.connect(self._close_progress)
        self._thread_pool.start(worker)
        self._show_progress(worker)

    def _show_progress(self, worker: Worker) -> None:
        dialog = QProgressDialog("Extracting…", "Cancel", 0, 0, self)
        dialog.setWindowTitle("Extract")
        dialog.canceled.connect(worker.cancel)
        dialog.show()
        self._progress_dialog = dialog

    def _close_progress(self) -> None:
        if self._progress_dialog:
            self._progress_dialog.hide()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None

    def _on_worker_error(self, exc: Exception) -> None:
        result = OperationResult(
            operation="extract",
            target=self._file_picker.path or Path(),
            success=False,
            message=str(exc),
            duration_s=0.0,
        )
        self.operationFinished.emit(result)

    def _on_extract_result(self, payload: bytes) -> None:
        try:
            decoded = payload.decode()
        except UnicodeDecodeError:
            decoded = "<binary payload>"
        self._output_text.setPlainText(decoded)
        result = OperationResult(
            operation="extract",
            target=self._file_picker.path or Path(),
            success=True,
            message="Extraction completed",
            duration_s=0.0,
        )
        self.operationFinished.emit(result)
