"""Analyze tab implementation for the STEGOSIGHT GUI."""

from __future__ import annotations

import datetime
import io
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPixmap, QPainter
from PyQt5.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from PIL import Image, ImageQt

from .common_widgets import RiskScoreWidget
from .styles import apply_analyze_styles
from utils.logger import setup_logger


# ----------------------------- Visual helper utilities -----------------------------

def _ensure_rgb(img: Image.Image) -> Image.Image:
    """Normalize any PIL image into RGB mode."""

    if img.mode == "RGB":
        return img
    return img.convert("RGB")


def _downscale_if_needed(img: Image.Image, max_side: int = 1600) -> Image.Image:
    """Prevent overly large previews from blocking the UI."""

    width, height = img.size
    scale = max(width, height) / float(max_side)
    if scale <= 1:
        return img
    new_size = (int(round(width / scale)), int(round(height / scale)))
    return img.resize(new_size, Image.LANCZOS)


def _qpixmap_from_pil(img: Image.Image) -> QPixmap:
    """Create a detached :class:`QPixmap` from a PIL image."""

    try:
        qimage = ImageQt.ImageQt(img)  # type: ignore[call-arg]
        return QPixmap.fromImage(qimage.copy())
    except AttributeError:
        # Some Pillow builds omit ``ImageQt.ImageQt`` (e.g. when Qt bindings are
        # unavailable at install time). Fall back to a manual conversion to a
        # :class:`QImage` to preserve preview functionality.
        rgb_img = _ensure_rgb(img)
        data = rgb_img.tobytes("raw", "RGB")
        qimage = QImage(
            data, rgb_img.width, rgb_img.height, QImage.Format_RGB888
        )
        return QPixmap.fromImage(qimage.copy())


def luminance_histogram(rgb: np.ndarray) -> np.ndarray:
    """Return a luminance histogram (Y channel) for an RGB numpy array."""

    r = rgb[..., 0].astype(np.float32)
    g = rgb[..., 1].astype(np.float32)
    b = rgb[..., 2].astype(np.float32)
    y = np.clip(0.299 * r + 0.587 * g + 0.114 * b, 0, 255).astype(np.uint8)
    return np.bincount(y.ravel(), minlength=256).astype(np.int64)


def draw_histogram_pixmap(hist: np.ndarray, size: Tuple[int, int] = (512, 160)) -> QPixmap:
    """Render a luminance histogram onto a :class:`QPixmap`."""

    width, height = size
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.white)

    painter = QPainter(pixmap)
    painter.setPen(Qt.NoPen)
    max_value = float(hist.max() if hist.max() > 0 else 1)
    bar_width = max(1.0, width / 256.0)
    bar_color = QColor(31, 41, 55)
    for index, value in enumerate(hist):
        bar_height = (value / max_value) * (height - 6)
        x_pos = int(index * bar_width)
        y_pos = int(height - bar_height)
        painter.setBrush(bar_color)
        painter.drawRect(x_pos, y_pos, max(1, int(bar_width - 1)), int(bar_height))
    painter.end()
    return pixmap


def chi_square_parity_suspicion(hist: np.ndarray) -> float:
    """Chi-square even/odd parity heuristic scaled to 0..100."""

    stat = 0.0
    for i in range(0, 256, 2):
        even = hist[i]
        odd = hist[i + 1]
        total = even + odd
        if total == 0:
            continue
        expected = total / 2.0
        stat += ((even - expected) ** 2) / expected
        stat += ((odd - expected) ** 2) / expected
    score = 100.0 - min(100.0, math.log1p(stat) * 18.0)
    return max(0.0, min(100.0, score))


def histogram_flatness_score(hist: np.ndarray) -> float:
    """Measure the flatness of a histogram (lower variance → higher score)."""

    total = float(hist.sum())
    if total <= 0:
        return 0.0
    mean = total / float(len(hist))
    variance = float(((hist - mean) ** 2).mean())
    flatness = 100.0 - min(100.0, math.log1p(math.sqrt(variance)) * 20.0)
    return max(0.0, min(100.0, flatness))


def compute_ela_heatmap(image: Image.Image, jpeg_quality: int = 75, scale: float = 8.0) -> Tuple[Image.Image, float]:
    """Compute an Error Level Analysis heatmap and its heuristic score."""

    base = _ensure_rgb(image)
    buffer = io.BytesIO()
    base.save(buffer, format="JPEG", quality=jpeg_quality)
    buffer.seek(0)
    recompressed = Image.open(buffer).convert("RGB")

    original_arr = np.asarray(base, dtype=np.int16)
    recompressed_arr = np.asarray(recompressed, dtype=np.int16)
    diff = np.abs(original_arr - recompressed_arr)
    channel_diff = diff.mean(axis=2)

    avg = float(channel_diff.mean())
    suspicion = max(0.0, min(100.0, (avg / 10.0) * 100.0))

    amplified = np.clip(channel_diff * scale, 0, 255).astype(np.uint8)
    heat = np.zeros((amplified.shape[0], amplified.shape[1], 3), dtype=np.uint8)
    heat[..., 0] = amplified
    heat[..., 2] = 255 - amplified
    heatmap = Image.fromarray(heat, mode="RGB")
    return heatmap, suspicion


