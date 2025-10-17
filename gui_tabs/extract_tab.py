"""Extract tab implementation for the STEGOSIGHT GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

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
    QCheckBox,
    QStackedWidget,
)

from .common_widgets import InfoPanel, MethodCard
from utils.payloads import unpack_payload


class ExtractTab(QWidget):
    """UI for the *Extract* functionality."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_window = parent

        self.stego_path: Optional[Path] = None
        self.extracted_data: Optional[bytes] = None
        self.extracted_payload: Optional[Dict[str, Any]] = None
        self._is_busy = False

        self.selected_media_type = "image"
        self.selected_method = "adaptive"
        self.method_definitions = self._build_method_definitions()
        self.method_cards: List[MethodCard] = []
        self.method_card_map: Dict[MethodCard, str] = {}
        self.media_type_buttons: Dict[str, QPushButton] = {}

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
            "image": "เลือกไฟล์ภาพที่คาดว่าถูกซ่อนข้อมูล...",
            "audio": "เลือกไฟล์เสียงที่คาดว่าถูกซ่อนข้อมูล...",
            "video": "เลือกไฟล์วิดีโอที่คาดว่าถูกซ่อนข้อมูล...",
        }
        self.extension_media_map = {
            ".png": "image",
            ".jpg": "image",
            ".jpeg": "image",
            ".bmp": "image",
            ".wav": "audio",
            ".mp3": "audio",
            ".flac": "audio",
            ".avi": "video",
            ".mp4": "video",
            ".mkv": "video",
            ".mov": "video",
            ".ogg": "video",
            ".wma": "video",
            ".aac": "video",
        }
        self.method_to_media: Dict[str, str] = {
            method_key: media_type
            for media_type, methods in self.method_definitions.items()
            for method_key in methods
        }

        self._init_ui()

    # ------------------------------------------------------------------
    def _build_method_definitions(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        return {
            "image": {
                "adaptive": {
                    "title": "✨ ตรวจจับอัตโนมัติ (แนะนำ)",
                    "desc": "ให้ระบบทดลอง LSB, PVD, DCT และ Tail Append ให้อัตโนมัติ",
                },
                "lsb": {
                    "title": "🔹 LSB Matching",
                    "desc": "ดึงข้อมูลจากการฝังแบบ LSB ในภาพ (เหมาะกับ PNG/BMP)",
                },
                "pvd": {
                    "title": "🔸 Pixel Value Differencing",
                    "desc": "ใช้ความต่างของพิกเซลเพื่อตีความบิตที่ซ่อนอยู่",
                },
                "dct": {
                    "title": "📊 Discrete Cosine Transform",
                    "desc": "กู้ข้อมูลที่ฝังในสัมประสิทธิ์ DCT ของไฟล์ JPEG",
                },
                "append": {
                    "title": "📎 Tail Append",
                    "desc": "ตรวจสอบว่ามีการต่อท้าย payload ต่อจากไฟล์ภาพหรือไม่",
                },
            },
            "audio": {
                "audio_adaptive": {
                    "title": "✨ ตรวจจับอัตโนมัติ",
                    "desc": "รองรับไฟล์เสียงที่ฝังด้วยเทคนิค LSB ของ STEGOSIGHT",
                },
                "audio_lsb": {
                    "title": "🎧 LSB ในสัญญาณเสียง",
                    "desc": "ดึงข้อมูลที่ซ่อนในบิตต่ำสุดของสัญญาณ PCM",
                },
            },
            "video": {
                "video_adaptive": {
                    "title": "✨ ตรวจจับอัตโนมัติ",
                    "desc": "ลองกู้ข้อมูลจากเฟรมวิดีโอโดยอัตโนมัติ",
                },
                "video_lsb": {
                    "title": "🎞️ Frame LSB",
                    "desc": "ดึงข้อมูลจากบิตต่ำสุดของแต่ละพิกเซลในเฟรมวิดีโอ",
                },
            },
        }

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
        group = QGroupBox("1. เลือกไฟล์สื่อที่ต้องการตรวจสอบ")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_row.addWidget(QLabel("ประเภทสื่อ:"))
        for key, label in (
            ("image", "🖼️ ภาพ"),
            ("audio", "🎧 เสียง"),
            ("video", "🎞️ วิดีโอ"),
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
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText(
            self.media_type_placeholders.get(self.selected_media_type, "เลือกไฟล์ที่ต้องการดึงข้อมูล...")
        )
        self.file_input.setReadOnly(True)
        browse_btn = QPushButton("เลือกไฟล์")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.file_input)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        self.file_support_label = QLabel(
            self.media_type_supports.get(self.selected_media_type, "รองรับไฟล์ที่สร้างโดย STEGOSIGHT")
        )
        self.file_support_label.setObjectName("infoBox")
        self.file_support_label.setWordWrap(True)
        layout.addWidget(self.file_support_label)

        return group

    def _create_method_group(self) -> QGroupBox:
        group = QGroupBox("2. เลือกวิธีการดึงข้อมูล")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        desc = QLabel(
            "เลือกเทคนิคที่ใช้ซ่อนข้อมูลให้ตรงกับตอนฝัง หรือใช้โหมดตรวจจับอัตโนมัติ"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.method_container = QWidget()
        self.method_container_layout = QVBoxLayout(self.method_container)
        self.method_container_layout.setContentsMargins(0, 0, 0, 0)
        self.method_container_layout.setSpacing(10)
        layout.addWidget(self.method_container)

        self._set_media_type(self.selected_media_type)

        hint = QLabel("ระบบจะทดลองหลายวิธีหากเลือกโหมดตรวจจับอัตโนมัติ")
        hint.setObjectName("infoBox")
        hint.setWordWrap(True)
        layout.addWidget(hint)
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
            self.file_input.setPlaceholderText(placeholder)

        support = self.media_type_supports.get(media_type)
        if support:
            self.file_support_label.setText(support)

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

    def _select_method_card(self, card: MethodCard) -> None:
        method_key = self.method_card_map.get(card)
        if not method_key:
            return

        target_media = self.method_to_media.get(method_key)
        if target_media and target_media != self.selected_media_type:
            self._set_media_type(target_media, keep_selection=method_key)
            return

        self._update_card_selection(method_key)

    def _update_card_selection(self, method_key: str) -> None:
        for card in self.method_cards:
            card.setSelected(self.method_card_map.get(card) == method_key)
        if method_key in self.method_to_media:
            self.selected_method = method_key

    def _create_decryption_group(self) -> QGroupBox:
        group = QGroupBox("3. การถอดรหัส (Decryption)")
        layout = QVBoxLayout(group)

        self.encrypted_cb = QCheckBox("ข้อมูลถูกเข้ารหัส (ต้องใช้รหัสผ่าน)")
        self.encrypted_cb.setChecked(False)
        layout.addWidget(self.encrypted_cb)

        pwd_row = QHBoxLayout()
        pwd_row.addWidget(QLabel("รหัสผ่าน:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("กรอกรหัสผ่าน...")
        self.password_input.setEnabled(False)
        pwd_row.addWidget(self.password_input)
        layout.addLayout(pwd_row)

        self.encrypted_cb.toggled.connect(self.password_input.setEnabled)
        return group

    def _create_result_group(self) -> QGroupBox:
        group = QGroupBox("4. ผลลัพธ์")
        layout = QVBoxLayout(group)

        self.result_stack = QStackedWidget()

        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        self.result_text = QTextEdit()
        self.result_text.setPlaceholderText("ข้อมูลที่ดึงออกมาจะแสดงที่นี่...")
        self.result_text.setReadOnly(True)
        text_layout.addWidget(self.result_text)
        self.result_stack.addWidget(text_widget)

        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_panel, file_labels = self._create_info_panel(["ชื่อไฟล์", "สกุลไฟล์", "ขนาด"])
        self.file_result_panel = file_panel
        self.file_result_labels = file_labels
        file_layout.addWidget(file_panel)
        self.file_hint_label = QLabel("ข้อมูลไฟล์ที่ดึงได้จะแสดงที่นี่")
        self.file_hint_label.setObjectName("infoBox")
        self.file_hint_label.setWordWrap(True)
        file_layout.addWidget(self.file_hint_label)
        file_layout.addStretch()
        self.result_stack.addWidget(file_widget)

        layout.addWidget(self.result_stack)
        self.result_stack.setCurrentIndex(0)

        self.save_btn = QPushButton("💾 บันทึกเป็นไฟล์")
        self.save_btn.clicked.connect(self._save_extracted)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn, 0, Qt.AlignRight)
        return group

    def _create_preview_group(self) -> QGroupBox:
        group = QGroupBox("ตัวอย่างไฟล์")
        layout = QVBoxLayout(group)

        self.preview_label = QLabel("ยังไม่ได้เลือกไฟล์")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setObjectName("previewArea")
        layout.addWidget(self.preview_label)

        panel, labels = self._create_info_panel(["ชื่อไฟล์", "ขนาด", "ประเภท", "สถานะ"])
        self.file_info_panel = panel
        self.info_labels = labels
        layout.addWidget(panel)
        return group

    def _create_details_group(self) -> QGroupBox:
        group = QGroupBox("ข้อมูลการดึง")
        layout = QVBoxLayout(group)
        panel, labels = self._create_info_panel(
            ["สื่อที่ตรวจสอบ", "วิธีการตรวจพบ", "ขนาดข้อมูล", "สถานะการเข้ารหัส", "วิธีที่ลอง"]
        )
        self.details_panel = panel
        self.details_labels = labels
        layout.addWidget(panel)
        return group

    def _create_info_panel(self, labels):
        panel = InfoPanel(labels)
        return panel, panel.value_labels

    def _reset_results(self) -> None:
        self.extracted_data = None
        self.extracted_payload = None
        self.result_text.clear()
        self.result_stack.setCurrentIndex(0)
        for label in self.file_result_labels.values():
            label.setText("—")
        self.file_hint_label.setText("ข้อมูลไฟล์ที่ดึงได้จะแสดงที่นี่")
        for label in self.details_labels.values():
            label.setText("—")
        self._update_save_state()

    def _update_save_state(self) -> None:
        if hasattr(self, "save_btn"):
            can_save = self.extracted_payload is not None and not self._is_busy
            self.save_btn.setEnabled(can_save)

    def _format_size(self, size: int) -> str:
        if size <= 0:
            return "0 bytes"
        units = ["bytes", "KB", "MB", "GB", "TB"]
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                if unit == "bytes":
                    return f"{int(value)} bytes"
                return f"{value:.2f} {unit}"
            value /= 1024
        return f"{size} bytes"

    # ------------------------------------------------------------------
    def _browse_file(self) -> None:
        file_filter = self.media_type_filters.get(self.selected_media_type, "All Files (*.*)")
        filename, _ = QFileDialog.getOpenFileName(
            self, "เลือกไฟล์ที่ซ่อนข้อมูล", "", file_filter
        )
        if filename:
            self.stego_path = Path(filename)
            self.file_input.setText(filename)
            ext = self.stego_path.suffix.lower()
            detected_media = self.extension_media_map.get(ext)
            if detected_media and detected_media != self.selected_media_type:
                self._set_media_type(detected_media)
            self._update_preview()

    def _update_preview(self) -> None:
        if not self.stego_path:
            return
        self.info_labels["ชื่อไฟล์"].setText(self.stego_path.name)
        size_kb = self.stego_path.stat().st_size / 1024
        self.info_labels["ขนาด"].setText(f"{size_kb:.2f} KB")
        media_type = self.extension_media_map.get(
            self.stego_path.suffix.lower(), self.selected_media_type
        )
        pretty_type = {
            "image": "ไฟล์ภาพ",
            "audio": "ไฟล์เสียง",
            "video": "ไฟล์วิดีโอ",
        }.get(media_type, "ไม่ทราบ")
        self.info_labels["ประเภท"].setText(pretty_type)
        self.info_labels["สถานะ"].setText("พร้อมตรวจสอบ")
        self.info_labels["สถานะ"].setStyleSheet("font-weight: bold; color: #1E88E5;")

        if media_type == "image":
            pixmap = QPixmap(str(self.stego_path))
            if not pixmap.isNull():
                self.preview_label.setPixmap(
                    pixmap.scaled(
                        self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
                return
        self.preview_label.setPixmap(QPixmap())
        if media_type == "audio":
            self.preview_label.setText(
                f"🎧 ไฟล์เสียง\n{self.stego_path.name}\n({self.stego_path.suffix})"
            )
        elif media_type == "video":
            self.preview_label.setText(
                f"🎞️ ไฟล์วิดีโอ\n{self.stego_path.name}\n({self.stego_path.suffix})"
            )
        else:
            self.preview_label.setText(
                f"ไฟล์: {self.stego_path.name}\nประเภท: {self.stego_path.suffix}"
            )

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

        if not self.selected_method:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกวิธีการดึงข้อมูล")
            return

        method = self.selected_method

        params = {
            "stego_path": str(self.stego_path),
            "password": password,
            "method": method,
            "expects_encrypted": self.encrypted_cb.isChecked(),
            "media_type": self.selected_media_type,
        }

        self._reset_results()
        self._set_busy(True)
        self.parent_window.start_worker(
            "extract",
            params,
            on_result=self._on_extract_result,
            on_error=self._on_worker_error,
            on_finished=self._on_worker_finished,
        )

    def _on_extract_result(self, result: Dict[str, object]) -> None:
        self.extracted_data = None
        self.extracted_payload = None

        if not isinstance(result, dict):
            self.result_text.setPlainText("ไม่สามารถอ่านข้อมูลที่ดึงมาได้")
            QMessageBox.warning(self, "คำเตือน", "รูปแบบผลลัพธ์ไม่ถูกต้อง")
            self._update_save_state()
            return

        raw_data = result.get("data")
        method = result.get("method", "adaptive")
        attempted_methods = result.get("attempted_methods")
        media_type = str(result.get("media_type") or self.selected_media_type)

        pretty_media = {
            "image": "ไฟล์ภาพ",
            "audio": "ไฟล์เสียง",
            "video": "ไฟล์วิดีโอ",
        }.get(media_type, media_type.upper())

        if "สื่อที่ตรวจสอบ" in self.details_labels:
            self.details_labels["สื่อที่ตรวจสอบ"].setText(pretty_media)

        attempts_text = "—"
        if isinstance(attempted_methods, (list, tuple)):
            attempts = [str(item).upper() for item in attempted_methods if item]
            if attempts:
                attempts_text = ", ".join(dict.fromkeys(attempts))
        if "วิธีที่ลอง" in self.details_labels:
            self.details_labels["วิธีที่ลอง"].setText(attempts_text)

        method_text = str(method).upper()
        if "วิธีการตรวจพบ" in self.details_labels:
            self.details_labels["วิธีการตรวจพบ"].setText(method_text)

        if not isinstance(raw_data, (bytes, bytearray)):
            self.result_text.setPlainText("ไม่สามารถอ่านข้อมูลที่ดึงมาได้")
            if "ขนาดข้อมูล" in self.details_labels:
                self.details_labels["ขนาดข้อมูล"].setText("—")
            if "สถานะการเข้ารหัส" in self.details_labels:
                self.details_labels["สถานะการเข้ารหัส"].setText("ไม่ทราบ")
            self._update_save_state()
            QMessageBox.warning(self, "คำเตือน", "ไม่พบข้อมูลที่ถูกซ่อนอยู่")
            return

        try:
            payload = unpack_payload(bytes(raw_data))
        except Exception as exc:
            self.result_text.setPlainText("ไม่สามารถอ่านข้อมูลที่ดึงมาได้")
            if "ขนาดข้อมูล" in self.details_labels:
                self.details_labels["ขนาดข้อมูล"].setText("—")
            if "สถานะการเข้ารหัส" in self.details_labels:
                self.details_labels["สถานะการเข้ารหัส"].setText("ไม่ทราบ")
            self._update_save_state()
            QMessageBox.warning(self, "คำเตือน", f"ไม่สามารถถอดข้อมูลได้:\n{exc}")
            return

        self.extracted_payload = payload
        self.extracted_data = payload.get("data")
        metadata = payload.get("metadata", {})
        kind = payload.get("kind", "binary")
        size = int(metadata.get("size", len(self.extracted_data) if self.extracted_data else 0))

        if kind == "text":
            text = payload.get("text")
            if text is None and self.extracted_data is not None:
                text = self.extracted_data.decode("utf-8", errors="replace")
            self.result_text.setPlainText(text or "")
            self.result_stack.setCurrentIndex(0)
        else:
            name = metadata.get("name") or "extracted_secret"
            extension = metadata.get("extension")
            if not extension and name:
                extension = Path(name).suffix.lstrip(".")
            self.file_result_labels["ชื่อไฟล์"].setText(name)
            self.file_result_labels["สกุลไฟล์"].setText(extension or "—")
            self.file_result_labels["ขนาด"].setText(self._format_size(size))
            self.file_hint_label.setText("กด \"บันทึกเป็นไฟล์\" เพื่อบันทึกข้อมูลที่ถอดได้")
            self.result_stack.setCurrentIndex(1)

        if "วิธีการตรวจพบ" in self.details_labels:
            self.details_labels["วิธีการตรวจพบ"].setText(str(method).upper())
        if "ขนาดข้อมูล" in self.details_labels:
            self.details_labels["ขนาดข้อมูล"].setText(self._format_size(size))
        encrypted_flag = metadata.get("encrypted")
        if encrypted_flag:
            status_text = "ถอดรหัสแล้ว"
        elif encrypted_flag is False:
            status_text = "ไม่มีการเข้ารหัส"
        else:
            status_text = "ไม่ทราบ"
        if "สถานะการเข้ารหัส" in self.details_labels:
            self.details_labels["สถานะการเข้ารหัส"].setText(status_text)

        self._update_save_state()
        QMessageBox.information(self, "สำเร็จ", "ดึงข้อมูลสำเร็จ!")

    def _save_extracted(self) -> None:
        if not self.extracted_payload or not isinstance(self.extracted_data, (bytes, bytearray)):
            QMessageBox.warning(self, "คำเตือน", "ยังไม่มีข้อมูลที่ดึงออกมา")
            return

        metadata = self.extracted_payload.get("metadata", {})
        kind = self.extracted_payload.get("kind", "binary")
        default_name = "extracted_secret"
        file_filter = "All Files (*.*)"

        if kind == "text":
            default_name = "extracted_secret.txt"
            file_filter = "Text Files (*.txt);;All Files (*.*)"
        else:
            name = metadata.get("name")
            if name:
                default_name = name
            else:
                extension = metadata.get("extension")
                if extension:
                    default_name = f"extracted_secret.{extension}"

        initial_path = str((self.stego_path.parent / default_name) if self.stego_path else default_name)
        filename, _ = QFileDialog.getSaveFileName(self, "บันทึกไฟล์", initial_path, file_filter)
        if filename:
            Path(filename).write_bytes(bytes(self.extracted_data))
            QMessageBox.information(self, "สำเร็จ", f"บันทึกไฟล์สำเร็จ: {filename}")

    def _on_worker_error(self, error: str) -> None:
        QMessageBox.critical(self, "ข้อผิดพลาด", f"เกิดข้อผิดพลาด:\n{error}")
        if "อาจถูกเข้ารหัส" in error:
            self.encrypted_cb.setChecked(True)
            self.details_labels["สถานะการเข้ารหัส"].setText("ต้องใช้รหัสผ่าน")
            self.password_input.setEnabled(True)
            self.password_input.setFocus()
            self.password_input.selectAll()
        self._set_busy(False)

    def _on_worker_finished(self) -> None:
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self._is_busy = busy
        self.action_btn.setEnabled(not busy)
        self._update_save_state()
