"""Neutralize view implementation."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.analysis import AnalysisResult, IAnalyzer
from ...core.neutralize import INeutralizer
from ...core.types import OperationResult
from ...utils.threading import Worker, WorkerConfig
from ..widgets.file_picker import FilePicker


class NeutralizeView(QWidget):
    """UI for neutralization workflows."""

    operationFinished = pyqtSignal(OperationResult)

    def __init__(
        self,
        neutralizer: INeutralizer,
        analyzer: IAnalyzer,
        thread_pool: QThreadPool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._neutralizer = neutralizer
        self._analyzer = analyzer
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._progress_dialog: Optional[QProgressDialog] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Neutralize suspicious media")
        header.setObjectName("viewTitle")
        layout.addWidget(header)

        input_box = QGroupBox("Input")
        form = QFormLayout(input_box)
        self._file_picker = FilePicker(self, "Select file")
        form.addRow("File", self._file_picker)
        self._tier_combo = QComboBox()
        self._tier_combo.addItems(["Light", "Standard", "Aggressive"])
        form.addRow("Tier", self._tier_combo)
        layout.addWidget(input_box)

        self._result_label = QLabel("Ready")
        layout.addWidget(self._result_label)

        buttons = QHBoxLayout()
        self._run_button = QPushButton("Neutralize")
        buttons.addWidget(self._run_button)
        layout.addLayout(buttons)
        layout.addStretch(1)

        self._run_button.clicked.connect(self._handle_neutralize)

    def _handle_neutralize(self) -> None:
        file_path = self._file_picker.path
        if not file_path:
            return
        tier = self._tier_combo.currentText().lower()
        config = WorkerConfig(fn=self._neutralizer.neutralize, args=(file_path, tier))
        worker = Worker(config)
        worker.signals.result.connect(self._on_neutralize_done)
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.finished.connect(self._close_progress)
        self._thread_pool.start(worker)
        self._show_progress(worker)

    def _show_progress(self, worker: Worker) -> None:
        dialog = QProgressDialog("Neutralizing…", "Cancel", 0, 0, self)
        dialog.canceled.connect(worker.cancel)
        dialog.show()
        self._progress_dialog = dialog

    def _close_progress(self) -> None:
        if self._progress_dialog:
            self._progress_dialog.hide()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None

    def _on_worker_error(self, exc: Exception) -> None:
        self._result_label.setText(str(exc))
        self.operationFinished.emit(
            OperationResult(
                operation="neutralize",
                target=self._file_picker.path or Path(),
                success=False,
                message=str(exc),
                duration_s=0.0,
            )
        )

    def _on_neutralize_done(self, sanitized: Path) -> None:
        self._result_label.setText(f"Neutralized file saved to {sanitized}")
        self.operationFinished.emit(
            OperationResult(
                operation="neutralize",
                target=sanitized,
                success=True,
                message="Neutralization completed",
                duration_s=0.0,
            )
        )
        config = WorkerConfig(fn=self._analyzer.scan, args=(sanitized, None))
        worker = Worker(config)
        worker.signals.result.connect(self._on_reanalyze_result)
        self._thread_pool.start(worker)

    def _on_reanalyze_result(self, result: AnalysisResult) -> None:
        self._result_label.setText(
            f"Neutralized. New risk score: {result.risk_score}"
        )
