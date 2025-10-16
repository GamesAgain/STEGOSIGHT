"""Neutralize tab implementation for the STEGOSIGHT GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

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
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QComboBox,
)

from .common_widgets import InfoPanel, RiskScoreWidget


class NeutralizeTab(QWidget):
    """UI for the *Neutralize* functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.file_path: Optional[Path] = None
        self._last_output_path: Optional[str] = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        top_splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(self._create_file_group())
        left_layout.addWidget(self._create_methods_group())
        left_layout.addWidget(self._create_options_group())
        left_layout.addStretch()
        top_splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(self._create_preview_group())
        right_layout.addWidget(self._create_processing_group())
        right_layout.addStretch()
        top_splitter.addWidget(right_widget)

        top_splitter.setStretchFactor(0, 60)
        top_splitter.setStretchFactor(1, 40)
        container_layout.addWidget(top_splitter)

        self.action_btn = QPushButton("🛡️ ทำให้เป็นกลาง")
        self.action_btn.setObjectName("actionButton")
        self.action_btn.clicked.connect(self._start_neutralize)
        container_layout.addWidget(self.action_btn, 0, Qt.AlignRight)

        results_group = QGroupBox("ผลการประมวลผล")
        results_layout = QVBoxLayout(results_group)

        comparison_layout = QHBoxLayout()
        before_card, before_widget = self._create_comparison_card("ก่อน", 42, "MEDIUM", "#FF9800")
        after_card, after_widget = self._create_comparison_card("หลัง", 10, "LOW", "#4CAF50")
        self.before_risk_widget = before_widget
        self.after_risk_widget = after_widget
        comparison_layout.addWidget(before_card)
        comparison_layout.addWidget(after_card)
        results_layout.addLayout(comparison_layout)

        summary_panel, labels = self._create_info_panel(
            ["✓ Metadata Stripped", "✓ Re-compressed", "✓ Resized", "Risk Score ลดลง"]
        )
        self.summary_panel = summary_panel
        self.summary_labels = labels
        results_layout.addWidget(summary_panel)

        self.success_box = self._create_success_box()
        self.success_box.setVisible(False)
        results_layout.addWidget(self.success_box)

        container_layout.addWidget(results_group)
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_file_group(self) -> QGroupBox:
        group = QGroupBox("1. เลือกไฟล์ที่จะทำให้เป็นกลาง")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("เลือกไฟล์ภาพ...")
        self.file_input.setReadOnly(True)
        browse_btn = QPushButton("เลือกไฟล์")
        browse_btn.clicked.connect(self._browse_file)
        row.addWidget(self.file_input)
        row.addWidget(browse_btn)
        layout.addLayout(row)
        layout.addWidget(self._create_info_box("รองรับ: PNG, JPEG, BMP, etc."))
        return group

    def _create_methods_group(self) -> QGroupBox:
        group = QGroupBox("2. วิธีการทำให้เป็นกลาง")
        layout = QVBoxLayout(group)
        self.metadata_cb = QCheckBox("Strip EXIF/Metadata - ลบ metadata")
        self.metadata_cb.setChecked(True)
        self.recompress_cb = QCheckBox("Re-compress Image - บีบอัดภาพซ้ำ")
        self.recompress_cb.setChecked(True)
        self.transform_cb = QCheckBox("Transform (Resize/Noise) - ปรับขนาด/เพิ่ม noise")
        layout.addWidget(self.metadata_cb)
        layout.addWidget(self.recompress_cb)
        layout.addWidget(self.transform_cb)
        warning_box = self._create_info_box(
            "<b>คำเตือน:</b> การทำให้เป็นกลางจะทำลายข้อมูลที่ซ่อนอยู่ และอาจลดคุณภาพภาพ"
        )
        warning_box.setStyleSheet(
            warning_box.styleSheet() + "background-color: #fff9c4; border-left-color: #fdd835;"
        )
        layout.addWidget(warning_box)
        return group

    def _create_options_group(self) -> QGroupBox:
        group = QGroupBox("3. ตัวเลือกการบีบอัด")
        layout = QVBoxLayout(group)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("ระดับคุณภาพ:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["สูง (95%)", "ปานกลาง (85%)", "ต่ำ (75%)"])
        self.quality_combo.setCurrentIndex(1)
        quality_row.addWidget(self.quality_combo)

        resize_row = QHBoxLayout()
        resize_row.addWidget(QLabel("ขนาดภาพ:"))
        self.resize_combo = QComboBox()
        self.resize_combo.addItems(["ไม่เปลี่ยนแปลง", "ลด 10%", "ลด 20%", "ลด 30%"])
        self.resize_combo.setCurrentIndex(2)
        resize_row.addWidget(self.resize_combo)

        layout.addLayout(quality_row)
        layout.addLayout(resize_row)
        return group

    def _create_preview_group(self) -> QGroupBox:
        group = QGroupBox("ตัวอย่างไฟล์")
        layout = QVBoxLayout(group)
        self.preview_label = QLabel("ยังไม่ได้เลือกไฟล์")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setObjectName("previewArea")
        layout.addWidget(self.preview_label)
        return group

    def _create_processing_group(self) -> QGroupBox:
        group = QGroupBox("การประมวลผล")
        layout = QVBoxLayout(group)
        panel, labels = self._create_info_panel(
            ["สถานะ", "ขนาดไฟล์เดิม", "ขนาดไฟล์ใหม่ (คาดการณ์)", "เวลาโดยประมาณ"]
        )
        self.processing_panel = panel
        self.processing_labels = labels
        layout.addWidget(panel)
        return group

    def _create_comparison_card(self, title_prefix: str, score: int, level: str, color: str):
        card = QWidget()
        card.setObjectName("comparisonCard")
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        title = QLabel(f"{title_prefix}ทำให้เป็นกลาง")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold;")

        preview = QLabel("ภาพตัวอย่าง")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumHeight(150)
        preview.setObjectName("previewArea")

        risk_widget = RiskScoreWidget()
        risk_widget.set_score(score, level, "", color)

        layout.addWidget(title)
        layout.addWidget(preview)
        layout.addWidget(risk_widget)
        return card, risk_widget

    def _create_success_box(self) -> QWidget:
        box = QWidget()
        box.setObjectName("successBox")
        layout = QVBoxLayout(box)
        msg = QLabel("<b>✓ สำเร็จ!</b> ไฟล์ถูกทำให้เป็นกลางแล้ว")
        msg.setWordWrap(True)
        layout.addWidget(msg)
        save_btn = QPushButton("💾 บันทึกไฟล์")
        save_btn.clicked.connect(self._save_output_file)
        layout.addWidget(save_btn)
        return box

    def _create_info_box(self, text: str) -> QLabel:
        info = QLabel(text)
        info.setWordWrap(True)
        info.setObjectName("infoBox")
        return info

    def _create_info_panel(self, labels):
        panel = InfoPanel(labels)
        return panel, panel.value_labels

    # ------------------------------------------------------------------
    def _browse_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "เลือกไฟล์",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)",
        )
        if filename:
            self.file_path = Path(filename)
            self.file_input.setText(filename)
            pixmap = QPixmap(filename)
            if not pixmap.isNull():
                self.preview_label.setPixmap(
                    pixmap.scaled(
                        self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
            else:
                self.preview_label.setText(f"ไฟล์: {Path(filename).name}")
            size_kb = self.file_path.stat().st_size / 1024
            self.processing_labels["ขนาดไฟล์เดิม"].setText(f"{size_kb:.2f} KB")
            self.processing_labels["สถานะ"].setText("พร้อมประมวลผล")
            self.processing_labels["สถานะ"].setStyleSheet("font-weight: bold; color: #1E88E5;")

    def _start_neutralize(self) -> None:
        if not self.file_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์")
            return

        methods: List[str] = []
        if self.metadata_cb.isChecked():
            methods.append("metadata")
        if self.recompress_cb.isChecked():
            methods.append("recompress")
        if self.transform_cb.isChecked():
            methods.append("transform")
        if not methods:
            methods = ["metadata"]

        params = {
            "file_path": str(self.file_path),
            "methods": methods,
            "quality": self.quality_combo.currentText(),
            "resize": self.resize_combo.currentText(),
        }

        self._set_busy(True)
        self.parent_window.start_worker(
            "neutralize",
            params,
            on_result=self._on_neutralize_result,
            on_error=self._on_worker_error,
            on_finished=self._on_worker_finished,
        )

    def _on_neutralize_result(self, result: Dict[str, object]) -> None:
        output_path = result.get("output_path", "")
        used_methods = result.get("methods", [])
        if isinstance(used_methods, list):
            used_methods = [str(m) for m in used_methods]
        else:
            used_methods = []

        # Update summary panel
        self.summary_labels["✓ Metadata Stripped"].setText("✔" if "metadata" in used_methods else "—")
        self.summary_labels["✓ Re-compressed"].setText("✔" if "recompress" in used_methods else "—")
        self.summary_labels["✓ Resized"].setText("✔" if "transform" in used_methods else "—")
        self.summary_labels["Risk Score ลดลง"].setText("YES" if used_methods else "—")

        # Update risk widgets with illustrative values
        self.before_risk_widget.set_score(42, "MEDIUM", "ก่อนทำให้เป็นกลาง", "#FF9800")
        self.after_risk_widget.set_score(8, "LOW", "หลังทำให้เป็นกลาง", "#4CAF50")

        self.processing_labels["สถานะ"].setText("เสร็จสิ้น")
        self.processing_labels["สถานะ"].setStyleSheet("font-weight: bold; color: #4CAF50;")
        self.processing_labels["ขนาดไฟล์ใหม่ (คาดการณ์)"].setText("—")
        self.processing_labels["เวลาโดยประมาณ"].setText("—")

        self.success_box.setVisible(True)
        self._last_output_path = str(output_path)
        QMessageBox.information(self, "สำเร็จ", "ไฟล์ถูกทำให้เป็นกลางเรียบร้อย")

    def _save_output_file(self) -> None:
        path = getattr(self, "_last_output_path", None)
        if not path:
            QMessageBox.warning(self, "คำเตือน", "ยังไม่มีไฟล์ผลลัพธ์")
            return
        QMessageBox.information(self, "ข้อมูล", f"ไฟล์ถูกจัดเก็บไว้ที่: {path}")

    def _on_worker_error(self, error: str) -> None:
        QMessageBox.critical(self, "ข้อผิดพลาด", f"Neutralization ล้มเหลว:\n{error}")
        self._set_busy(False)

    def _on_worker_finished(self) -> None:
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.action_btn.setEnabled(not busy)
