"""Interactive steganalysis workbench tab."""

from __future__ import annotations

import base64
import gzip
import io
import math
import os
import random
import zlib
from collections import Counter
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from PIL import Image

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
)


ASCII_PRINTABLE = set(range(32, 127)) | {9, 10, 13}


@dataclass
class HistoryEntry:
    """Represents a workbench operation history entry."""

    description: str
    size: int


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
        self._history: List[bytes] = []
        self._history_entries: List[HistoryEntry] = []
        self._init_ui()

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

        header_layout.addWidget(open_btn, 0)
        header_layout.addWidget(self.file_label, 1)
        root_layout.addLayout(header_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        content_layout.addLayout(self._build_left_column(), 4)
        content_layout.addLayout(self._build_right_column(), 6)
        root_layout.addLayout(content_layout, 1)

    def _build_left_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(16)

        column.addWidget(self._build_file_info_group())
        column.addWidget(self._build_tools_group(), 1)
        column.addWidget(self._build_history_group(), 1)

        column.addStretch(1)
        return column

    def _build_right_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(16)
        column.addWidget(self._build_preview_group(), 1)
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

    def _build_tools_group(self) -> QGroupBox:
        group = QGroupBox("เครื่องมือและการแปลงข้อมูล")
        outer_layout = QVBoxLayout(group)
        outer_layout.setSpacing(12)

        self.tool_tabs = QTabWidget()
        self.tool_tabs.addTab(self._build_encoding_tab(), "Encoding")
        self.tool_tabs.addTab(self._build_compression_tab(), "Compression")
        self.tool_tabs.addTab(self._build_crypto_tab(), "Cryptography")
        self.tool_tabs.addTab(self._build_neutralize_tab(), "Neutralize")

        outer_layout.addWidget(self.tool_tabs)

        action_row = QHBoxLayout()
        self.undo_btn = QPushButton("ย้อนกลับ")
        self.undo_btn.clicked.connect(self._undo)
        self.save_btn = QPushButton("บันทึกผลลัพธ์…")
        self.save_btn.clicked.connect(self._save_output)
        action_row.addWidget(self.undo_btn)
        action_row.addWidget(self.save_btn)
        action_row.addStretch()
        outer_layout.addLayout(action_row)

        return group

    def _build_history_group(self) -> QGroupBox:
        group = QGroupBox("ประวัติการทำงาน")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.history_list = QListWidget()
        self.history_list.setObjectName("workbenchHistoryList")
        self.history_list.setAlternatingRowColors(True)
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

        self.preview_image = QLabel("ไม่มีตัวอย่างภาพ")
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setMinimumSize(320, 240)
        self.preview_image.setStyleSheet(
            "background-color: #111827; color: #cbd5f5; border: 1px dashed #374151;"
        )

        self.preview_tabs.addTab(self.preview_text, "Text")
        self.preview_tabs.addTab(self.preview_hex, "Hex")
        self.preview_tabs.addTab(self.preview_image, "Image")
        layout.addWidget(self.preview_tabs, 1)
        return group

    def _build_encoding_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        info = QLabel("ใช้การเข้ารหัส/ถอดรหัสที่พบบ่อยเพื่อตรวจสอบ payload")
        info.setWordWrap(True)
        layout.addWidget(info)

        row1 = QHBoxLayout()
        self.base64_decode_btn = QPushButton("Base64 Decode")
        self.base64_decode_btn.clicked.connect(lambda: self._apply_transform("Base64 Decode"))
        self.base64_encode_btn = QPushButton("Base64 Encode")
        self.base64_encode_btn.clicked.connect(lambda: self._apply_transform("Base64 Encode"))
        row1.addWidget(self.base64_decode_btn)
        row1.addWidget(self.base64_encode_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.hex_decode_btn = QPushButton("Hex Decode")
        self.hex_decode_btn.clicked.connect(lambda: self._apply_transform("Hex Decode"))
        self.hex_encode_btn = QPushButton("Hex Encode")
        self.hex_encode_btn.clicked.connect(lambda: self._apply_transform("Hex Encode"))
        row2.addWidget(self.hex_decode_btn)
        row2.addWidget(self.hex_encode_btn)
        layout.addLayout(row2)

        layout.addStretch(1)
        return widget

    def _build_compression_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        info = QLabel("ทดสอบการบีบอัดเพื่อคลายข้อมูลที่อาจถูกฝัง")
        info.setWordWrap(True)
        layout.addWidget(info)

        row1 = QHBoxLayout()
        self.zlib_decomp_btn = QPushButton("Zlib Decompress")
        self.zlib_decomp_btn.clicked.connect(lambda: self._apply_transform("Zlib Decompress"))
        self.zlib_comp_btn = QPushButton("Zlib Compress")
        self.zlib_comp_btn.clicked.connect(lambda: self._apply_transform("Zlib Compress"))
        row1.addWidget(self.zlib_decomp_btn)
        row1.addWidget(self.zlib_comp_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.gzip_decomp_btn = QPushButton("Gzip Decompress")
        self.gzip_decomp_btn.clicked.connect(lambda: self._apply_transform("Gzip Decompress"))
        self.gzip_comp_btn = QPushButton("Gzip Compress")
        self.gzip_comp_btn.clicked.connect(lambda: self._apply_transform("Gzip Compress"))
        row2.addWidget(self.gzip_decomp_btn)
        row2.addWidget(self.gzip_comp_btn)
        layout.addLayout(row2)

        layout.addStretch(1)
        return widget

    def _build_crypto_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        info = QLabel("ใช้ XOR key เพื่อถอดรหัสหรือเข้ารหัสข้อมูลที่สงสัย")
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        self.xor_key_input = QLineEdit()
        self.xor_key_input.setPlaceholderText("Key (เช่น secret, 0x41AA, 41 aa bb)")
        self.xor_apply_btn = QPushButton("Apply XOR")
        self.xor_apply_btn.clicked.connect(self._apply_xor)
        row.addWidget(self.xor_key_input, 2)
        row.addWidget(self.xor_apply_btn, 1)
        layout.addLayout(row)

        layout.addStretch(1)
        return widget

    def _build_neutralize_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        info = QLabel("ทำให้ไฟล์เป็นกลางเพื่อลบร่องรอยการฝังข้อมูล")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.recompress_btn = QPushButton("Re-compress Image")
        self.recompress_btn.clicked.connect(self._recompress_image)
        self.strip_metadata_btn = QPushButton("Strip All Metadata")
        self.strip_metadata_btn.clicked.connect(self._strip_metadata)
        self.noise_btn = QPushButton("Apply Noise Filter")
        self.noise_btn.clicked.connect(self._apply_noise)

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
        self._data = data
        self._history = [data]
        self._history_entries = [HistoryEntry(f"Loaded: {os.path.basename(path)}", len(data))]
        self._refresh_history()
        self.file_label.setText(path)
        self._update_file_info()
        self._update_preview()

    def _set_data(self, data: bytes, description: str) -> None:
        self._data = data
        self._history.append(data)
        self._history_entries.append(HistoryEntry(description, len(data)))
        self._refresh_history()
        self._update_file_info()
        self._update_preview()

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
            self.preview_text.setPlainText("(no data)")
            return
        encoding = self.encoding_combo.currentText() or "utf-8"
        try:
            text = self._data.decode(encoding, errors="replace")
        except Exception:
            text = "(unable to decode with selected encoding)"
        self.preview_text.setPlainText(text)

    def _update_preview_hex(self) -> None:
        if self._data is None:
            self.preview_hex.setPlainText("(no data)")
            return
        self.preview_hex.setPlainText(self._hexdump(self._data))

    def _update_preview_image(self) -> None:
        if self._data is None:
            self.preview_image.setText("ไม่มีตัวอย่างภาพ")
            self.preview_image.setPixmap(QPixmap())
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
            self.preview_image.setPixmap(QPixmap())
            self.preview_image.setText("ไม่สามารถแสดงผลเป็นภาพได้")

    # ------------------------------------------------------------------
    # File info helpers
    # ------------------------------------------------------------------
    def _update_file_info(self) -> None:
        if self._data is None:
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
    def _hexdump(data: bytes, width: int = 16) -> str:
        lines: List[str] = []
        for offset in range(0, len(data), width):
            chunk = data[offset : offset + width]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            text_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"{offset:08X}  {hex_part:<{width * 3}}  {text_part}")
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

