"""Embed tab implementation for the STEGOSIGHT GUI."""

from __future__ import annotations

import shutil
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
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from .common_widgets import InfoPanel, MethodCard
from .styles import apply_embed_styles
from utils.payloads import create_file_payload, create_text_payload


class EmbedTab(QWidget):
    """UI for the *Embed* functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_window = parent

        self.cover_path: Optional[Path] = None
        self.secret_path: Optional[Path] = None
        self.selected_method = "content_adaptive"
        self.selected_media_type = "image"
        self._current_secret_data: Optional[bytes] = None
        self._current_embed_params: Dict[str, object] = {}
        self._current_temp_path: Optional[Path] = None
        self._last_risk: Optional[Dict[str, object]] = None
        self._last_result: Optional[Dict[str, object]] = None

        self.method_definitions = self._build_method_definitions()
        self.method_cards: List[MethodCard] = []
        self.method_card_map: Dict[MethodCard, str] = {}
        self.media_type_buttons: Dict[str, QPushButton] = {}
        self.method_to_media: Dict[str, str] = {
            method_key: media_type
            for media_type, methods in self.method_definitions.items()
            for method_key in methods
        }
        self.media_type_supports = {
            "image": "รองรับ: PNG, JPEG, JPG, BMP",
            "audio": "รองรับ: WAV, MP3, FLAC",
            "video": "รองรับ: AVI, MP4, MKV, MOV, OGG, WMA, AAC",
        }
        self.media_type_filters = {
            "image": "ไฟล์ภาพ (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)",
            "audio": "ไฟล์เสียง (*.wav *.mp3 *.flac);;All Files (*.*)",
            "video": "ไฟล์วิดีโอ (*.avi *.mp4 *.mkv *.mov *.ogg *.wma *.aac);;All Files (*.*)",
        }
        self.media_type_placeholders = {
            "image": "เลือกไฟล์ภาพที่ต้องการใช้เป็นต้นฉบับ...",
            "audio": "เลือกไฟล์เสียงที่ต้องการใช้เป็นต้นฉบับ...",
            "video": "เลือกไฟล์วิดีโอที่ต้องการใช้เป็นต้นฉบับ...",
        }

        self._init_ui()
        apply_embed_styles(self)

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_method_definitions(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        return {
            "image": {
                "content_adaptive": {
                    "title": "✨ Content-Adaptive (แนะนำ)",
                    "desc": "วิเคราะห์ขอบและพื้นผิวเพื่อเลือกพื้นที่ฝังที่แนบเนียน",
                },
                "lsb": {
                    "title": "🔹 LSB Matching",
                    "desc": "ปรับ LSB เพื่อลดความผิดปกติทางสถิติ (เหมาะกับ PNG/BMP)",
                },
                "pvd": {
                    "title": "🔸 Pixel Value Differencing",
                    "desc": "กำหนดจำนวนบิตจากความต่างพิกเซล เพิ่มปริมาณข้อมูล",
                },
                "dct": {
                    "title": "📊 Discrete Cosine Transform",
                    "desc": "ฝังข้อมูลในสัมประสิทธิ์ DCT สำหรับ JPEG ทนการบีบอัดซ้ำ",
                },
                "append": {
                    "title": "📎 ต่อท้ายไฟล์ (Tail Append)",
                    "desc": "พ่วง payload ต่อท้ายไฟล์ต้นฉบับ (เหมาะกับ PNG/BMP)",
                },
            },
            "audio": {
                "audio_adaptive": {
                    "title": "✨ Adaptive Audio",
                    "desc": "วิเคราะห์ไดนามิกเสียง เลือกตำแหน่งฝังที่แนบเนียน",
                },
                "audio_lsb": {
                    "title": "🎧 LSB ในสัญญาณเสียง",
                    "desc": "ซ่อนข้อมูลด้วย LSB สำหรับ WAV/MP3/FLAC",
                },
                "audio_metadata": {
                    "title": "🏷️ Metadata Tagging",
                    "desc": "ฝังข้อมูลใน Meta Tag (ID3/Tag สำหรับ MP3/FLAC)",
                },
            },
            "video": {
                "video_adaptive": {
                    "title": "✨ Adaptive Video",
                    "desc": "ประเมินเฟรมวิดีโอและเลือกพื้นที่ที่ยากต่อการสังเกต",
                },
                "video_lsb": {
                    "title": "🎞️ Frame LSB",
                    "desc": "ซ่อนข้อมูลทีละเฟรมด้วย LSB (รองรับ MP4/AVI/MKV/MOV)",
                },
                "video_metadata": {
                    "title": "🏷️ Metadata Tagging",
                    "desc": "ฝังข้อมูลในเมทาดาทาของไฟล์วิดีโอ (MP4/MKV/MOV)",
                },
            },
        }

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        left_layout.addWidget(self._create_cover_file_group())
        left_layout.addWidget(self._create_secret_data_group())
        left_layout.addWidget(self._create_method_group())
        left_layout.addWidget(self._create_encryption_group())
        left_layout.addWidget(self._create_auto_analysis_group())
        left_layout.addStretch()

        left_scroll.setWidget(left_widget)
        splitter.addWidget(left_scroll)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(self._create_preview_group())
        right_layout.addStretch()
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 50)
        splitter.setStretchFactor(1, 50)
        main_layout.addWidget(splitter)

        self.action_btn = QPushButton("🔒 เริ่มซ่อนข้อมูล")
        self.action_btn.setObjectName("actionButton")
        self.action_btn.clicked.connect(self._start_embed)
        main_layout.addWidget(self.action_btn, 0, Qt.AlignRight)

    def _create_cover_file_group(self) -> QGroupBox:
        group = QGroupBox("1. เลือกไฟล์ต้นฉบับ (Cover File)")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_row.addWidget(QLabel("เลือกประเภทไฟล์ต้นฉบับ:"))
        for key, label in (
            ("image", "🖼️ ไฟล์ภาพ"),
            ("audio", "🎧 ไฟล์เสียง"),
            ("video", "🎞️ ไฟล์วิดีโอ"),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("toggleButton")
            btn.setChecked(key == self.selected_media_type)
            btn.clicked.connect(lambda _, media=key: self._set_media_type(media))
            self.media_type_buttons[key] = btn
            type_row.addWidget(btn)

        type_row.addStretch()
        layout.addLayout(type_row)

        file_row = QHBoxLayout()
        self.cover_file_input = QLineEdit()
        placeholder = self.media_type_placeholders.get(
            self.selected_media_type, "เลือกไฟล์ภาพ, เสียง, หรือวิดีโอ..."
        )
        self.cover_file_input.setPlaceholderText(placeholder)
        self.cover_file_input.setReadOnly(True)
        browse_btn = QPushButton("เลือกไฟล์")
        browse_btn.clicked.connect(self._browse_cover_file)
        file_row.addWidget(self.cover_file_input)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        info_text = self.media_type_supports.get(
            self.selected_media_type, "รองรับ: PNG, JPEG, BMP, WAV, MP4"
        )
        self.cover_file_info = QLabel(info_text)
        self.cover_file_info.setObjectName("infoBox")
        self.cover_file_info.setWordWrap(True)
        layout.addWidget(self.cover_file_info)
        return group

    def _create_secret_data_group(self) -> QGroupBox:
        group = QGroupBox("2. เลือกข้อมูลลับ (Secret Data)")
        layout = QVBoxLayout(group)

        toggle_layout = QHBoxLayout()
        self.btn_secret_file = QPushButton("📄 จากไฟล์")
        self.btn_secret_text = QPushButton("📝 พิมพ์ข้อความ")
        for button in (self.btn_secret_file, self.btn_secret_text):
            button.setCheckable(True)
            button.setObjectName("toggleButton")
        self.btn_secret_file.setChecked(True)
        toggle_layout.addWidget(self.btn_secret_file)
        toggle_layout.addWidget(self.btn_secret_text)
        toggle_layout.addStretch()

        self.secret_stack = QStackedWidget()

        file_widget = QWidget()
        file_layout = QHBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self.secret_file_input = QLineEdit()
        self.secret_file_input.setPlaceholderText("เลือกไฟล์ที่ต้องการซ่อน...")
        self.secret_file_input.setReadOnly(True)
        browse_btn = QPushButton("เลือกไฟล์")
        browse_btn.clicked.connect(self._browse_secret_file)
        file_layout.addWidget(self.secret_file_input)
        file_layout.addWidget(browse_btn)

        self.secret_text_edit = QTextEdit()
        self.secret_text_edit.setPlaceholderText("พิมพ์ข้อความที่ต้องการซ่อน...")

        self.secret_stack.addWidget(file_widget)
        self.secret_stack.addWidget(self.secret_text_edit)

        self.btn_secret_file.clicked.connect(lambda: self._set_secret_mode(0))
        self.btn_secret_text.clicked.connect(lambda: self._set_secret_mode(1))

        layout.addLayout(toggle_layout)
        layout.addWidget(self.secret_stack)

        info = QLabel("รองรับไฟล์ได้ทุกประเภท")
        info.setObjectName("infoBox")
        info.setWordWrap(True)
        layout.addWidget(info)
        return group

    def _create_method_group(self) -> QGroupBox:
        group = QGroupBox("3. เลือกวิธีการซ่อนข้อมูล")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.method_container = QWidget()
        self.method_container_layout = QVBoxLayout(self.method_container)
        self.method_container_layout.setContentsMargins(0, 0, 0, 0)
        self.method_container_layout.setSpacing(10)
        layout.addWidget(self.method_container)

        self._set_media_type(self.selected_media_type)
        return group

    def _set_media_type(self, media_type: str, *, keep_selection: Optional[str] = None) -> None:
        if media_type not in self.method_definitions:
            return

        self.selected_media_type = media_type
        for key, button in self.media_type_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == media_type)
            button.blockSignals(False)

        placeholder = self.media_type_placeholders.get(media_type)
        if placeholder:
            self.cover_file_input.setPlaceholderText(placeholder)

        info_text = self.media_type_supports.get(media_type)
        if info_text:
            self.cover_file_info.setText(info_text)

        self._populate_method_cards(media_type, keep_selection=keep_selection)

    def _populate_method_cards(
        self, media_type: str, *, keep_selection: Optional[str] = None
    ) -> None:
        if not hasattr(self, "method_container_layout"):
            return

        while self.method_container_layout.count():
            item = self.method_container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        methods = self.method_definitions.get(media_type, {})
        self.method_cards = []
        self.method_card_map = {}

        for key, meta in methods.items():
            card = MethodCard(meta["title"], meta["desc"])
            card.clicked.connect(lambda _, c=card: self._select_method_card(c))
            self.method_container_layout.addWidget(card)
            self.method_cards.append(card)
            self.method_card_map[card] = key

        self.method_container_layout.addStretch()

        if not methods:
            self.selected_method = ""
            return

        if keep_selection and keep_selection in methods:
            target = keep_selection
        elif self.selected_method in methods:
            target = self.selected_method
        else:
            target = next(iter(methods))

        self._update_card_selection(target)

    def _update_card_selection(self, method_key: str) -> None:
        for card in self.method_cards:
            selected = self.method_card_map.get(card) == method_key
            card.setSelected(selected)
        if method_key in self.method_to_media:
            self.selected_method = method_key

    def _create_encryption_group(self) -> QGroupBox:
        group = QGroupBox("4. การเข้ารหัส (Encryption)")
        layout = QVBoxLayout(group)

        self.use_encryption_cb = QCheckBox("ใช้การเข้ารหัส AES-256-GCM")
        self.use_encryption_cb.setChecked(True)
        layout.addWidget(self.use_encryption_cb)

        pwd_row = QHBoxLayout()
        pwd_row.addWidget(QLabel("รหัสผ่าน:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("กรอกรหัสผ่าน...")
        pwd_row.addWidget(self.password_input)

        confirm_row = QHBoxLayout()
        confirm_row.addWidget(QLabel("ยืนยัน:"))
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setPlaceholderText("ยืนยันรหัสผ่าน...")
        confirm_row.addWidget(self.confirm_password_input)

        self.use_encryption_cb.toggled.connect(self.password_input.setEnabled)
        self.use_encryption_cb.toggled.connect(self.confirm_password_input.setEnabled)

        layout.addLayout(pwd_row)
        layout.addLayout(confirm_row)

        info = QLabel("ใช้ AES-256-GCM + Argon2id KDF เพื่อความปลอดภัยสูงสุด")
        info.setObjectName("infoBox")
        info.setWordWrap(True)
        layout.addWidget(info)
        return group

    def _create_auto_analysis_group(self) -> QGroupBox:
        group = QGroupBox("5. การวิเคราะห์อัตโนมัติ")
        layout = QVBoxLayout(group)
        self.auto_analyze_cb = QCheckBox("วิเคราะห์ความเสี่ยงอัตโนมัติหลังซ่อนข้อมูล")
        self.auto_analyze_cb.setChecked(True)
        self.auto_neutralize_cb = QCheckBox("ทำให้เป็นกลางอัตโนมัติหากพบความเสี่ยงสูง")
        layout.addWidget(self.auto_analyze_cb)
        layout.addWidget(self.auto_neutralize_cb)
        return group

    def _create_preview_group(self) -> QGroupBox:
        group = QGroupBox("ตัวอย่างไฟล์")
        layout = QVBoxLayout(group)
        self.preview_label = QLabel("ยังไม่ได้เลือกไฟล์")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(250)
        self.preview_label.setObjectName("previewArea")
        layout.addWidget(self.preview_label)

        panel, labels = self._create_info_panel(["ชื่อไฟล์", "ขนาด", "ประเภท", "ความจุที่ว่าง"])
        self.file_info_panel = panel
        self.info_labels = labels
        layout.addWidget(panel)
        return group

    def _create_info_panel(self, labels):
        panel = InfoPanel(labels)
        return panel, panel.value_labels

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------
    def _set_secret_mode(self, index: int) -> None:
        self.secret_stack.setCurrentIndex(index)
        self.btn_secret_file.setChecked(index == 0)
        self.btn_secret_text.setChecked(index == 1)

    def _select_method_card(self, card: MethodCard) -> None:
        for item in self.method_cards:
            item.setSelected(item is card)
        method_key = self.method_card_map.get(card)
        if method_key:
            self.selected_method = method_key

    def _get_cover_file_filter(self) -> str:
        return self.media_type_filters.get(self.selected_media_type, "All Files (*.*)")

    def _infer_media_type_from_suffix(self, suffix: str) -> Optional[str]:
        suffix = suffix.lower()
        image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}
        audio_exts = {".wav", ".mp3", ".flac", ".aac", ".ogg", ".wma"}
        video_exts = {
            ".avi",
            ".mp4",
            ".mkv",
            ".mov",
            ".ogv",
            ".wmv",
            ".m4v",
        }

        if suffix in image_exts:
            return "image"
        if suffix in audio_exts:
            return "audio"
        if suffix in video_exts or suffix in {".mpg", ".mpeg"}:
            return "video"
        return None

    def _browse_cover_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "เลือกไฟล์ต้นฉบับ",
            "",
            self._get_cover_file_filter(),
        )
        if filename:
            self.cover_path = Path(filename)
            inferred = self._infer_media_type_from_suffix(self.cover_path.suffix)
            if inferred and inferred != self.selected_media_type:
                self._set_media_type(inferred)
            self.cover_file_input.setText(filename)
            self._update_cover_preview()

    def _browse_secret_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์ที่ต้องการซ่อน", "", "All Files (*.*)")
        if filename:
            self.secret_path = Path(filename)
            self.secret_file_input.setText(filename)

    def _update_cover_preview(self) -> None:
        if not self.cover_path:
            return
        self.info_labels["ชื่อไฟล์"].setText(self.cover_path.name)
        size_kb = self.cover_path.stat().st_size / 1024
        self.info_labels["ขนาด"].setText(f"{size_kb:.2f} KB")
        self.info_labels["ประเภท"].setText(self.cover_path.suffix.upper() or "—")
        estimated_capacity = max(int(self.cover_path.stat().st_size * 0.2 / 1024), 1)
        self.info_labels["ความจุที่ว่าง"].setText(f"~{estimated_capacity} KB (ประมาณ)")

        pixmap = QPixmap(str(self.cover_path))
        if not pixmap.isNull():
            self.preview_label.setPixmap(
                pixmap.scaled(
                    self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        else:
            self.preview_label.setText(f"ไฟล์: {self.cover_path.name}\nประเภท: {self.cover_path.suffix}")

    def _start_embed(self) -> None:
        if not self.cover_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์ต้นฉบับ")
            return

        secret_payload: Optional[bytes] = None
        secret_mode = self.secret_stack.currentIndex()
        secret_text: Optional[str] = None
        if secret_mode == 0:
            if not self.secret_path:
                QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์ข้อมูลลับ")
                return
            raw_bytes = self.secret_path.read_bytes()
        else:
            text = self.secret_text_edit.toPlainText()
            if not text.strip():
                QMessageBox.warning(self, "คำเตือน", "กรุณากรอกข้อความที่ต้องการซ่อน")
                return
            secret_text = text
            raw_bytes = text.encode("utf-8")

        password: Optional[str] = None
        if self.use_encryption_cb.isChecked():
            pwd = self.password_input.text()
            confirm = self.confirm_password_input.text()
            if not pwd:
                QMessageBox.warning(self, "คำเตือน", "กรุณากรอกรหัสผ่าน")
                return
            if pwd != confirm:
                QMessageBox.warning(self, "คำเตือน", "รหัสผ่านไม่ตรงกัน")
                return
            password = pwd

        if secret_mode == 0 and self.secret_path:
            secret_payload = create_file_payload(
                raw_bytes,
                name=self.secret_path.name,
                encrypted=bool(password),
            )
        elif secret_text is not None:
            secret_payload = create_text_payload(
                secret_text,
                encrypted=bool(password),
            )

        if not secret_payload:
            QMessageBox.warning(self, "คำเตือน", "ไม่พบข้อมูลที่จะซ่อน")
            return

        self._current_secret_data = secret_payload
        self._current_embed_params = {
            "cover_path": str(self.cover_path),
            "password": password,
            "method": self.selected_method,
            "media_type": self.selected_media_type,
            "options": {},
            "auto_analyze": self.auto_analyze_cb.isChecked(),
            "auto_neutralize": self.auto_neutralize_cb.isChecked(),
        }

        self._cleanup_temp_file()
        self._run_embed_worker()

    def _run_embed_worker(self) -> None:
        if not self._current_secret_data or not self._current_embed_params:
            QMessageBox.warning(self, "คำเตือน", "ไม่มีข้อมูลสำหรับการซ่อน")
            return

        params = dict(self._current_embed_params)
        params["secret_data"] = self._current_secret_data

        self._set_busy(True)
        self.parent_window.start_worker(
            "embed",
            params,
            on_result=self._on_embed_result,
            on_error=self._on_worker_error,
            on_finished=self._on_worker_finished,
        )

    def _on_embed_result(self, result: Dict[str, object]) -> None:
        self._last_result = result

        stego_path = result.get("stego_path")
        if not stego_path:
            QMessageBox.warning(self, "คำเตือน", "ไม่พบไฟล์ผลลัพธ์จากการซ่อน")
            return

        temp_path = Path(stego_path)
        self._current_temp_path = temp_path
        risk = result.get("risk_score") if isinstance(result.get("risk_score"), dict) else None
        self._last_risk = risk

        media_type = result.get("media_type")
        if isinstance(media_type, str):
            self._current_embed_params["media_type"] = media_type

        method_used = result.get("method", self._current_embed_params.get("method", self.selected_method))
        self._current_embed_params["method"] = method_used
        self._current_embed_params["options"] = result.get("options") or self._current_embed_params.get("options", {})
        self._update_method_selection(method_used)

        self._show_risk_confirmation(temp_path, risk, result)

    def _on_worker_error(self, error: str) -> None:
        QMessageBox.critical(self, "ข้อผิดพลาด", f"เกิดข้อผิดพลาด:\n{error}")
        self._set_busy(False)

    def _on_worker_finished(self) -> None:
        self._set_busy(False)

    def _update_method_selection(self, method_key: str) -> None:
        target_media = self.method_to_media.get(method_key)
        if target_media and target_media != self.selected_media_type:
            self._set_media_type(target_media, keep_selection=method_key)
            return

        if target_media is None:
            return

        self._update_card_selection(method_key)

    def _show_risk_confirmation(
        self, temp_path: Path, risk: Optional[Dict[str, object]], result: Dict[str, object]
    ) -> None:
        score_text = "—"
        level_text = "—"
        if risk:
            score_text = str(risk.get("score", "—"))
            level_text = str(risk.get("level", "—"))

        message = (
            f"ซ่อนข้อมูลสำเร็จ!\n\nคะแนนความเสี่ยง: {score_text}\nระดับ: {level_text}"
        )

        dialog = QMessageBox(self)
        dialog.setWindowTitle("ผลการประเมินความเสี่ยง")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText(message)
        dialog.setInformativeText("ต้องการบันทึกไฟล์นี้หรือไม่?")

        save_button = dialog.addButton("บันทึก...", QMessageBox.AcceptRole)
        improve_button = dialog.addButton("ปรับปรุงความแนบเนียน", QMessageBox.ActionRole)
        dialog.setDefaultButton(save_button)
        dialog.exec_()

        clicked = dialog.clickedButton()
        if clicked is save_button:
            self._prompt_save_file(temp_path, risk)
        elif clicked is improve_button:
            self._improve_and_retry(risk, result)
        else:
            # หากปิดหน้าต่าง ให้เก็บไฟล์ชั่วคราวไว้ให้ผู้ใช้ตัดสินใจภายหลัง
            pass

    def _prompt_save_file(self, temp_path: Path, risk: Optional[Dict[str, object]]) -> None:
        if not self.cover_path:
            QMessageBox.warning(self, "คำเตือน", "ไม่พบไฟล์ต้นฉบับสำหรับตั้งชื่อผลลัพธ์")
            return

        default_name = f"{self.cover_path.stem}_stego{temp_path.suffix}"
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "บันทึกไฟล์ที่ซ่อนข้อมูล",
            str(self.cover_path.parent / default_name),
            "All Files (*.*)",
        )

        if not target_path:
            return

        try:
            shutil.copyfile(temp_path, target_path)
        except Exception as exc:
            QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถบันทึกไฟล์ได้:\n{exc}")
            return

        self._cleanup_temp_file()

        message = f"บันทึกไฟล์เรียบร้อยแล้วที่:\n{target_path}"
        if risk:
            message += (
                f"\n\nคะแนนความเสี่ยง: {risk.get('score', '—')}"
                f"\nระดับ: {risk.get('level', '—')}"
            )
        QMessageBox.information(self, "สำเร็จ", message)

    def _improve_and_retry(
        self, risk: Optional[Dict[str, object]], result: Dict[str, object]
    ) -> None:
        improved = self._apply_improvements(risk, result)
        if not improved:
            QMessageBox.information(
                self,
                "ข้อมูล",
                "ไม่สามารถปรับปรุงพารามิเตอร์เพิ่มเติมได้ ลองเลือกไฟล์ต้นฉบับอื่น",
            )
            return

        self._cleanup_temp_file()
        self._run_embed_worker()

    def _apply_improvements(
        self, risk: Optional[Dict[str, object]], result: Dict[str, object]
    ) -> bool:
        if not self._current_embed_params:
            return False

        params = self._current_embed_params
        options = dict(params.get("options") or {})
        current_method = params.get("method", self.selected_method)
        improved = False

        if current_method in {"audio_adaptive", "audio_lsb", "video_adaptive", "video_lsb"}:
            return False

        recommendation = result.get("recommendation")
        if not recommendation:
            try:
                from steganography_module.adaptive import AdaptiveSteganography

                adaptive = AdaptiveSteganography()
                recommendation = adaptive.get_recommended_settings(
                    Path(params["cover_path"]), self._current_secret_data or b""
                )
            except Exception:
                recommendation = None

        if recommendation:
            recommended_method = recommendation.get("method", current_method)
            if recommended_method and recommended_method != current_method:
                current_method = recommended_method
                params["method"] = recommended_method
                improved = True

        # Method-specific refinements
        if current_method == "lsb":
            bits = options.get("lsb_bits", 1)
            if bits > 1:
                options["lsb_bits"] = 1
                improved = True
            mode = options.get("lsb_mode")
            if mode != "adaptive":
                options["lsb_mode"] = "adaptive"
                improved = True
        elif current_method == "pvd":
            pair_skip = options.get("pair_skip", 1)
            if pair_skip < 2:
                options["pair_skip"] = 2
                improved = True
        elif current_method == "dct":
            coeffs = options.get("coefficients") or []
            if not coeffs:
                options["coefficients"] = [(4, 3)]
                improved = True
            elif len(coeffs) > 1:
                options["coefficients"] = [coeffs[0]]
                improved = True

        if not improved and current_method != "adaptive":
            params["method"] = "adaptive"
            params["options"] = {}
            self._update_method_selection("adaptive")
            return True

        params["method"] = current_method
        params["options"] = options
        self._update_method_selection(current_method)
        return improved

    def _set_busy(self, busy: bool) -> None:
        self.action_btn.setEnabled(not busy)

    def _cleanup_temp_file(self) -> None:
        if self._current_temp_path and self._current_temp_path.exists():
            try:
                self._current_temp_path.unlink()
            except Exception:
                pass
        self._current_temp_path = None