def aggregate_risk(chi: float, ela: float, flat: float, ml: float = 0.0) -> int:
    """Combine heuristic sub-scores into a single 0..100 score."""

    weights = (0.35, 0.35, 0.25, 0.05)
    score = chi * weights[0] + ela * weights[1] + flat * weights[2] + ml * weights[3]
    return int(round(max(0.0, min(100.0, score))))


class PreviewLabel(QLabel):
    """Display widget for image previews that keeps aspect ratio on resize."""

    def __init__(self, placeholder: str, min_size: Tuple[int, int], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._placeholder = placeholder
        self._pixmap = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(*min_size)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)
        self.setStyleSheet(
            "background-color: #ffffff; border: 1px dashed #d1d5db; "
            "border-radius: 6px; padding: 8px;"
        )
        self.setText(placeholder)

    def set_preview(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._update_scaled_pixmap()

    def clear_preview(self) -> None:
        self._pixmap = QPixmap()
        super().setPixmap(self._pixmap)
        self.setText(self._placeholder)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self) -> None:
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            super().setPixmap(scaled)
            self.setText("")


class VisualRiskGauge(QFrame):
    """Compact score widget inspired by the React Analyze gauge."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("visualRiskGauge")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        title = QLabel("Risk Score")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: 600;")
        self.score_label = QLabel("—")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("font-size: 32px; font-weight: 800;")
        self.level_label = QLabel("ยังไม่ได้วิเคราะห์")
        self.level_label.setAlignment(Qt.AlignCenter)
        self.status_label = QLabel("เลือกไฟล์แล้วกดวิเคราะห์เพื่อเริ่มต้น")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)

        layout.addWidget(title)
        layout.addWidget(self.score_label)
        layout.addWidget(self.level_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)

        self._apply_palette(QColor(99, 102, 241))
        self.reset()

    @staticmethod
    def _color_for(score: int) -> QColor:
        if score < 40:
            return QColor(34, 197, 94)
        if score < 70:
            return QColor(245, 158, 11)
        return QColor(239, 68, 68)

    @staticmethod
    def _label_for(score: int) -> str:
        if score < 40:
            return "ต่ำ (Low)"
        if score < 70:
            return "กลาง (Medium)"
        return "สูง (High)"

    def _apply_palette(self, color: QColor) -> None:
        accent = f"rgb({color.red()}, {color.green()}, {color.blue()})"
        self.score_label.setStyleSheet(
            f"font-size: 32px; font-weight: 800; color: {accent};"
        )
        self.level_label.setStyleSheet(f"font-weight: 600; color: {accent};")
        self.progress.setStyleSheet(
            "QProgressBar { background:#e5e7eb; border-radius:5px; }"
            f"QProgressBar::chunk {{ background: {accent}; border-radius:5px; }}"
        )

    def reset(self) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._apply_palette(QColor(99, 102, 241))
        self.score_label.setText("—")
        self.level_label.setText("ยังไม่ได้วิเคราะห์")
        self.status_label.setText("เลือกไฟล์แล้วกดวิเคราะห์เพื่อเริ่มต้น")

    def show_analyzing(self) -> None:
        self._apply_palette(QColor(99, 102, 241))
        self.progress.setRange(0, 0)
        self.score_label.setText("…")
        self.level_label.setText("กำลังวิเคราะห์…")
        self.status_label.setText("ระบบกำลังรวบรวมผลจากโมดูลต่าง ๆ")

    def set_score(self, score: int) -> None:
        bounded = max(0, min(100, int(score)))
        color = self._color_for(bounded)
        self._apply_palette(color)
        self.progress.setRange(0, 100)
        self.progress.setValue(bounded)
        self.score_label.setText(str(bounded))
        self.level_label.setText(self._label_for(bounded))
        if bounded < 40:
            status = "ประเมินว่าเสี่ยงต่ำ"
        elif bounded < 70:
            status = "พบสัญญาณที่น่าสงสัย"
        else:
            status = "มีความเป็นไปได้สูงว่ามีการซ่อนข้อมูล"
        self.status_label.setText(status)

    def set_status_text(self, text: str) -> None:
        self.status_label.setText(text)


class AnalyzeTab(QWidget):
    """UI for the *Analyze* functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.file_path: Optional[Path] = None
        self.selected_media_type: str = "image"
        self.media_type_buttons: Dict[str, QPushButton] = {}
        self.active_checks: Dict[str, bool] = {
            "statistical": True,
            "structural": True,
            "metadata": True,
        }
        self.media_type_supports = {
            "image": "รองรับ: PNG, JPEG, BMP",
            "audio": "รองรับ: WAV, MP3, FLAC",
            "video": "รองรับ: MP4, AVI, MKV, MOV",
        }
        self.media_type_filters = {
            "image": "ไฟล์ภาพ (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)",
            "audio": "ไฟล์เสียง (*.wav *.mp3 *.flac);;All Files (*.*)",
            "video": "ไฟล์วิดีโอ (*.mp4 *.avi *.mkv *.mov);;All Files (*.*)",
        }
        self.media_type_placeholders = {
            "image": "ยังไม่ได้เลือกไฟล์ภาพ...",
            "audio": "ยังไม่ได้เลือกไฟล์เสียง...",
            "video": "ยังไม่ได้เลือกไฟล์วิดีโอ...",
        }
        self.image_suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

        self._preview_image: Optional[Image.Image] = None
        self._preview_array: Optional[np.ndarray] = None
        self._preview_hist: Optional[np.ndarray] = None
        self._visual_scores: Dict[str, float] = {}
        self.visual_metric_labels: Dict[str, QLabel] = {}
        self.visual_metric_names: Dict[str, str] = {
            "chi_square": "Chi-Square",
            "ela": "ELA",
            "histogram": "Histogram",
            "ml": "Machine Learning",
        }
        self.visual_group: Optional[QGroupBox] = None

        self.logger = setup_logger(__name__)
        self._init_ui()
        apply_analyze_styles(self)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 16, 16, 16)
        container_layout.setSpacing(18)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(16)
        left_layout.addWidget(self._create_file_group())
        left_layout.addWidget(self._create_settings_group())
        left_layout.addWidget(self._create_action_section())
        left_layout.addStretch()
        left_widget.setMinimumWidth(320)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(16)
        right_layout.addWidget(self._create_visual_panel())
        right_layout.addWidget(self._create_log_group())
        right_layout.addWidget(self._create_summary_group())
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)

        container_layout.addWidget(splitter)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_file_group(self) -> QGroupBox:
        group = QGroupBox("1. เลือกไฟล์สำหรับวิเคราะห์")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_row.addWidget(QLabel("เลือกประเภทสื่อ:"))
        for key, label in (
            ("image", "🖼️ ไฟล์ภาพ"),
            ("audio", "🎧 ไฟล์เสียง"),
            ("video", "🎞️ ไฟล์วิดีโอ"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("toggleButton")
            button.setChecked(key == self.selected_media_type)
            button.clicked.connect(lambda _, media=key: self._set_media_type(media))
            self.media_type_buttons[key] = button
            type_row.addWidget(button)

        type_row.addStretch()
        layout.addLayout(type_row)

        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText(self.media_type_placeholders[self.selected_media_type])
        self.file_input.setReadOnly(True)
        browse_btn = QPushButton("เลือกไฟล์...")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.file_input)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        self.support_label = self._create_info_label(
            self.media_type_supports[self.selected_media_type]
        )
        layout.addWidget(self.support_label)

        self._set_media_type(self.selected_media_type)
        return group

    def _create_settings_group(self) -> QGroupBox:
        group = QGroupBox("2. ตั้งค่าการวิเคราะห์")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.statistical_cb = QCheckBox("การวิเคราะห์ทางสถิติ (Statistical Analysis)")
        self.statistical_cb.setChecked(True)
        self.structural_cb = QCheckBox("การวิเคราะห์โครงสร้างไฟล์ (Structural Analysis)")
        self.structural_cb.setChecked(True)
        self.metadata_cb = QCheckBox("การวิเคราะห์ Metadata")
        self.metadata_cb.setChecked(True)

        layout.addWidget(self.statistical_cb)
        layout.addWidget(self.structural_cb)
        layout.addWidget(self.metadata_cb)
        layout.addWidget(
            self._create_info_label(
                "เลือกได้หลายเทคนิคเพื่อเจาะลึกความผิดปกติ ทุกตัวเลือกสามารถปรับเปลี่ยนได้"
            )
        )
        return group

    def _create_action_section(self) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.addStretch()
        self.analyze_button = QPushButton("🚀 เริ่มการวิเคราะห์")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self._start_analysis)
        layout.addWidget(self.analyze_button)
        return wrapper

    def _create_visual_panel(self) -> QGroupBox:
        group = QGroupBox("3. ภาพรวมการตรวจวิเคราะห์เชิงภาพ")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        self.visual_gauge = VisualRiskGauge()
        self.visual_gauge.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        header_row.addWidget(self.visual_gauge, 1)

        metrics_frame = QFrame()
        metrics_frame.setObjectName("visualMetricsFrame")
        metrics_layout = QVBoxLayout(metrics_frame)
        metrics_layout.setContentsMargins(12, 12, 12, 12)
        metrics_layout.setSpacing(6)
        metrics_title = QLabel("คะแนนเทคนิค (0-100)")
        metrics_title.setStyleSheet("font-weight: 600;")
        metrics_layout.addWidget(metrics_title)
        self.visual_metric_labels.clear()
        for key, label in self.visual_metric_names.items():
            metric_label = QLabel(f"{label}: —")
            metric_label.setObjectName("visualMetricLabel")
            metrics_layout.addWidget(metric_label)
            self.visual_metric_labels[key] = metric_label
        metrics_layout.addStretch()
        header_row.addWidget(metrics_frame, 1)

        layout.addLayout(header_row)

        preview_grid = QGridLayout()
        preview_grid.setSpacing(12)
        self.original_preview = PreviewLabel("ยังไม่มีภาพตัวอย่าง", (320, 220))
        self.ela_preview = PreviewLabel("ยังไม่มี Heatmap", (320, 220))
        self.histogram_preview = PreviewLabel("ยังไม่มีฮิสโตแกรม", (340, 180))
        preview_grid.addWidget(self._wrap_preview_widget("ภาพต้นฉบับ", self.original_preview), 0, 0)
        preview_grid.addWidget(self._wrap_preview_widget("ELA Heatmap", self.ela_preview), 0, 1)
        preview_grid.addWidget(
            self._wrap_preview_widget("Luminance Histogram", self.histogram_preview), 1, 0, 1, 2
        )
        layout.addLayout(preview_grid)

        self.visual_group = group
        self._clear_visual_panel()
        self._update_visual_state_for_media(self.selected_media_type)
        return group

    def _wrap_preview_widget(self, title: str, widget: PreviewLabel) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        caption = QLabel(title)
        caption.setStyleSheet("font-weight: 600;")
        layout.addWidget(caption)
        layout.addWidget(widget)
        return frame

    def _create_log_group(self) -> QGroupBox:
        group = QGroupBox("4. Log การทำงานสด")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        self.live_log = QPlainTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setObjectName("liveLogConsole")
        self.live_log.setStyleSheet(
            "QPlainTextEdit#liveLogConsole {"
            "background-color: #111827;"
            "color: #d1d5db;"
            "font-family: 'JetBrains Mono', monospace;"
            "padding: 12px;"
            "border-radius: 6px;"
            "}"
        )
        self.live_log.setPlaceholderText("Awaiting analysis to start...")
        self.live_log.setFixedHeight(260)
        layout.addWidget(self.live_log)
        return group

    def _create_summary_group(self) -> QGroupBox:
        group = QGroupBox("5. สรุปผลและคำแนะนำ")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.summary_container = QFrame()
        self.summary_container.setObjectName("summaryContainer")
        self.summary_container.setStyleSheet(
            "QFrame#summaryContainer {"
            "background-color: #f3f4f6;"
            "border: 1px solid #d1d5db;"
            "border-radius: 8px;"
            "padding: 16px;"
            "}"
        )
        summary_layout = QVBoxLayout(self.summary_container)
        summary_layout.setSpacing(10)

        self.summary_title = QLabel("ยังไม่มีการวิเคราะห์")
        self.summary_title.setObjectName("summaryTitle")
        self.summary_title.setStyleSheet("font-weight: bold; font-size: 15px;")
        self.summary_message = QLabel("เลือกไฟล์แล้วกดวิเคราะห์เพื่อดูผลลัพธ์โดยละเอียด")
        self.summary_message.setWordWrap(True)

        summary_layout.addWidget(self.summary_title)
        summary_layout.addWidget(self.summary_message)

        self.risk_score_widget = RiskScoreWidget()
        summary_layout.addWidget(self.risk_score_widget)

        self.analysis_table = QTableWidget(0, 3)
        self.analysis_table.setHorizontalHeaderLabels(["Technique", "Result", "Confidence"])
        self.analysis_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.analysis_table.verticalHeader().setVisible(False)
        self.analysis_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.analysis_table.setSelectionMode(QTableWidget.NoSelection)
        summary_layout.addWidget(self.analysis_table)

        layout.addWidget(self.summary_container)

        self.guidance_frame = QFrame()
        self.guidance_frame.setObjectName("guidanceFrame")
        self.guidance_frame.setStyleSheet(
            "QFrame#guidanceFrame {"
            "background-color: #eef2ff;"
            "border-left: 4px solid #4f46e5;"
            "padding: 12px;"
            "border-radius: 4px;"
            "}"
        )
        guidance_layout = QVBoxLayout(self.guidance_frame)
        guidance_layout.setContentsMargins(8, 4, 8, 4)
        self.guidance_title = QLabel("คำแนะนำ (Actionable Guidance)")
        self.guidance_title.setStyleSheet("font-weight: bold; color: #3730a3;")
        self.guidance_label = QLabel("จะปรากฏคำแนะนำหลังจากการวิเคราะห์")
        self.guidance_label.setWordWrap(True)
        guidance_layout.addWidget(self.guidance_title)
        guidance_layout.addWidget(self.guidance_label)
        layout.addWidget(self.guidance_frame)

        self.guidance_frame.setVisible(False)
        return group

    def _clear_visual_panel(self) -> None:
        self._preview_image = None
        self._preview_array = None
        self._preview_hist = None
        self._visual_scores = {}
        if hasattr(self, "original_preview"):
            self.original_preview.clear_preview()
        if hasattr(self, "ela_preview"):
            self.ela_preview.clear_preview()
        if hasattr(self, "histogram_preview"):
            self.histogram_preview.clear_preview()
        self._apply_metric_labels({})
        if hasattr(self, "visual_gauge"):
            self.visual_gauge.reset()

    def _update_visual_state_for_media(self, media_type: str) -> None:
        if self.visual_group is not None:
            self.visual_group.setVisible(media_type == "image")
        if media_type != "image":
            self._clear_visual_panel()
        elif self.file_path and self.file_path.suffix.lower() in self.image_suffixes:
            self._prepare_visual_preview()
        else:
            self._clear_visual_panel()

    def _prepare_visual_preview(self) -> None:
        if self.selected_media_type != "image" or not self.file_path:
            self._clear_visual_panel()
            return
        try:
            image = Image.open(str(self.file_path))
            image = _ensure_rgb(_downscale_if_needed(image))
        except Exception as exc:  # pragma: no cover - GUI feedback
            self.logger.warning("Cannot load preview for %s: %s", self.file_path, exc)
            self._clear_visual_panel()
            if hasattr(self, "visual_gauge"):
                self.visual_gauge.set_status_text("ไม่สามารถเปิดไฟล์ภาพเพื่อแสดงตัวอย่างได้")
            return

        self._preview_image = image
        self._preview_array = np.asarray(image, dtype=np.uint8)
        self._preview_hist = luminance_histogram(self._preview_array)

        if hasattr(self, "original_preview"):
            self.original_preview.set_preview(_qpixmap_from_pil(image))
        heatmap, ela_score = compute_ela_heatmap(image)
        if hasattr(self, "ela_preview"):
            self.ela_preview.set_preview(_qpixmap_from_pil(heatmap))
        if hasattr(self, "histogram_preview") and self._preview_hist is not None:
            self.histogram_preview.set_preview(draw_histogram_pixmap(self._preview_hist))

        self._visual_scores = {
            "chi_square": chi_square_parity_suspicion(self._preview_hist),
            "histogram": histogram_flatness_score(self._preview_hist),
            "ela": ela_score,
        }
        self._apply_metric_labels(self._visual_scores, approx=True)
        if hasattr(self, "visual_gauge"):
            self.visual_gauge.reset()
            self.visual_gauge.set_status_text("พร้อมสำหรับการวิเคราะห์เชิงลึก")

    def _apply_metric_labels(
        self,
        scores: Optional[Dict[str, float]] = None,
        *,
        approx: bool = False,
        approx_keys: Optional[Iterable[str]] = None,
    ) -> None:
        display_scores = scores or {}
        approx_set = set(approx_keys or [])
        for key, label in self.visual_metric_labels.items():
            name = self.visual_metric_names.get(key, key)
            value = display_scores.get(key)
            if value is None:
                label.setText(f"{name}: —")
            else:
                is_approx = approx or key in approx_set
                prefix = "≈ " if is_approx else ""
                label.setText(f"{name}: {prefix}{value:.0f} / 100")

    def _update_visual_after_analysis(self, details: Dict[str, float], overall_score: float) -> None:
        if not hasattr(self, "visual_gauge"):
            return

        if self.selected_media_type != "image":
            self.visual_gauge.set_score(int(round(overall_score)))
            self.visual_gauge.set_status_text("ผลรวมจากโมดูลวิเคราะห์")
            return

        combined: Dict[str, float] = dict(self._visual_scores)
        for key in self.visual_metric_names:
            if key in details:
                raw_value = details.get(key)
                if isinstance(raw_value, bool):
                    continue
                numeric = self._safe_float(raw_value)
                combined[key] = numeric

        score = overall_score
        if (not score or score == 0.0) and not details and combined:
            score = float(
                aggregate_risk(
                    combined.get("chi_square", 0.0),
                    combined.get("ela", 0.0),
                    combined.get("histogram", 0.0),
                    combined.get("ml", 0.0),
                )
            )

        approx_keys = {key for key in combined.keys() if key not in details}
        self._apply_metric_labels(combined, approx_keys=approx_keys)
        self.visual_gauge.set_score(int(round(score)))
        self.visual_gauge.set_status_text("อัปเดตจากผลการวิเคราะห์ล่าสุด")

    # ------------------------------------------------------------------
    # Event handlers and worker integration
    # ------------------------------------------------------------------
    def _set_media_type(self, media_type: str) -> None:
        self.selected_media_type = media_type
        for key, button in self.media_type_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == media_type)
            button.blockSignals(False)

        if hasattr(self, "file_input"):
            placeholder = self.media_type_placeholders.get(media_type)
            if placeholder:
                self.file_input.setPlaceholderText(placeholder)

        support_text = self.media_type_supports.get(media_type)
        if support_text and hasattr(self, "support_label"):
            self.support_label.setText(support_text)

        self._update_visual_state_for_media(media_type)

    def _create_info_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("infoBox")
        label.setWordWrap(True)
        return label

    def _browse_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "เลือกไฟล์สำหรับวิเคราะห์",
            "",
            self.media_type_filters[self.selected_media_type],
        )
        if filename:
            self.file_path = Path(filename)
            self.file_input.setText(filename)
            if self.selected_media_type == "image":
                self._prepare_visual_preview()
                self.risk_score_widget.desc_label.setText(
                    f"พร้อมวิเคราะห์ไฟล์: {self.file_path.name}"
                )
            else:
                self._clear_visual_panel()
            self.analyze_button.setEnabled(True)

    def _start_analysis(self) -> None:
        if not self.file_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์ที่จะวิเคราะห์")
            return

        if hasattr(self, "visual_gauge") and self.selected_media_type == "image":
            self.visual_gauge.show_analyzing()

        self._reset_summary()
        self.live_log.clear()
        self._append_log("เริ่มต้นกระบวนการตรวจพิสูจน์ไฟล์", level="info")
        self._append_log(f"ไฟล์: {self.file_path.name}", level="info")

        self.active_checks = {
            "statistical": self.statistical_cb.isChecked(),
            "structural": self.structural_cb.isChecked(),
            "metadata": self.metadata_cb.isChecked(),
        }

        methods = self._resolve_methods()
        params = {
            "file_path": str(self.file_path),
            "methods": methods,
        }

        if self.active_checks.get("statistical"):
            self._append_log("กำหนดการทดสอบทางสถิติ (Chi-Square, RS, Histogram)", level="running")
        if self.active_checks.get("structural"):
            self._append_log("เตรียมการตรวจสอบโครงสร้างไฟล์ (EOF, Chunk Integrity)", level="running")
        if self.active_checks.get("metadata"):
            self._append_log("รวบรวมเมทาดาทาและแท็กที่เกี่ยวข้อง", level="running")

        self._set_busy(True)
        self.logger.info("Starting analysis for %s with methods %s", self.file_path, methods)
        self.parent_window.start_worker(
            "analyze",
            params,
            on_result=self._on_analysis_result,
            on_error=self._on_worker_error,
            on_finished=self._on_worker_finished,
        )

        worker = getattr(self.parent_window, "worker", None)
        if worker is not None:
            worker.status.connect(self._on_worker_status)

    def _resolve_methods(self) -> List[str]:
        methods: List[str] = []
        if self.active_checks.get("statistical"):
            methods.extend(["chi-square", "histogram"])
        if self.active_checks.get("structural"):
            methods.append("ela")
        if self.active_checks.get("metadata"):
            methods.append("ml")
        if not methods:
            methods = ["all"]
        seen = set()
        ordered: List[str] = []
        for method in methods:
            if method not in seen:
                ordered.append(method)
                seen.add(method)
        return ordered

    def _on_worker_status(self, message: str) -> None:
        self._append_log(message, level="status")

    def _on_analysis_result(self, result: Dict[str, object]) -> None:
        self._append_log("การวิเคราะห์เชิงลึกเสร็จสมบูรณ์", level="result")

        details = result.get("details", {}) if isinstance(result, dict) else {}
        if not isinstance(details, dict):
            details = {}

        score = self._safe_float(result.get("score", 0.0))
        level = str(result.get("level", "LOW")).upper()
        confidence = self._safe_float(result.get("confidence", 0.0))
        suspected_method = str(result.get("suspected_method", "ไม่พบวิธีการซ่อนที่ชัดเจน"))
        suspicious = bool(result.get("suspicious", False))
        insights = result.get("insights", []) if isinstance(result, dict) else []
        recommendation = str(result.get("recommendation", ""))

        description = self._build_score_description(score, level, suspected_method, confidence)
        palette = self._summary_palette(level, suspicious)
        self._apply_summary_palette(palette)
        self.summary_title.setText(palette["title"])
        self.summary_message.setText(description)

        self.risk_score_widget.set_score(int(round(score)), level, description, palette["accent"])
        self._update_visual_after_analysis(details, score)

        rows: List[Tuple[str, str, str]] = []
        rows.extend(self._build_statistical_rows(details))

        structural_info = (
            self._perform_structural_scan(self.file_path)
            if self.active_checks.get("structural")
            else None
        )
        metadata_info = (
            self._perform_metadata_scan(self.file_path)
            if self.active_checks.get("metadata")
            else None
        )

        if structural_info:
            rows.append(
                (
                    "Structural Analysis",
                    structural_info["result"],
                    structural_info["confidence"],
                )
            )
            if structural_info.get("log"):
                self._append_log(
                    structural_info["log"], level=structural_info.get("log_level", "result")
                )

        if metadata_info:
            rows.append(
                (
                    "Metadata Review",
                    metadata_info["result"],
                    metadata_info["confidence"],
                )
            )
            if metadata_info.get("log"):
                self._append_log(
                    metadata_info["log"], level=metadata_info.get("log_level", "result")
                )

        self._populate_table(rows)

        guidance_messages = self._build_guidance(
            recommendation,
            suspected_method,
            details,
            structural_info,
            metadata_info,
        )
        if guidance_messages:
            self.guidance_label.setText(
                "<ul>" + "".join(f"<li>{msg}</li>" for msg in guidance_messages) + "</ul>"
            )
            self.guidance_frame.setVisible(True)
        else:
            self.guidance_label.setText("ไม่พบข้อเสนอแนะเพิ่มเติม")
            self.guidance_frame.setVisible(False)

        if insights:
            for insight in insights:
                self._append_log(insight, level="insight")

        self.logger.info(
            "Analysis finished for %s -> score %.2f (%s) | suspected=%s | confidence=%.2f",
            self.file_path,
            score,
            level,
            suspected_method,
            confidence,
        )

    def _populate_table(self, rows: Iterable[Tuple[str, str, str]]) -> None:
        rows_list = list(rows)
        self.analysis_table.setRowCount(len(rows_list))
        for row_index, (technique, result_text, confidence) in enumerate(rows_list):
            for column_index, value in enumerate((technique, result_text, confidence)):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                if column_index == 2:
                    item.setTextAlignment(Qt.AlignCenter)
                self.analysis_table.setItem(row_index, column_index, item)

    def _build_statistical_rows(self, details: Dict[str, float]) -> List[Tuple[str, str, str]]:
        rows: List[Tuple[str, str, str]] = []
        mapping = {
            "chi_square": "Chi-Square Test",
            "histogram": "Histogram Analysis",
            "ela": "Error Level Analysis",
            "ml": "ML Detector",
        }
        for key, label in mapping.items():
            if key not in details:
                continue
            score = self._safe_float(details.get(key, 0.0))
            status, confidence = self._describe_score(score)
            rows.append((label, status, confidence))
        return rows

    def _build_guidance(
        self,
        recommendation: str,
        suspected_method: str,
        details: Dict[str, float],
        structural_info: Optional[Dict[str, str]],
        metadata_info: Optional[Dict[str, str]],
    ) -> List[str]:
        guidance: List[str] = []
        if recommendation:
            guidance.append(recommendation)

        chi_score = self._safe_float(details.get("chi_square", 0.0))
        histogram_score = self._safe_float(details.get("histogram", 0.0))
        ela_score = self._safe_float(details.get("ela", 0.0))
        ml_score = self._safe_float(details.get("ml", 0.0))

        if chi_score >= 60 or histogram_score >= 60:
            guidance.append(
                "ร่องรอยทางสถิติชี้ถึงเทคนิค LSB/LSP ให้ลองแท็บ 'Extract' ด้วยวิธี 'LSB Matching' หรือ 'PVD'"
            )
        if ela_score >= 60:
            guidance.append(
                "ELA สูงผิดปกติ: หากไฟล์เป็น JPEG ให้ทดลองถอดด้วยวิธี 'Transform Domain' หรือทำ Neutralize ก่อน"
            )
        if ml_score >= 60:
            guidance.append(
                "ตัวตรวจจับ ML ระบุสัญญาณขั้นสูง แนะนำให้รัน Extract ด้วยโหมด Adaptive เพื่อตรวจซ้ำ"
            )

        if structural_info and structural_info.get("status") == "alert":
            guidance.append(
                "ตรวจพบข้อมูลต่อท้ายไฟล์ ลองใช้แท็บ 'Extract' กับเทคนิค 'Tail Append' หรือสคริปต์ forensic"
            )
        if metadata_info and metadata_info.get("status") == "alert":
            guidance.append(
                "Metadata ผิดปกติ อาจมีข้อมูลซ่อนใน EXIF/ID3 ให้ใช้ Extract > Metadata Inspector หรือทำ Neutralize"
            )

        if suspected_method and "ไม่พบ" not in suspected_method:
            guidance.append(f"คาดว่าใช้วิธี: {suspected_method}")

        seen = set()
        unique_guidance = []
        for message in guidance:
            if message and message not in seen:
                unique_guidance.append(message)
                seen.add(message)
        return unique_guidance

    def _perform_structural_scan(self, file_path: Optional[Path]) -> Optional[Dict[str, str]]:
        if not file_path or not file_path.exists():
            return None
        info: Dict[str, str] = {
            "result": "ยังไม่ตรวจสอบ",
            "confidence": "—",
            "status": "neutral",
        }
        suffix = file_path.suffix.lower()
        try:
            data = file_path.read_bytes()
            if suffix == ".png":
                marker = data.rfind(b"IEND\xAE\x42\x60\x82")
                if marker != -1 and marker + 12 < len(data):
                    extra = len(data) - (marker + 12)
                    info.update(
                        {
                            "result": f"พบข้อมูลต่อท้ายไฟล์ ~{extra} ไบต์หลัง IEND",
                            "confidence": "92%",
                            "status": "alert",
                            "log": "[RESULT] EOF: พบข้อมูลต่อท้ายหลัง IEND",
                            "log_level": "warning",
                        }
                    )
                else:
                    info.update(
                        {
                            "result": "ไม่พบข้อมูลต่อท้ายไฟล์",
                            "confidence": "35%",
                            "log": "[RESULT] EOF: โครงสร้าง PNG ปกติ",
                            "log_level": "result",
                        }
                    )
            elif suffix in {".jpg", ".jpeg"}:
                marker = data.rfind(b"\xFF\xD9")
                if marker != -1 and marker + 2 < len(data):
                    extra = len(data) - (marker + 2)
                    info.update(
                        {
                            "result": f"พบข้อมูลต่อท้ายไฟล์ ~{extra} ไบต์หลัง FFD9",
                            "confidence": "88%",
                            "status": "alert",
                            "log": "[RESULT] EOF: พบข้อมูลหลัง JPEG EOI",
                            "log_level": "warning",
                        }
                    )
                else:
                    info.update(
                        {
                            "result": "ไม่พบข้อมูลต่อท้ายไฟล์",
                            "confidence": "35%",
                            "log": "[RESULT] EOF: โครงสร้าง JPEG ปกติ",
                            "log_level": "result",
                        }
                    )
            else:
                info.update(
                    {
                        "result": "ยังไม่มีสูตรวิเคราะห์ไฟล์ชนิดนี้",
                        "confidence": "—",
                        "log": "[INFO] Structural analysis รองรับเฉพาะ PNG/JPEG ณ ขณะนี้",
                        "log_level": "info",
                    }
                )
        except Exception as exc:  # pragma: no cover - IO failure
            self.logger.warning("Structural scan failed: %s", exc)
            info.update(
                {
                    "result": "โครงสร้างตรวจสอบไม่สำเร็จ",
                    "confidence": "—",
                    "status": "error",
                    "log": "[ERROR] Structural scan ไม่สำเร็จ",
                    "log_level": "error",
                }
            )
        return info

    def _perform_metadata_scan(self, file_path: Optional[Path]) -> Optional[Dict[str, str]]:
        if not file_path or not file_path.exists():
            return None
        info: Dict[str, str] = {
            "result": "ยังไม่ตรวจสอบ",
            "confidence": "—",
            "status": "neutral",
        }
        suffix = file_path.suffix.lower()
        try:
            if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
                with Image.open(file_path) as img:
                    metadata = img.getexif() if hasattr(img, "getexif") else {}
                    if metadata:
                        info.update(
                            {
                                "result": f"พบ EXIF/Metadata {len(metadata)} รายการ",
                                "confidence": "68%",
                                "status": "alert",
                                "log": "[RESULT] Metadata: ตรวจพบ EXIF หลายรายการ",
                                "log_level": "warning",
                            }
                        )
                    else:
                        info.update(
                            {
                                "result": "ไม่พบ Metadata ที่ผิดปกติ",
                                "confidence": "30%",
                                "log": "[RESULT] Metadata: ไม่พบ EXIF",
                                "log_level": "result",
                            }
                        )
            else:
                info.update(
                    {
                        "result": "ยังไม่มีตัวอ่านเมทาดาทาสำหรับไฟล์ชนิดนี้",
                        "confidence": "—",
                        "log": "[INFO] Metadata analysis จำกัดเฉพาะไฟล์ภาพ",
                        "log_level": "info",
                    }
                )
        except Exception as exc:  # pragma: no cover - IO failure
            self.logger.warning("Metadata scan failed: %s", exc)
            info.update(
                {
                    "result": "อ่าน Metadata ไม่สำเร็จ",
                    "confidence": "—",
                    "status": "error",
                    "log": "[ERROR] Metadata scan ไม่สำเร็จ",
                    "log_level": "error",
                }
            )
        return info

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _safe_float(self, value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _describe_score(self, score: float) -> Tuple[str, str]:
        if score >= 70:
            return ("พบความผิดปกติสูง", f"{score:.0f}%")
        if score >= 40:
            return ("น่าสงสัย", f"{score:.0f}%")
        return ("ปกติ", f"{score:.0f}%")

    def _summary_palette(self, level: str, suspicious: bool) -> Dict[str, str]:
        palette = {
            "LOW": {
                "bg": "#e8f5e9",
                "border": "#a5d6a7",
                "fg": "#1b5e20",
                "accent": "#2e7d32",
                "title": "ผลการวิเคราะห์: ไม่พบร่องรอยการซ่อนข้อมูล",
            },
            "MEDIUM": {
                "bg": "#fff8e1",
                "border": "#ffe082",
                "fg": "#ff8f00",
                "accent": "#ff9800",
                "title": "ผลการวิเคราะห์: พบจุดที่น่าสงสัย",
            },
            "HIGH": {
                "bg": "#ffebee",
                "border": "#ef9a9a",
                "fg": "#c62828",
                "accent": "#f44336",
                "title": "ผลการวิเคราะห์: มีความเป็นไปได้สูงว่าจะมีการซ่อนข้อมูล",
            },
            "CRITICAL": {
                "bg": "#ffebee",
                "border": "#ef5350",
                "fg": "#b71c1c",
                "accent": "#d32f2f",
                "title": "ผลการวิเคราะห์: ตรวจพบร่องรอยชัดเจน",
            },
        }
        default_palette = {
            "bg": "#f3f4f6",
            "border": "#d1d5db",
            "fg": "#111827",
            "accent": "#1976d2",
            "title": "ผลการวิเคราะห์: ไม่สามารถระบุระดับความเสี่ยง",
        }
        selected = palette.get(level, default_palette)
        if suspicious and level == "LOW":
            selected = palette.get("MEDIUM", default_palette)
        return selected

    def _apply_summary_palette(self, palette: Dict[str, str]) -> None:
        self.summary_container.setStyleSheet(
            "QFrame#summaryContainer {"
            f"background-color: {palette['bg']};"
            f"border: 1px solid {palette['border']};"
            "border-radius: 8px;"
            "padding: 16px;"
            "}"
        )
        self.summary_title.setStyleSheet(
            f"font-weight: bold; font-size: 15px; color: {palette['fg']};"
        )
        self.summary_message.setStyleSheet(f"color: {palette['fg']};")

    def _build_score_description(
        self, score: float, level: str, suspected_method: str, confidence: float
    ) -> str:
        parts = [f"คะแนนรวม {score:.0f}/100 ({level})"]
        if confidence:
            parts.append(f"ความมั่นใจของโมดูลวิเคราะห์ ~{confidence:.0f}%")
        if suspected_method and "ไม่พบ" not in suspected_method:
            parts.append(f"คาดว่าวิธีการซ่อน: {suspected_method}")
        else:
            parts.append("ยังไม่พบรูปแบบการซ่อนที่แน่ชัด")
        return " • ".join(parts)

    def _append_log(self, message: str, *, level: str = "info") -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color_map = {
            "info": "#60a5fa",
            "running": "#fbbf24",
            "status": "#c084fc",
            "result": "#22c55e",
            "warning": "#f97316",
            "error": "#f87171",
            "insight": "#38bdf8",
        }
        color = color_map.get(level, "#d1d5db")
        formatted = f"<span style='color:{color}'>[{timestamp}] {message}</span>"
        self.live_log.appendHtml(formatted)
        self.live_log.verticalScrollBar().setValue(self.live_log.verticalScrollBar().maximum())

    def _reset_summary(self) -> None:
        self.summary_title.setText("กำลังเตรียมผลการวิเคราะห์…")
        self.summary_message.setText("ระบบกำลังรวบรวมข้อมูลจากโมดูลต่าง ๆ")
        self.analysis_table.clearContents()
        self.analysis_table.setRowCount(0)
        self.guidance_frame.setVisible(False)
        self.risk_score_widget.set_score(0, "ANALYZING", "กำลังเตรียมข้อมูล", "#1E88E5")

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _on_worker_error(self, error: str) -> None:
        self._append_log(f"เกิดข้อผิดพลาด: {error}", level="error")
        QMessageBox.critical(self, "ข้อผิดพลาด", f"วิเคราะห์ล้มเหลว:\n{error}")
        self.logger.error("Analysis failed for %s: %s", self.file_path, error)
        self._set_busy(False)

    def _on_worker_finished(self) -> None:
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.analyze_button.setEnabled(not busy)
        self.analyze_button.setText("⏳ กำลังวิเคราะห์..." if busy else "🚀 เริ่มการวิเคราะห์อีกครั้ง")
