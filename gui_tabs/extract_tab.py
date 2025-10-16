"""Extract tab implementation for the STEGOSIGHT GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QCheckBox,
)

from .common_widgets import InfoPanel


class ExtractTab(QWidget):
    """UI for the *Extract* functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_window = parent

        self.stego_path: Optional[Path] = None
        self.extracted_data: Optional[bytes] = None

        self._init_ui()

    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        left_layout.addWidget(self._create_file_group())
        left_layout.addWidget(self._create_method_group())
        left_layout.addWidget(self._create_decryption_group())
        left_layout.addWidget(self._create_result_group())
        left_layout.addStretch()

        left_scroll.setWidget(left_widget)
        splitter.addWidget(left_scroll)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(self._create_preview_group())
        right_layout.addWidget(self._create_details_group())
        right_layout.addStretch()
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 50)
        splitter.setStretchFactor(1, 50)
        main_layout.addWidget(splitter)

        self.action_btn = QPushButton("🔓 ดึงข้อมูล")
        self.action_btn.setObjectName("actionButton")
        self.action_btn.clicked.connect(self._start_extract)
        main_layout.addWidget(self.action_btn, 0, Qt.AlignRight)

    def _create_file_group(self) -> QGroupBox:
        group = QGroupBox("1. เลือกไฟล์ที่มีข้อมูลซ่อนอยู่")
        layout = QVBoxLayout(group)

        file_row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("เลือกไฟล์ที่ต้องการดึงข้อมูล...")
        self.file_input.setReadOnly(True)
        browse_btn = QPushButton("เลือกไฟล์")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.file_input)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        info = QLabel("รองรับไฟล์ที่สร้างโดย STEGOSIGHT ทุกประเภท")
        info.setObjectName("infoBox")
        info.setWordWrap(True)
        layout.addWidget(info)
        return group

    def _create_method_group(self) -> QGroupBox:
        group = QGroupBox("2. เลือกวิธีการที่ใช้ซ่อนข้อมูล")
        layout = QVBoxLayout(group)
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Adaptive (อัตโนมัติ)",
            "LSB Matching",
            "PVD",
            "DCT (JPEG)",
        ])
        layout.addWidget(self.method_combo)

        info = QLabel('เลือก "Adaptive" หากไม่ทราบวิธีที่ใช้')
        info.setObjectName("infoBox")
        info.setWordWrap(True)
        layout.addWidget(info)
        return group

    def _create_decryption_group(self) -> QGroupBox:
        group = QGroupBox("3. การถอดรหัส (Decryption)")
        layout = QVBoxLayout(group)

        self.encrypted_cb = QCheckBox("ข้อมูลถูกเข้ารหัส (ต้องใช้รหัสผ่าน)")
        self.encrypted_cb.setChecked(True)
        layout.addWidget(self.encrypted_cb)

        pwd_row = QHBoxLayout()
        pwd_row.addWidget(QLabel("รหัสผ่าน:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("กรอกรหัสผ่าน...")
        pwd_row.addWidget(self.password_input)
        layout.addLayout(pwd_row)

        self.encrypted_cb.toggled.connect(self.password_input.setEnabled)
        return group

    def _create_result_group(self) -> QGroupBox:
        group = QGroupBox("4. ผลลัพธ์")
        layout = QVBoxLayout(group)

        self.result_text = QTextEdit()
        self.result_text.setPlaceholderText("ข้อมูลที่ดึงออกมาจะแสดงที่นี่...")
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        save_btn = QPushButton("💾 บันทึกเป็นไฟล์")
        save_btn.clicked.connect(self._save_extracted)
        layout.addWidget(save_btn, 0, Qt.AlignRight)
        return group

    def _create_preview_group(self) -> QGroupBox:
        group = QGroupBox("ตัวอย่างไฟล์")
        layout = QVBoxLayout(group)

        self.preview_label = QLabel("ยังไม่ได้เลือกไฟล์")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setObjectName("previewArea")
        layout.addWidget(self.preview_label)

        panel, labels = self._create_info_panel(["ชื่อไฟล์", "ขนาด", "สถานะ"])
        self.file_info_panel = panel
        self.info_labels = labels
        layout.addWidget(panel)
        return group

    def _create_details_group(self) -> QGroupBox:
        group = QGroupBox("ข้อมูลการดึง")
        layout = QVBoxLayout(group)
        panel, labels = self._create_info_panel(["วิธีการตรวจพบ", "ขนาดข้อมูล", "สถานะการเข้ารหัส"])
        self.details_panel = panel
        self.details_labels = labels
        layout.addWidget(panel)
        return group

    def _create_info_panel(self, labels):
        panel = InfoPanel(labels)
        return panel, panel.value_labels

    # ------------------------------------------------------------------
    def _browse_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์ที่ซ่อนข้อมูล", "", "All Files (*.*)")
        if filename:
            self.stego_path = Path(filename)
            self.file_input.setText(filename)
            self._update_preview()

    def _update_preview(self) -> None:
        if not self.stego_path:
            return
        self.info_labels["ชื่อไฟล์"].setText(self.stego_path.name)
        size_kb = self.stego_path.stat().st_size / 1024
        self.info_labels["ขนาด"].setText(f"{size_kb:.2f} KB")
        self.info_labels["สถานะ"].setText("พร้อมตรวจสอบ")
        self.info_labels["สถานะ"].setStyleSheet("font-weight: bold; color: #1E88E5;")

        pixmap = QPixmap(str(self.stego_path))
        if not pixmap.isNull():
            self.preview_label.setPixmap(
                pixmap.scaled(
                    self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        else:
            self.preview_label.setText(f"ไฟล์: {self.stego_path.name}\nประเภท: {self.stego_path.suffix}")

    def _start_extract(self) -> None:
        if not self.stego_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์")
            return

        password: Optional[str] = None
        if self.encrypted_cb.isChecked():
            password = self.password_input.text()
            if not password:
                QMessageBox.warning(self, "คำเตือน", "กรุณากรอกรหัสผ่าน")
                return

        method_map = {0: "adaptive", 1: "lsb", 2: "pvd", 3: "dct"}
        method = method_map.get(self.method_combo.currentIndex(), "adaptive")

        params = {
            "stego_path": str(self.stego_path),
            "password": password,
            "method": method,
        }

        self._set_busy(True)
        self.parent_window.start_worker(
            "extract",
            params,
            on_result=self._on_extract_result,
            on_error=self._on_worker_error,
            on_finished=self._on_worker_finished,
        )

    def _on_extract_result(self, result: Dict[str, object]) -> None:
        self.extracted_data = result.get("data") if isinstance(result, dict) else None
        method = result.get("method", "adaptive") if isinstance(result, dict) else "adaptive"
        if isinstance(self.extracted_data, (bytes, bytearray)):
            try:
                decoded = self.extracted_data.decode("utf-8")
                self.result_text.setPlainText(decoded)
            except Exception:
                self.result_text.setPlainText(
                    f"ดึงข้อมูลไบนารีสำเร็จ ({len(self.extracted_data)} bytes)\n\nกรุณาบันทึกเป็นไฟล์"
                )
            self.details_labels["ขนาดข้อมูล"].setText(f"{len(self.extracted_data)} bytes")
        else:
            self.result_text.setPlainText("ไม่สามารถอ่านข้อมูลที่ดึงมาได้")
            self.details_labels["ขนาดข้อมูล"].setText("—")

        self.details_labels["วิธีการตรวจพบ"].setText(method.upper())
        self.details_labels["สถานะการเข้ารหัส"].setText(
            "ถอดรหัสแล้ว" if self.encrypted_cb.isChecked() else "ไม่มีการเข้ารหัส"
        )
        QMessageBox.information(self, "สำเร็จ", "ดึงข้อมูลสำเร็จ!")

    def _save_extracted(self) -> None:
        if not isinstance(self.extracted_data, (bytes, bytearray)):
            QMessageBox.warning(self, "คำเตือน", "ยังไม่มีข้อมูลที่ดึงออกมา")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "บันทึกไฟล์", "", "All Files (*.*)")
        if filename:
            Path(filename).write_bytes(self.extracted_data)
            QMessageBox.information(self, "สำเร็จ", f"บันทึกไฟล์สำเร็จ: {filename}")

    def _on_worker_error(self, error: str) -> None:
        QMessageBox.critical(self, "ข้อผิดพลาด", f"เกิดข้อผิดพลาด:\n{error}")
        self._set_busy(False)

    def _on_worker_finished(self) -> None:
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.action_btn.setEnabled(not busy)
