"""History view implementation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.types import OperationResult


@dataclass(slots=True)
class HistoryEntry:
    """Represents a recorded operation."""

    timestamp: datetime
    result: OperationResult


class HistoryView(QWidget):
    """Simple history/logs view."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[HistoryEntry] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("History & Logs")
        header.setObjectName("viewTitle")
        layout.addWidget(header)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Time", "Operation", "File", "Success", "Message", "Risk"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        export_button = QPushButton("Export CSV")
        export_button.clicked.connect(self._export_csv)
        layout.addWidget(export_button)
        layout.addStretch(1)

    def add_entry(self, result: OperationResult) -> None:
        entry = HistoryEntry(timestamp=datetime.utcnow(), result=result)
        self._entries.append(entry)
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        self._table.setItem(row_idx, 0, QTableWidgetItem(entry.timestamp.isoformat()))
        self._table.setItem(row_idx, 1, QTableWidgetItem(result.operation))
        self._table.setItem(row_idx, 2, QTableWidgetItem(str(result.target)))
        self._table.setItem(row_idx, 3, QTableWidgetItem("Yes" if result.success else "No"))
        self._table.setItem(row_idx, 4, QTableWidgetItem(result.message))
        self._table.setItem(row_idx, 5, QTableWidgetItem(str(result.risk_score or "")))

    def _export_csv(self) -> None:
        if not self._entries:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export history", filter="CSV (*.csv)")
        if not path:
            return
        lines = ["timestamp,operation,file,success,message,risk"]
        for entry in self._entries:
            result = entry.result
            lines.append(
                f"{entry.timestamp.isoformat()},{result.operation},{result.target},{result.success},{result.message},{result.risk_score or ''}"
            )
        Path(path).write_text("\n".join(lines), encoding="utf-8")
