"""Analyze view implementation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThreadPool, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.analysis import AnalysisResult, IAnalyzer
from ...core.types import OperationResult
from ...utils.threading import Worker, WorkerConfig
from ..widgets.file_picker import FilePicker


@dataclass(slots=True)
class AnalyzeRow:
    """Represents a row in the analysis table."""

    file: Path
    result: Optional[AnalysisResult] = None


class AnalyzeView(QWidget):
    """UI for scanning carriers for hidden payloads."""

    operationFinished = pyqtSignal(OperationResult)

    def __init__(self, analyzer: IAnalyzer, thread_pool: QThreadPool | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._analyzer = analyzer
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._rows: list[AnalyzeRow] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Analyze media for steganography")
        header.setObjectName("viewTitle")
        layout.addWidget(header)

        controls = QHBoxLayout()
        self._file_picker = FilePicker(self, "Select media file")
        controls.addWidget(self._file_picker)
        add_button = QPushButton("Add")
        controls.addWidget(add_button)
        run_button = QPushButton("Scan")
        controls.addWidget(run_button)
        export_button = QPushButton("Export CSV")
        controls.addWidget(export_button)
        layout.addLayout(controls)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["File", "Risk", "Flags"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        details_box = QGroupBox("Details")
        details_layout = QVBoxLayout(details_box)
        self._details_label = QLabel("Select a row to view details")
        self._details_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        details_layout.addWidget(self._details_label)
        layout.addWidget(details_box)
        layout.addStretch(1)

        add_button.clicked.connect(self._add_file)
        run_button.clicked.connect(self._scan_files)
        export_button.clicked.connect(self._export_results)
        self._table.itemSelectionChanged.connect(self._update_details)

    def _add_file(self) -> None:
        file = self._file_picker.path
        if not file:
            return
        self._rows.append(AnalyzeRow(file=file))
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        self._table.setItem(row_idx, 0, QTableWidgetItem(str(file)))
        self._table.setItem(row_idx, 1, QTableWidgetItem("—"))
        self._table.setItem(row_idx, 2, QTableWidgetItem(""))

    def _scan_files(self) -> None:
        for row in self._rows:
            config = WorkerConfig(fn=self._analyzer.scan, args=(row.file, None))
            worker = Worker(config)
            worker.signals.result.connect(lambda result, row=row: self._on_scan_result(row, result))
            worker.signals.error.connect(lambda exc, row=row: self._on_scan_error(row, exc))
            self._thread_pool.start(worker)

    def _on_scan_result(self, row: AnalyzeRow, result: AnalysisResult) -> None:
        row.result = result
        idx = self._rows.index(row)
        self._table.item(idx, 1).setText(str(result.risk_score))
        flags = ", ".join(f"{k}: {v:.2f}" for k, v in result.flags.items())
        self._table.item(idx, 2).setText(flags)
        self.operationFinished.emit(
            OperationResult(
                operation="analyze",
                target=row.file,
                success=True,
                message="Scan completed",
                duration_s=0.0,
                risk_score=result.risk_score,
            )
        )

    def _on_scan_error(self, row: AnalyzeRow, exc: Exception) -> None:
        idx = self._rows.index(row)
        self._table.item(idx, 1).setText("error")
        self._table.item(idx, 2).setText(str(exc))
        self.operationFinished.emit(
            OperationResult(
                operation="analyze",
                target=row.file,
                success=False,
                message=str(exc),
                duration_s=0.0,
            )
        )

    def _update_details(self) -> None:
        selected = self._table.selectedIndexes()
        if not selected:
            return
        row_idx = selected[0].row()
        row = self._rows[row_idx]
        if not row.result:
            self._details_label.setText("Scan pending…")
            return
        metadata = "\n".join(f"{key}: {value}" for key, value in row.result.metadata.items())
        self._details_label.setText(
            f"File: {row.file}\nRisk: {row.result.risk_score}\n{metadata}"
        )

    def _export_results(self) -> None:
        if not self._rows:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", filter="CSV (*.csv)")
        if not path:
            return
        lines = ["file,risk,flags"]
        for row in self._rows:
            flags = ",".join(f"{k}:{v:.2f}" for k, v in (row.result.flags if row.result else {}).items())
            risk = row.result.risk_score if row.result else ""
            lines.append(f"{row.file},{risk},{flags}")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
