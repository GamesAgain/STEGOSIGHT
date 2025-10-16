"""Analyze tab implementation for the STEGOSIGHT GUI."""

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
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from .common_widgets import InfoPanel, RiskScoreWidget


class AnalyzeTab(QWidget):
    """UI for the *Analyze* functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.file_path: Optional[Path] = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        container_layout = QVBoxLayout(container)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(self._create_file_group())
        left_layout.addWidget(self._create_methods_group())
        left_layout.addWidget(self._create_options_group())
        left_layout.addStretch()
        top_layout.addWidget(left_widget, 2)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(self._create_preview_group())
        right_layout.addStretch()
        top_layout.addWidget(right_widget, 1)

        container_layout.addWidget(top_widget)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.action_btn = QPushButton("🔍 วิเคราะห์ไฟล์")
        self.action_btn.setObjectName("actionButton")
        self.action_btn.clicked.connect(self._start_analysis)
        action_layout.addWidget(self.action_btn)
        container_layout.addLayout(action_layout)

        results_group = QGroupBox("ผลการวิเคราะห์")
        results_layout = QVBoxLayout(results_group)
        self.risk_score_widget = RiskScoreWidget()
        results_layout.addWidget(self.risk_score_widget)

        details_panel, labels = self._create_info_panel(
            ["📊 Chi-Square Test", "🔍 ELA Analysis", "📈 Histogram", "🎯 ความมั่นใจ"]
        )
        self.details_panel = details_panel
        self.details_labels = labels
        results_layout.addWidget(details_panel)

        self.recommendation_box = self._create_info_box(
            "<b>คำแนะนำ:</b> เลือกไฟล์และเริ่มวิเคราะห์เพื่อดูผลลัพธ์"
        )
        results_layout.addWidget(self.recommendation_box)

        container_layout.addWidget(results_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_file_group(self) -> QGroupBox:
        group = QGroupBox("1. เลือกไฟล์สำหรับวิเคราะห์")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("เลือกไฟล์ภาพที่ต้องการวิเคราะห์...")
        self.file_input.setReadOnly(True)
        browse_btn = QPushButton("เลือกไฟล์")
        browse_btn.clicked.connect(self._browse_file)
        row.addWidget(self.file_input)
        row.addWidget(browse_btn)
        layout.addLayout(row)
        layout.addWidget(self._create_info_box("รองรับ: PNG, JPEG, BMP"))
        return group

    def _create_methods_group(self) -> QGroupBox:
        group = QGroupBox("2. วิธีการวิเคราะห์")
        layout = QVBoxLayout(group)
        self.chi_square_cb = QCheckBox("Chi-Square Attack - ตรวจจับ LSB")
        self.chi_square_cb.setChecked(True)
        self.ela_cb = QCheckBox("Error Level Analysis (ELA) - วิเคราะห์ JPEG")
        self.ela_cb.setChecked(True)
        self.histogram_cb = QCheckBox("Histogram Analysis - วิเคราะห์สี")
        self.histogram_cb.setChecked(True)
        self.ml_cb = QCheckBox("Machine Learning - AI ตรวจจับ (ทดลอง)")
        layout.addWidget(self.chi_square_cb)
        layout.addWidget(self.ela_cb)
        layout.addWidget(self.histogram_cb)
        layout.addWidget(self.ml_cb)
        layout.addWidget(self._create_info_box("เลือกหลายวิธีเพื่อผลลัพธ์ที่แม่นยำ"))
        return group

    def _create_options_group(self) -> QGroupBox:
        group = QGroupBox("3. ตัวเลือกเพิ่มเติม")
        layout = QVBoxLayout(group)
        self.compare_checkbox = QCheckBox("แสดงภาพเปรียบเทียบแบบละเอียด")
        self.pdf_checkbox = QCheckBox("สร้างรายงาน PDF")
        self.reference_checkbox = QCheckBox("เปรียบเทียบกับไฟล์ต้นฉบับ (ถ้ามี)")
        layout.addWidget(self.compare_checkbox)
        layout.addWidget(self.pdf_checkbox)
        layout.addWidget(self.reference_checkbox)
        return group

    def _create_preview_group(self) -> QGroupBox:
        group = QGroupBox("ตัวอย่างไฟล์")
        layout = QVBoxLayout(group)
        self.preview_label = QLabel("ยังไม่ได้เลือกไฟล์")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setObjectName("previewArea")
        layout.addWidget(self.preview_label)
        return group

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
            "เลือกไฟล์สำหรับวิเคราะห์",
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

    def _start_analysis(self) -> None:
        if not self.file_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์ที่จะวิเคราะห์")
            return

        methods: List[str] = []
        if self.chi_square_cb.isChecked():
            methods.append("chi-square")
        if self.ela_cb.isChecked():
            methods.append("ela")
        if self.histogram_cb.isChecked():
            methods.append("histogram")
        if self.ml_cb.isChecked():
            methods.append("ml")
        if not methods:
            methods = ["all"]

        params = {
            "file_path": str(self.file_path),
            "methods": methods,
        }

        self._set_busy(True)
        self.parent_window.start_worker(
            "analyze",
            params,
            on_result=self._on_analysis_result,
            on_error=self._on_worker_error,
            on_finished=self._on_worker_finished,
        )

    def _on_analysis_result(self, result: Dict[str, object]) -> None:
        score = int(result.get("score", 42))
        level = str(result.get("level", "MEDIUM"))
        details = result.get("details", {}) if isinstance(result, dict) else {}

        color = "#4CAF50"
        if score >= 60:
            color = "#F44336"
        elif score >= 30:
            color = "#FF9800"

        description = ""
        if isinstance(details, dict):
            chi = details.get("chi_square", "—")
            ela = details.get("ela", "—")
            hist = details.get("histogram", "—")
            description = f"Chi-Square: {chi}\nELA: {ela}\nHistogram: {hist}"
            self.details_labels["📊 Chi-Square Test"].setText(str(chi))
            self.details_labels["🔍 ELA Analysis"].setText(str(ela))
            self.details_labels["📈 Histogram"].setText(str(hist))
            confidence = details.get("confidence", "—")
            self.details_labels["🎯 ความมั่นใจ"].setText(str(confidence))
        else:
            for key in self.details_labels:
                self.details_labels[key].setText("—")

        self.risk_score_widget.set_score(score, level.upper(), description, color)

        if score >= 60:
            advice = "<b>คำแนะนำ:</b> พบความเสี่ยงสูง แนะนำให้ใช้ฟังก์ชัน Neutralize"
        elif score >= 30:
            advice = "<b>คำแนะนำ:</b> พบความเสี่ยงปานกลาง ควรตรวจสอบเพิ่มเติม"
        else:
            advice = "<b>คำแนะนำ:</b> ความเสี่ยงต่ำ แต่ควรเก็บไฟล์อย่างระมัดระวัง"
        self.recommendation_box.setText(advice)

    def _on_worker_error(self, error: str) -> None:
        QMessageBox.critical(self, "ข้อผิดพลาด", f"วิเคราะห์ล้มเหลว:\n{error}")
        self._set_busy(False)

    def _on_worker_finished(self) -> None:
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.action_btn.setEnabled(not busy)
