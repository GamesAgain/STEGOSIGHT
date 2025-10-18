"""Interactive steganalysis workbench tab."""

from __future__ import annotations

import base64
import gzip
import io
import math
import os
import random
import time
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from PIL import Image

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QSizePolicy,
)

from utils.tab_utils import FullTextTabBar


ASCII_PRINTABLE = set(range(32, 127)) | {9, 10, 13}

# Hard limits that keep preview rendering responsive even for large payloads.
MAX_TEXT_PREVIEW = 64 * 1024  # 64 KiB of decoded text
MAX_HEX_PREVIEW = 8 * 1024  # 8 KiB rendered as hex


@dataclass
class HistoryEntry:
    """Represents a workbench operation history entry."""

    description: str
    size: int


class ResponsiveButtonGrid(QWidget):
    """Lay buttons in a responsive grid that adapts to the available width."""

    def __init__(
        self,
        buttons: Iterable[QPushButton],
        parent: Optional[QWidget] = None,
        *,
        max_columns: int = 2,
        minimum_cell_width: int = 180,
        spacing: int = 12,
    ) -> None:
        super().__init__(parent)
        self._buttons = list(buttons)
        self._max_columns = max(1, max_columns)
        self._minimum_cell_width = max(1, minimum_cell_width)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(spacing)
        self._layout.setVerticalSpacing(spacing)
        self._current_columns = 0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._update_layout(force=True)

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._update_layout()

    def _update_layout(self, force: bool = False) -> None:
        available = max(self.width(), self._minimum_cell_width)
        columns = max(1, min(self._max_columns, available // self._minimum_cell_width))
        if not force and columns == self._current_columns:
            return

        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self)

        self._current_columns = columns
        for index, button in enumerate(self._buttons):
            row = index // columns
            column = index % columns
            self._layout.addWidget(button, row, column)

        for column in range(self._max_columns):
            self._layout.setColumnStretch(column, 1 if column < columns else 0)


class WorkbenchTab(QWidget):
    """UI for the *Workbench* functionality.

    The workbench provides a deep manipulation environment that merges
    traditional byte-level transforms with neutralisation tooling commonly
    used during steganalysis.  It keeps the state purely in-memory so users
    can experiment freely and step backwards at any time.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.file_path: Optional[str] = None
        self._data: Optional[bytes] = None
        self._pending_data: Optional[bytes] = None
        self._history: List[bytes] = []
        self._history_entries: List[HistoryEntry] = []
        self._action_buttons: List[QPushButton] = []
        self._init_ui()
        self._update_action_states()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        header_layout = QHBoxLayout()

        self.file_label = QLabel("ยังไม่ได้โหลดไฟล์")
        self.file_label.setObjectName("workbenchFileLabel")
        self.file_label.setFrameShape(QLabel.Panel)
        self.file_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        open_btn = QPushButton("เปิดไฟล์…")
        open_btn.clicked.connect(self._browse_file)

        self.process_btn = QPushButton("เริ่มประมวลผล")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self._activate_pending_data)

        header_layout.addWidget(open_btn, 0)
        header_layout.addWidget(self.process_btn, 0)
        header_layout.addWidget(self.file_label, 1)
        root_layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Horizontal)

        left_container = QWidget()
        left_container.setLayout(self._build_left_column())
        splitter.addWidget(left_container)

        right_container = QWidget()
        right_container.setLayout(self._build_right_column())
        splitter.addWidget(right_container)

        splitter.setStretchFactor(0, 45)
        splitter.setStretchFactor(1, 55)

        root_layout.addWidget(splitter, 1)

    def _register_action_buttons(self, buttons: Iterable[QPushButton]) -> None:
        for button in buttons:
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            button.setMinimumHeight(36)
            if button not in self._action_buttons:
                self._action_buttons.append(button)

    def _update_action_states(self) -> None:
        has_data = self._data is not None
        for button in self._action_buttons:
            button.setEnabled(has_data)

        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(has_data and len(self._history) > 1)
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(has_data)
        if hasattr(self, "refresh_preview_btn"):
            self.refresh_preview_btn.setEnabled(has_data)
        if hasattr(self, "encoding_combo"):
            self.encoding_combo.setEnabled(has_data)
        if hasattr(self, "xor_key_input"):
            self.xor_key_input.setEnabled(has_data)

        if hasattr(self, "process_btn"):
            self.process_btn.setEnabled(self._pending_data is not None)

        if hasattr(self, "quick_export_btn"):
            has_output = bool(getattr(self, "quick_output", None) and self.quick_output.toPlainText().strip())
            self.quick_export_btn.setEnabled(has_output)

    def _build_left_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(16)

        column.addWidget(self._build_file_info_group())
        column.addWidget(self._build_quick_tools_group())
        column.addWidget(self._build_tools_group(), 1)

        column.addStretch(1)
        return column

    def _build_right_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(16)
        column.addWidget(self._build_preview_group(), 2)
        column.addWidget(self._build_quick_output_group(), 1)
        column.addWidget(self._build_history_group(), 1)
        column.addStretch(1)
        return column

    def _build_file_info_group(self) -> QGroupBox:
        group = QGroupBox("ข้อมูลไฟล์")
        layout = QFormLayout(group)
        layout.setSpacing(8)

        self.info_name = QLabel("-")
        self.info_size = QLabel("-")
        self.info_magic = QLabel("-")
        self.info_entropy = QLabel("-")
        self.info_printable = QLabel("-")

        layout.addRow("ชื่อไฟล์", self.info_name)
        layout.addRow("ขนาด", self.info_size)
        layout.addRow("ชนิด (Magic)", self.info_magic)
        layout.addRow("Entropy (4KB)", self.info_entropy)
        layout.addRow("Printable Ratio", self.info_printable)
        return group

    def _build_quick_tools_group(self) -> QGroupBox:
        group = QGroupBox("เครื่องมือสืบสวนอย่างรวดเร็ว")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        info = QLabel("เลือกเครื่องมือเพื่อสำรวจโครงสร้างไฟล์แบบรวดเร็ว")
        info.setWordWrap(True)
        layout.addWidget(info)

        tools: List[Tuple[str, str]] = [
            ("🔢 Hex Viewer", "hex"),
            ("📊 Byte Frequency", "byte"),
            ("📈 Entropy Overview", "entropy"),
            ("🔤 String Extractor", "strings"),
            ("🔄 Data Transformer", "transform"),
            ("📋 Metadata Inspector", "metadata"),
        ]

        self.quick_tool_buttons: List[QPushButton] = []
        for label, key in tools:
            button = QPushButton(label)
            button.clicked.connect(lambda _, tool=key: self._run_quick_tool(tool))
            self._register_action_buttons([button])
            self.quick_tool_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)
        return group

    def _build_tools_group(self) -> QGroupBox:
        group = QGroupBox("เครื่องมือและการแปลงข้อมูล")
        outer_layout = QVBoxLayout(group)
        outer_layout.setSpacing(12)

        self.tool_tabs = QTabWidget()
        self.tool_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tool_tabs.setTabBar(FullTextTabBar(minimum_width=150, extra_padding=56))
        self.tool_tabs.setUsesScrollButtons(True)
        self.tool_tabs.addTab(self._build_encoding_tab(), "Encoding")
        self.tool_tabs.addTab(self._build_compression_tab(), "Compression")
        self.tool_tabs.addTab(self._build_crypto_tab(), "Cryptography")
        self.tool_tabs.addTab(self._build_neutralize_tab(), "Neutralize")
        self._apply_tab_tooltips(self.tool_tabs)

        outer_layout.addWidget(self.tool_tabs, 1)

        action_row = QHBoxLayout()
        self.undo_btn = QPushButton("ย้อนกลับ")
        self.undo_btn.clicked.connect(self._undo)
        self.save_btn = QPushButton("บันทึกผลลัพธ์…")
        self.save_btn.clicked.connect(self._save_output)
        self._register_action_buttons([self.undo_btn, self.save_btn])
        action_row.addWidget(self.undo_btn)
        action_row.addWidget(self.save_btn)
        action_row.addStretch()
        outer_layout.addLayout(action_row)

        return group

    def _apply_tab_tooltips(self, tab_widget: QTabWidget) -> None:
        """Expose the full text of each tab via tooltips."""

        for index in range(tab_widget.count()):
            label = tab_widget.tabText(index).strip()
            tab_widget.setTabToolTip(index, label)

    def _build_history_group(self) -> QGroupBox:
        group = QGroupBox("ประวัติการทำงาน")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.history_list = QListWidget()
        self.history_list.setObjectName("workbenchHistoryList")
        self.history_list.setAlternatingRowColors(True)
        self.history_list.setMinimumHeight(140)
        layout.addWidget(self.history_list)

        return group

    def _build_preview_group(self) -> QGroupBox:
        group = QGroupBox("มุมมองข้อมูล")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Text Encoding:"))
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["utf-8", "latin-1", "ascii", "utf-16", "cp1252"])
        self.encoding_combo.currentTextChanged.connect(self._update_preview_text)
        controls.addWidget(self.encoding_combo)

        self.refresh_preview_btn = QPushButton("รีเฟรชมุมมอง")
        self.refresh_preview_btn.clicked.connect(self._update_preview)
        self._register_action_buttons([self.refresh_preview_btn])
        controls.addWidget(self.refresh_preview_btn)
        controls.addStretch()

        layout.addLayout(controls)

        self.preview_tabs = QTabWidget()
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setLineWrapMode(QTextEdit.WidgetWidth)

        self.preview_hex = QTextEdit()
        self.preview_hex.setReadOnly(True)
        self.preview_hex.setLineWrapMode(QTextEdit.NoWrap)
        self.preview_hex.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 11px;")

        self.preview_image = QLabel("ยังไม่มีตัวอย่างภาพ")
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setWordWrap(True)
        self.preview_image.setMargin(16)
        self.preview_image.setMinimumSize(320, 240)
        self.preview_image.setObjectName("previewArea")

        self.preview_tabs.addTab(self.preview_text, "Text")
        self.preview_tabs.addTab(self.preview_hex, "Hex")
        self.preview_tabs.addTab(self.preview_image, "Image")
        layout.addWidget(self.preview_tabs, 1)
        return group

    def _build_quick_output_group(self) -> QGroupBox:
        group = QGroupBox("ผลลัพธ์เครื่องมือสืบสวน")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.quick_output = QTextEdit()
        self.quick_output.setReadOnly(True)
        self.quick_output.setPlaceholderText("เลือกเครื่องมือเพื่อดูผลลัพธ์ที่นี่…")
        self.quick_output.setStyleSheet(
            "font-family: 'JetBrains Mono', monospace; font-size: 11px;"
        )
        layout.addWidget(self.quick_output)

        self.quick_export_btn = QPushButton("💾 Export Results")
        self.quick_export_btn.clicked.connect(self._export_quick_output)
        self.quick_export_btn.setEnabled(False)
        layout.addWidget(self.quick_export_btn, alignment=Qt.AlignRight)

        return group

    def _build_encoding_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        info = QLabel("ใช้การเข้ารหัส/ถอดรหัสที่พบบ่อยเพื่อตรวจสอบ payload")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.base64_decode_btn = QPushButton("Base64 Decode")
        self.base64_decode_btn.clicked.connect(lambda: self._apply_transform("Base64 Decode"))
        self.base64_encode_btn = QPushButton("Base64 Encode")
        self.base64_encode_btn.clicked.connect(lambda: self._apply_transform("Base64 Encode"))
        self.hex_decode_btn = QPushButton("Hex Decode")
        self.hex_decode_btn.clicked.connect(lambda: self._apply_transform("Hex Decode"))
        self.hex_encode_btn = QPushButton("Hex Encode")
        self.hex_encode_btn.clicked.connect(lambda: self._apply_transform("Hex Encode"))
        self._register_action_buttons(
            [
                self.base64_decode_btn,
                self.base64_encode_btn,
                self.hex_decode_btn,
                self.hex_encode_btn,
            ]
        )

        button_grid = ResponsiveButtonGrid(
            [
                self.base64_decode_btn,
                self.base64_encode_btn,
                self.hex_decode_btn,
                self.hex_encode_btn,
            ],
            max_columns=2,
            minimum_cell_width=180,
        )
        layout.addWidget(button_grid)

        layout.addStretch(1)
        return widget

    def _build_compression_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        info = QLabel("ทดสอบการบีบอัดเพื่อคลายข้อมูลที่อาจถูกฝัง")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.zlib_decomp_btn = QPushButton("Zlib Decompress")
        self.zlib_decomp_btn.clicked.connect(lambda: self._apply_transform("Zlib Decompress"))
        self.zlib_comp_btn = QPushButton("Zlib Compress")
        self.zlib_comp_btn.clicked.connect(lambda: self._apply_transform("Zlib Compress"))
        self.gzip_decomp_btn = QPushButton("Gzip Decompress")
        self.gzip_decomp_btn.clicked.connect(lambda: self._apply_transform("Gzip Decompress"))
        self.gzip_comp_btn = QPushButton("Gzip Compress")
        self.gzip_comp_btn.clicked.connect(lambda: self._apply_transform("Gzip Compress"))
        self._register_action_buttons(
            [
                self.zlib_decomp_btn,
                self.zlib_comp_btn,
                self.gzip_decomp_btn,
                self.gzip_comp_btn,
            ]
        )

        button_grid = ResponsiveButtonGrid(
            [
                self.zlib_decomp_btn,
                self.zlib_comp_btn,
                self.gzip_decomp_btn,
                self.gzip_comp_btn,
            ],
            max_columns=2,
            minimum_cell_width=180,
        )
        layout.addWidget(button_grid)

        layout.addStretch(1)
        return widget

    def _build_crypto_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        info = QLabel("ใช้ XOR key เพื่อถอดรหัสหรือเข้ารหัสข้อมูลที่สงสัย")
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.xor_key_input = QLineEdit()
        self.xor_key_input.setPlaceholderText("Key (เช่น secret, 0x41AA, 41 aa bb)")
        self.xor_apply_btn = QPushButton("Apply XOR")
        self.xor_apply_btn.clicked.connect(self._apply_xor)
        self._register_action_buttons([self.xor_apply_btn])
        row.addWidget(self.xor_key_input, 2)
        row.addWidget(self.xor_apply_btn, 1)
        layout.addLayout(row)

        layout.addStretch(1)
        return widget

    def _build_neutralize_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        info = QLabel("ทำให้ไฟล์เป็นกลางเพื่อลบร่องรอยการฝังข้อมูล")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.recompress_btn = QPushButton("Re-compress Image")
        self.recompress_btn.clicked.connect(self._recompress_image)
        self.strip_metadata_btn = QPushButton("Strip All Metadata")
        self.strip_metadata_btn.clicked.connect(self._strip_metadata)
        self.noise_btn = QPushButton("Apply Noise Filter")
        self.noise_btn.clicked.connect(self._apply_noise)
        self._register_action_buttons(
            [self.recompress_btn, self.strip_metadata_btn, self.noise_btn]
        )

        layout.addWidget(self.recompress_btn)
        layout.addWidget(self.strip_metadata_btn)
        layout.addWidget(self.noise_btn)
        layout.addStretch(1)
        return widget

    # ------------------------------------------------------------------
    # File operations & state management
    # ------------------------------------------------------------------
    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์", "", "All Files (*.*)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str) -> None:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except Exception as exc:  # pragma: no cover - GUI message
            QMessageBox.critical(self, "Workbench", f"ไม่สามารถเปิดไฟล์ได้:\n{exc}")
            return

        self.file_path = path
        self._pending_data = data
        self._data = None
        self._history = []
        self._history_entries = []
        self.history_list.clear()
        self.file_label.setText(f"{path} (รอประมวลผล)")
        self._update_file_info()
        self._update_preview()
        self._clear_quick_output()
        self._update_action_states()

    def _activate_pending_data(self) -> None:
        if self._pending_data is None:
            QMessageBox.information(self, "Workbench", "ไม่มีไฟล์ค้างอยู่ให้ประมวลผล")
            return

        data = self._pending_data
        self._pending_data = None
        self._data = data
        description = f"Loaded: {os.path.basename(self.file_path)}" if self.file_path else "Loaded"
        self._history = [data]
        self._history_entries = [HistoryEntry(description, len(data))]
        self._refresh_history()
        if self.file_path:
            self.file_label.setText(self.file_path)
        else:
            self.file_label.setText("(memory)")
        self._update_file_info()
        self._update_preview()
        self._clear_quick_output()
        self._update_action_states()

    def _set_data(self, data: bytes, description: str) -> None:
        self._data = data
        self._history.append(data)
        self._history_entries.append(HistoryEntry(description, len(data)))
        self._refresh_history()
        self._update_file_info()
        self._update_preview()
        self._clear_quick_output()
        self._update_action_states()

    def _undo(self) -> None:
        if len(self._history) <= 1:
            QMessageBox.information(self, "Workbench", "ไม่มีขั้นตอนก่อนหน้าให้ย้อนกลับ")
            return

        self._history.pop()
        self._history_entries.pop()
        self._data = self._history[-1]
        self._refresh_history()
        self._update_file_info()
        self._update_preview()
        self._clear_quick_output()
        self._update_action_states()

    def _save_output(self) -> None:
        if self._data is None:
            QMessageBox.information(self, "Workbench", "ยังไม่มีข้อมูลให้บันทึก")
            return

        path, _ = QFileDialog.getSaveFileName(self, "บันทึกไฟล์", "output.bin", "All Files (*.*)")
        if not path:
            return
        try:
            with open(path, "wb") as fh:
                fh.write(self._data)
        except Exception as exc:  # pragma: no cover - GUI message
            QMessageBox.critical(self, "Workbench", f"ไม่สามารถบันทึกไฟล์ได้:\n{exc}")
        else:
            QMessageBox.information(self, "Workbench", f"บันทึกผลลัพธ์สำเร็จ:\n{path}")

    # ------------------------------------------------------------------
    # History rendering
    # ------------------------------------------------------------------
    def _refresh_history(self) -> None:
        self.history_list.clear()
        for idx, entry in enumerate(self._history_entries, start=1):
            item = QListWidgetItem(f"{idx:02d}. {entry.description} → {entry.size} bytes")
            self.history_list.addItem(item)
        if self.history_list.count():
            self.history_list.setCurrentRow(self.history_list.count() - 1)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def _update_preview(self) -> None:
        self._update_preview_text()
        self._update_preview_hex()
        self._update_preview_image()

    def _update_preview_text(self) -> None:
        if self._data is None:
            if self._pending_data is not None:
                self.preview_text.setPlainText("รอเริ่มประมวลผล…")
            else:
                self.preview_text.setPlainText("(no data)")
            return
        encoding = self.encoding_combo.currentText() or "utf-8"
        try:
            snippet = self._data[:MAX_TEXT_PREVIEW]
            text = snippet.decode(encoding, errors="replace")
        except Exception:
            text = "(unable to decode with selected encoding)"
        else:
            if len(self._data) > MAX_TEXT_PREVIEW:
                text += (
                    "\n\n… Preview truncated to "
                    f"{MAX_TEXT_PREVIEW:,} bytes of {len(self._data):,}."
                )
        self.preview_text.setPlainText(text)

    def _update_preview_hex(self) -> None:
        if self._data is None:
            if self._pending_data is not None:
                self.preview_hex.setPlainText("(รอเริ่มประมวลผล)")
            else:
                self.preview_hex.setPlainText("(no data)")
            return
        self.preview_hex.setPlainText(
            self._hexdump(self._data, limit=MAX_HEX_PREVIEW)
        )

    def _update_preview_image(self) -> None:
        self.preview_image.setPixmap(QPixmap())

        if self._data is None:
            if self._pending_data is not None:
                self.preview_image.setText("🕒 กำลังเตรียมข้อมูล\nเริ่มประมวลผลเพื่อดูตัวอย่างภาพ")
            else:
                self.preview_image.setText("ยังไม่มีตัวอย่างภาพ\nนำเข้าข้อมูลเพื่อดูตัวอย่างที่นี่")
            return

        pixmap = QPixmap()
        if pixmap.loadFromData(self._data):
            scaled = pixmap.scaled(
                self.preview_image.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.preview_image.setPixmap(scaled)
            self.preview_image.setText("")
            self.preview_tabs.setCurrentWidget(self.preview_image)
        else:
            self.preview_image.setText(
                "⚠️ ไม่สามารถแสดงผลเป็นภาพได้\nรองรับเฉพาะข้อมูลไฟล์ภาพ เช่น PNG หรือ JPEG"
            )

    # ------------------------------------------------------------------
    # Quick tool helpers
    # ------------------------------------------------------------------
    def _clear_quick_output(self) -> None:
        if hasattr(self, "quick_output"):
            self.quick_output.clear()
        if hasattr(self, "quick_export_btn"):
            self.quick_export_btn.setEnabled(False)

    def _export_quick_output(self) -> None:
        if not hasattr(self, "quick_output"):
            return
        text = self.quick_output.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "Workbench", "ไม่มีผลลัพธ์ให้บันทึก")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "บันทึกผลการวิเคราะห์",
            "analysis_report.txt",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI message
            QMessageBox.critical(self, "Workbench", f"ไม่สามารถบันทึกผลลัพธ์ได้:\n{exc}")
        else:
            QMessageBox.information(self, "Workbench", f"บันทึกผลลัพธ์สำเร็จ:\n{path}")

    def _run_quick_tool(self, tool: str) -> None:
        if self._data is None:
            if self._pending_data is not None:
                QMessageBox.warning(self, "Workbench", "กด 'เริ่มประมวลผล' ก่อนใช้เครื่องมือ")
            else:
                QMessageBox.information(self, "Workbench", "ยังไม่มีข้อมูลสำหรับวิเคราะห์")
            return

        handlers: Dict[str, Tuple[str, Callable[[], str]]] = {
            "hex": ("HEX VIEWER", self._quick_hex_viewer),
            "byte": ("BYTE FREQUENCY", self._quick_byte_frequency),
            "entropy": ("ENTROPY OVERVIEW", self._quick_entropy_overview),
            "strings": ("STRING EXTRACTOR", self._quick_strings),
            "transform": ("DATA TRANSFORMER", self._quick_transformer),
            "metadata": ("METADATA INSPECTOR", self._quick_metadata),
        }

        title_func = handlers.get(tool)
        if not title_func:
            return

        title, func = title_func
        try:
            body = func()
        except Exception as exc:  # pragma: no cover - GUI message
            QMessageBox.critical(self, "Workbench", f"เกิดข้อผิดพลาดในการวิเคราะห์:\n{exc}")
            return

        self._display_quick_output(title, body)

    def _display_quick_output(self, title: str, body: str) -> None:
        if not hasattr(self, "quick_output"):
            return
        text = f"=== {title} ===\n\n{body.strip()}"
        self.quick_output.setPlainText(text)
        if hasattr(self, "quick_export_btn"):
            self.quick_export_btn.setEnabled(True)

    def _quick_hex_viewer(self) -> str:
        data = self._data or b""
        sample = data[:1024]
        lines = ["Offset    Hex                                             ASCII", "-" * 80]
        for offset in range(0, len(sample), 16):
            chunk = sample[offset : offset + 16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{offset:08X}  {hex_part:<48}  {ascii_part}")

        lines.append("")
        lines.append(f"Total bytes shown: {len(sample)}")
        lines.append(f"Payload size: {len(data)} bytes")
        return "\n".join(lines)

    def _quick_byte_frequency(self) -> str:
        data = self._data or b""
        total = len(data)
        if not total:
            return "ไม่มีข้อมูล"

        counter = Counter(data)
        most_common = counter.most_common(20)
        max_count = most_common[0][1] if most_common else 1

        lines = [f"Total bytes: {total}"]
        lines.append(f"Unique bytes: {len(counter)}")
        lines.append("")
        lines.append("Byte  Hex   Count    Percentage  Bar")
        lines.append("-" * 60)
        for byte, count in most_common:
            pct = (count / total) * 100
            bar = "█" * max(1, int((count / max_count) * 30))
            char = chr(byte) if 32 <= byte < 127 else "."
            lines.append(f"{char:3}   {byte:02X}    {count:6}   {pct:6.2f}%    {bar}")
        if len(counter) > 20:
            lines.append("")
            lines.append(f"… {len(counter) - 20} additional byte values omitted")
        return "\n".join(lines)

    def _quick_entropy_overview(self) -> str:
        data = self._data or b""
        if not data:
            return "ไม่มีข้อมูล"

        entropy = self._shannon_entropy(data)
        pct = (entropy / 8) * 100
        lines = [f"Entropy: {entropy:.6f} bits/byte ({pct:.2f}% of max)"]
        if entropy < 1.0:
            lines.append("• Very low entropy - highly structured data")
        elif entropy < 3.0:
            lines.append("• Low entropy - structured data with patterns")
        elif entropy < 5.0:
            lines.append("• Medium entropy - mixed data")
        elif entropy < 7.0:
            lines.append("• High entropy - compressed or encrypted likely")
        else:
            lines.append("• Very high entropy - encrypted/random data suspected")

        sections = 4
        chunk_size = max(1, len(data) // sections)
        lines.append("")
        lines.append("Section entropy estimates:")
        for idx in range(sections):
            chunk = data[idx * chunk_size : (idx + 1) * chunk_size]
            if not chunk:
                continue
            lines.append(f"  Section {idx + 1}: {self._shannon_entropy(chunk):.3f} bits/byte")

        if entropy > 7.5:
            lines.append("")
            lines.append("⚠️  Warning: Very high entropy detected (possible encrypted payload)")
        return "\n".join(lines)

    def _quick_strings(self) -> str:
        data = self._data or b""
        if not data:
            return "ไม่มีข้อมูล"

        strings: List[str] = []
        current: List[str] = []
        for byte in data:
            if 32 <= byte < 127:
                current.append(chr(byte))
            else:
                if len(current) >= 4:
                    strings.append("".join(current))
                current = []
        if len(current) >= 4:
            strings.append("".join(current))

        lines = [f"Strings found: {len(strings)} (min length 4)"]
        lines.append("-")
        for index, value in enumerate(strings[:100], start=1):
            lines.append(f"{index:4}. {value[:76]}")
        if len(strings) > 100:
            lines.append("")
            lines.append(f"… and {len(strings) - 100} more strings")
        return "\n".join(lines)

    def _quick_transformer(self) -> str:
        data = self._data or b""
        head = data[:256]
        lines = [f"Previewing first {len(head)} bytes"]

        if head:
            b64 = base64.b64encode(head).decode("ascii")
            lines.append("")
            lines.append("--- BASE64 ---")
            for i in range(0, len(b64), 64):
                lines.append(b64[i : i + 64])

            hex_str = head.hex()
            lines.append("")
            lines.append("--- HEX ---")
            for i in range(0, len(hex_str), 64):
                lines.append(hex_str[i : i + 64])

            lines.append("")
            lines.append("--- BINARY (first 64 bytes) ---")
            for i in range(0, min(64, len(head)), 8):
                chunk = head[i : i + 8]
                lines.append(" ".join(f"{b:08b}" for b in chunk))

            lines.append("")
            lines.append("--- XOR Analysis (first 32 bytes) ---")
            for key in (0x00, 0xFF, 0xAA, 0x55, 0x42):
                xored = bytes(b ^ key for b in head[:32])
                lines.append(f"XOR 0x{key:02X}: {xored.hex()[:64]}…")
        else:
            lines.append("ไม่มีข้อมูลสำหรับการแปลง")

        return "\n".join(lines)

    def _quick_metadata(self) -> str:
        data = self._data or b""
        lines: List[str] = []
        if self.file_path:
            path = Path(self.file_path)
            try:
                stat = path.stat()
            except OSError:
                stat = None
            lines.append(f"File: {path.name}")
            lines.append(f"Location: {path}")
            if stat is not None:
                lines.append(f"Size: {stat.st_size:,} bytes")
                lines.append(f"Created: {time.ctime(stat.st_ctime)}")
                lines.append(f"Modified: {time.ctime(stat.st_mtime)}")
                lines.append(f"Accessed: {time.ctime(stat.st_atime)}")
        else:
            lines.append("File: (in-memory)")
            lines.append(f"Size: {len(data):,} bytes")

        lines.append("")
        lines.append("Magic bytes: " + data[:16].hex())
        lines.append("Detected type: " + self._detect_magic(data))

        if self.file_path and Path(self.file_path).suffix.lower() in {".png", ".jpg", ".jpeg", ".tiff"}:
            try:
                img = Image.open(io.BytesIO(data))
            except Exception:
                lines.append("")
                lines.append("Image metadata: ไม่สามารถอ่านไฟล์ภาพได้")
            else:
                lines.append("")
                lines.append("Image metadata:")
                lines.append(f"  Format: {img.format}")
                lines.append(f"  Mode: {img.mode}")
                lines.append(f"  Size: {img.size[0]} x {img.size[1]}")
                if hasattr(img, "_getexif") and img._getexif():
                    lines.append("  EXIF entries available")
                else:
                    lines.append("  No EXIF data detected")

        lines.append("")
        lines.append("Suspicious indicators:")
        eof_markers = {
            b"\xFF\xD9": "JPEG EOI",
            b"IEND\xAE\x42\x60\x82": "PNG IEND",
        }
        for marker, name in eof_markers.items():
            pos = data.rfind(marker)
            if pos != -1 and pos + len(marker) < len(data):
                trailing = len(data) - (pos + len(marker))
                lines.append(f"  ⚠️  {trailing} bytes after {name} marker (possible append)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # File info helpers
    # ------------------------------------------------------------------
    def _update_file_info(self) -> None:
        if self._data is None:
            if self._pending_data is not None:
                name = os.path.basename(self.file_path) if self.file_path else "(memory)"
                self.info_name.setText(name)
                self.info_size.setText(f"{len(self._pending_data):,} bytes (pending)")
            else:
                self.info_name.setText("-")
                self.info_size.setText("-")
            self.info_magic.setText("-")
            self.info_entropy.setText("-")
            self.info_printable.setText("-")
            return

        name = os.path.basename(self.file_path) if self.file_path else "(memory)"
        self.info_name.setText(name)
        self.info_size.setText(f"{len(self._data):,} bytes")
        self.info_magic.setText(self._detect_magic(self._data))
        self.info_entropy.setText(f"{self._shannon_entropy(self._data[:4096]):.3f}")
        self.info_printable.setText(f"{self._printable_ratio(self._data):.2%}")

    # ------------------------------------------------------------------
    # Transformations
    # ------------------------------------------------------------------
    def _apply_transform(self, action: str) -> None:
        if self._data is None:
            QMessageBox.information(self, "Workbench", "โปรดโหลดไฟล์ก่อน")
            return

        transform_map: dict[str, Callable[[bytes], bytes]] = {
            "Base64 Decode": base64.b64decode,
            "Base64 Encode": base64.b64encode,
            "Hex Decode": self._hex_decode,
            "Hex Encode": self._hex_encode,
            "Zlib Decompress": zlib.decompress,
            "Zlib Compress": zlib.compress,
            "Gzip Decompress": gzip.decompress,
            "Gzip Compress": gzip.compress,
        }

        func = transform_map.get(action)
        if func is None:
            return
        try:
            new_data = func(self._data)
        except Exception as exc:  # pragma: no cover - GUI message path
            QMessageBox.critical(self, "Workbench", f"{action} ล้มเหลว:\n{exc}")
            return

        self._set_data(new_data, action)

    def _apply_xor(self) -> None:
        if self._data is None:
            QMessageBox.information(self, "Workbench", "โปรดโหลดไฟล์ก่อน")
            return

        key_text = self.xor_key_input.text().strip()
        if not key_text:
            QMessageBox.information(self, "Workbench", "กรุณาระบุ XOR key")
            return

        try:
            key = self._parse_xor_key(key_text)
        except ValueError as exc:
            QMessageBox.critical(self, "Workbench", str(exc))
            return
        if not key:
            QMessageBox.information(self, "Workbench", "XOR key ว่างเปล่า")
            return

        new_data = bytes(b ^ key[i % len(key)] for i, b in enumerate(self._data))
        self._set_data(new_data, f"XOR [{key_text}]")

    # ------------------------------------------------------------------
    # Neutralisation operations
    # ------------------------------------------------------------------
    def _ensure_image(self) -> Optional[Image.Image]:
        if self._data is None:
            QMessageBox.information(self, "Workbench", "ยังไม่มีข้อมูล")
            return None
        try:
            img = Image.open(io.BytesIO(self._data))
            img.load()
            return img
        except Exception:
            QMessageBox.information(self, "Workbench", "ข้อมูลปัจจุบันไม่ใช่ไฟล์ภาพที่รองรับ")
            return None

    def _recompress_image(self) -> None:
        img = self._ensure_image()
        if img is None:
            return

        buffer = io.BytesIO()
        format_hint = img.format or "PNG"
        save_kwargs = {}
        if format_hint.upper() == "JPEG":
            save_kwargs.update({"quality": 85, "optimize": True})
        elif format_hint.upper() == "PNG":
            save_kwargs.update({"optimize": True})

        img.save(buffer, format=format_hint, **save_kwargs)
        self._set_data(buffer.getvalue(), f"Re-compress ({format_hint.upper()})")

    def _strip_metadata(self) -> None:
        img = self._ensure_image()
        if img is None:
            return

        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        buffer = io.BytesIO()
        format_hint = img.format or "PNG"
        if format_hint.upper() == "JPEG":
            clean.save(buffer, format=format_hint, quality=90, optimize=True, exif=b"")
        else:
            clean.save(buffer, format=format_hint)
        self._set_data(buffer.getvalue(), "Strip Metadata")

    def _apply_noise(self) -> None:
        img = self._ensure_image()
        if img is None:
            return

        working = img.convert("RGBA")
        pixels = bytearray(working.tobytes())
        intensity = max(1, min(10, int((working.size[0] * working.size[1]) ** 0.5 // 3)))
        for idx in range(0, len(pixels), 4):
            for channel in range(3):
                offset = random.randint(-intensity, intensity)
                val = pixels[idx + channel] + offset
                pixels[idx + channel] = max(0, min(255, val))
        noisy = Image.frombytes(working.mode, working.size, bytes(pixels))
        buffer = io.BytesIO()
        format_hint = img.format or "PNG"
        if format_hint.upper() == "JPEG":
            noisy = noisy.convert("RGB")
            noisy.save(buffer, format=format_hint, quality=85, optimize=True)
        else:
            noisy.save(buffer, format=format_hint)
        self._set_data(buffer.getvalue(), "Apply Noise Filter")

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _hexdump(data: bytes, width: int = 16, limit: Optional[int] = None) -> str:
        total = len(data)
        truncated = False
        if limit is not None and total > limit:
            data = data[:limit]
            truncated = True

        lines: List[str] = []
        for offset in range(0, len(data), width):
            chunk = data[offset : offset + width]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            text_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"{offset:08X}  {hex_part:<{width * 3}}  {text_part}")

        if truncated:
            lines.append("")
            lines.append(
                "… Preview truncated to "
                f"{limit:,} bytes of {total:,}."
            )
        return "\n".join(lines)

    @staticmethod
    def _parse_xor_key(value: str) -> bytes:
        value = value.strip()
        if not value:
            return b""
        if value.startswith("0x"):
            hex_part = value[2:]
            if len(hex_part) % 2:
                hex_part = "0" + hex_part
            try:
                return bytes.fromhex(hex_part)
            except ValueError as exc:
                raise ValueError("รูปแบบ hex ไม่ถูกต้อง") from exc
        if all(ch in "0123456789abcdefABCDEF " for ch in value) and " " in value:
            try:
                return bytes.fromhex(value)
            except ValueError as exc:
                raise ValueError("รูปแบบ hex ไม่ถูกต้อง") from exc
        return value.encode("utf-8")

    @staticmethod
    def _hex_decode(data: bytes) -> bytes:
        # Accept whitespace in textual hex payloads
        try:
            text = data.decode("ascii")
        except Exception as exc:
            raise ValueError("ข้อมูลไม่อยู่ในรูปแบบ ASCII hex") from exc
        cleaned = "".join(text.split())
        if len(cleaned) % 2:
            cleaned = "0" + cleaned
        return bytes.fromhex(cleaned)

    @staticmethod
    def _hex_encode(data: bytes) -> bytes:
        return data.hex().encode("ascii")

    @staticmethod
    def _detect_magic(data: bytes) -> str:
        signatures: List[Tuple[bytes, str]] = [
            (b"\x89PNG\r\n\x1a\n", "PNG"),
            (b"\xFF\xD8\xFF", "JPEG"),
            (b"GIF8", "GIF"),
            (b"BM", "BMP"),
            (b"PK\x03\x04", "ZIP"),
            (b"%PDF", "PDF"),
            (b"ID3", "MP3"),
            (b"OggS", "OGG"),
            (b"ftyp", "MP4/QuickTime"),
            (b"RIFF", "RIFF (ตรวจสอบเพิ่มเติม)"),
        ]
        head = data[:16]
        for sig, label in signatures:
            if head.startswith(sig):
                return label
        return "Unknown"

    @staticmethod
    def _shannon_entropy(data: bytes) -> float:
        if not data:
            return 0.0
        counter = Counter(data)
        total = len(data)
        entropy = 0.0
        for count in counter.values():
            prob = count / total
            entropy -= prob * math.log2(prob)
        return entropy

    @staticmethod
    def _printable_ratio(data: bytes, sample: int = 256) -> float:
        if not data:
            return 0.0
        subset = data[:sample]
        return sum(b in ASCII_PRINTABLE for b in subset) / len(subset)


__all__ = ["WorkbenchTab"]

