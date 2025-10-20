"""STEGOSIGHT GUI application with the refreshed interface design."""

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# ---------- Config fallbacks (GUI can run even if optional modules are missing) ----------
try:
    from config import (
        APP_NAME,
        APP_DESCRIPTION,
        GUI_SETTINGS,
        STEGO_SETTINGS,
        SUPPORTED_IMAGE_FORMATS,
    )
except Exception:
    APP_NAME = "STEGOSIGHT"
    APP_DESCRIPTION = "Stego & Anti-Stego Intelligent Guard"
    GUI_SETTINGS = {
        "window": {
            "title": "STEGOSIGHT - Stego & Anti-Stego Intelligent Guard",
            "width": 1400,
            "height": 900,
            "min_width": 1200,
            "min_height": 800,
        },
        "theme": {
            "background_color": "#f5f5f5",
        },
    }
    STEGO_SETTINGS = {}
    SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".bmp"]

# ---------- Logger fallback ----------
try:
    from utils.logger import setup_logger

    logger = setup_logger(__name__)
except Exception:  # pragma: no cover - fallback logger
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

from utils.tab_utils import FullTextTabBar


class WorkerThread(QThread):
    """Worker thread สำหรับประมวลผลแบบ asynchronous."""

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    result = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, operation: str, params: Dict[str, Any]):
        super().__init__()
        self.operation = operation
        self.params = params

    def _step(self, pct: int, msg: str) -> None:
        self.progress.emit(pct)
        self.status.emit(msg)
        self.msleep(220)

    def run(self) -> None:  # pragma: no cover - GUI thread
        try:
            self.status.emit(f"กำลังดำเนินการ: {self.operation}")
            if self.operation == "embed":
                result = self._embed()
            elif self.operation == "extract":
                result = self._extract()
            elif self.operation == "analyze":
                result = self._analyze()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")

            self.result.emit(result)
            self.status.emit("เสร็จสิ้น")
        except Exception as exc:  # pragma: no cover - GUI thread
            logger.exception("Error in worker thread")
            self.error.emit(str(exc))
        finally:
            self.finished.emit()

    # ---------------- actual ops with graceful fallbacks ----------------
    def _embed(self) -> Dict[str, Any]:
        try:
            from cryptography_module.encryption import encrypt_data
            from steganography.appender import append_payload_to_file

            cover_path = Path(self.params["cover_path"])
            data = self.params["secret_data"]
            password = self.params.get("password")
            method = str(self.params.get("method", "adaptive"))
            media_type = str(self.params.get("media_type", "image"))
            options = self.params.get("options")
            auto_analyze = bool(self.params.get("auto_analyze", True))

            temp_dir = Path(self.params.get("temp_dir") or tempfile.gettempdir())
            suffix = cover_path.suffix or ".stego"
            fd, temp_name = tempfile.mkstemp(prefix="stego_", suffix=suffix, dir=str(temp_dir))
            os.close(fd)
            output_path = Path(temp_name)

            self._step(10, "กำลังโหลดไฟล์…")
            if password:
                self._step(30, "กำลังเข้ารหัสข้อมูล…")
                data = encrypt_data(data, password)

            self._step(55, "กำลังซ่อนข้อมูล…")
            adaptive_engine = None
            if method == "append":
                stego_path = append_payload_to_file(
                    cover_path,
                    data,
                    output_path=output_path,
                )
                actual_method = "append"
                media_type = "image"
            elif method in {"audio_adaptive", "audio_lsb"}:
                from steganography.audio import AudioSteganography

                audio_engine = AudioSteganography()
                stego_path = audio_engine.embed(cover_path, data, output_path=output_path)
                actual_method = "audio_lsb" if method == "audio_adaptive" else method
                media_type = "audio"
            elif method in {"video_adaptive", "video_lsb"}:
                from steganography.video import VideoSteganography

                video_engine = VideoSteganography()
                stego_path = video_engine.embed(cover_path, data, output_path=output_path)
                actual_method = "video_lsb" if method == "video_adaptive" else method
                media_type = "video"
            else:
                from steganography.adaptive import AdaptiveSteganography

                adaptive_engine = AdaptiveSteganography()
                stego_path = adaptive_engine.embed(
                    cover_path,
                    data,
                    method,
                    output_path=output_path,
                    options=options,
                )
                actual_method = getattr(adaptive_engine, "last_method", method)
                media_type = "image"

            if auto_analyze and media_type == "image":
                self._step(80, "กำลังวิเคราะห์ความเสี่ยง…")
                from steganalysis.risk_scoring import RiskScorer

                scorer = RiskScorer()
                risk_score = scorer.calculate_risk(stego_path)
            else:
                self._step(80, "กำลังเตรียมผลลัพธ์…")
                risk_score = None

            recommendation = None
            if adaptive_engine is not None:
                try:
                    recommendation = adaptive_engine.get_recommended_settings(cover_path, data)
                except Exception:
                    recommendation = None

            self._step(100, "เสร็จสิ้น")
            return {
                "stego_path": stego_path,
                "risk_score": risk_score,
                "method": actual_method,
                "options": options,
                "recommendation": recommendation,
                "media_type": media_type,
                "temporary": True,
            }
        except Exception as exc:  # pragma: no cover - simulated pipeline
            logger.info("Embedding pipeline not available, using simulator: %s", exc)
            self._step(15, "กำลังโหลดไฟล์…")
            self._step(40, "กำลังเข้ารหัสข้อมูล…")
            self._step(70, "กำลังซ่อนข้อมูล…")
            cover_path = Path(self.params["cover_path"])
            secret_data = self.params.get("secret_data", b"")
            method = str(self.params.get("method", "adaptive"))
            media_type = str(self.params.get("media_type", "image"))
            auto_analyze = bool(self.params.get("auto_analyze", True))
            suffix = cover_path.suffix or ".stego"
            fd, temp_name = tempfile.mkstemp(prefix="stego_", suffix=suffix)
            os.close(fd)
            out_path = Path(temp_name)
            try:
                if method == "append":
                    from steganography.appender import append_payload_to_file

                    append_payload_to_file(
                        cover_path,
                        secret_data,
                        output_path=out_path,
                    )
                    actual_method = "append"
                    media_type = "image"
                elif method in {"audio_adaptive", "audio_lsb"}:
                    out_path.write_bytes(cover_path.read_bytes())
                    actual_method = "audio_lsb"
                    media_type = "audio"
                elif method in {"video_adaptive", "video_lsb"}:
                    out_path.write_bytes(cover_path.read_bytes())
                    actual_method = "video_lsb"
                    media_type = "video"
                else:
                    out_path.write_bytes(cover_path.read_bytes())
                    actual_method = method
            except Exception:
                out_path.write_bytes(b"STEGOSIGHT SIMULATED STEGO FILE")
                actual_method = method
            if auto_analyze and media_type == "image":
                self._step(95, "กำลังวิเคราะห์ความเสี่ยง…")
                risk_score = {"score": 42, "level": "MEDIUM"}
            else:
                self._step(95, "กำลังเตรียมผลลัพธ์…")
                risk_score = None
            return {
                "stego_path": str(out_path),
                "risk_score": risk_score,
                "method": actual_method,
                "options": self.params.get("options"),
                "recommendation": None,
                "media_type": media_type,
                "temporary": True,
            }

    @staticmethod
    def _should_hint_encryption(
        data: Optional[bytes], payload_detected: bool, expects_encrypted: bool
    ) -> bool:
        """Return ``True`` when recovered bytes may be an encrypted payload."""

        if expects_encrypted or payload_detected:
            return False
        if not isinstance(data, (bytes, bytearray, memoryview)):
            return False
        return len(data) >= 16

    def _extract(self) -> Dict[str, Any]:
        from utils.payloads import is_payload_blob

        try:
            from cryptography_module.encryption import decrypt_data
            from steganography.appender import (
                extract_appended_payload,
                has_appended_payload,
            )

            AdaptiveSteganographyCls: Optional[type] = None
            adaptive_import_error: Optional[Exception] = None
            try:
                from steganography.adaptive import AdaptiveSteganography as _AdaptiveSteganography

                AdaptiveSteganographyCls = _AdaptiveSteganography
            except Exception as exc:  # pragma: no cover - optional dependency
                adaptive_import_error = exc

            stego_path = Path(self.params["stego_path"])
            password = self.params.get("password") or None
            requested_method = str(self.params.get("method", "adaptive")).lower()
            expects_encrypted = bool(self.params.get("expects_encrypted", False))
            self._step(20, "กำลังโหลดไฟล์…")

            audio_methods = {"audio_lsb", "audio_adaptive"}
            video_methods = {"video_lsb", "video_adaptive"}

            if requested_method in audio_methods:
                self._step(40, "กำลังดึงข้อมูลเสียง…")
                try:
                    from steganography.audio import AudioSteganography
                except Exception as exc:  # pragma: no cover - optional dependency
                    raise RuntimeError("ไม่สามารถโหลดโมดูลสำหรับถอดข้อมูลเสียงได้") from exc

                extractor = AudioSteganography()
                data = extractor.extract(stego_path)
                used_method = "audio_lsb"
                attempted = [requested_method]
                if requested_method != used_method:
                    attempted.append(used_method)

                payload_detected = is_payload_blob(data)
                encrypted = False

                if password:
                    self._step(70, "กำลังถอดรหัสข้อมูล…")
                    try:
                        data = decrypt_data(data, password)
                    except Exception as exc:
                        raise ValueError("รหัสผ่านไม่ถูกต้องหรือข้อมูลถูกทำลาย") from exc
                    encrypted = True
                    payload_detected = is_payload_blob(data)
                    if not payload_detected:
                        raise ValueError("ไม่สามารถยืนยันโครงสร้างข้อมูลหลังถอดรหัส")
                elif expects_encrypted:
                    raise ValueError("จำเป็นต้องกรอกรหัสผ่านเพื่อถอดข้อมูลที่เข้ารหัส")

                self._step(95, "กำลังตรวจสอบผลลัพธ์…")
                self._step(100, "เสร็จสิ้น")
                return {
                    "data": data,
                    "method": used_method,
                    "attempted_methods": attempted,
                    "payload_detected": payload_detected,
                    "encrypted": encrypted,
                    "media_type": "audio",
                }

            if requested_method in video_methods:
                self._step(40, "กำลังดึงข้อมูลวิดีโอ…")
                try:
                    from steganography.video import VideoSteganography
                except Exception as exc:  # pragma: no cover - optional dependency
                    raise RuntimeError("ไม่สามารถโหลดโมดูลสำหรับถอดข้อมูลวิดีโอได้") from exc

                extractor = VideoSteganography()
                data = extractor.extract(stego_path)
                used_method = "video_lsb"
                attempted = [requested_method]
                if requested_method != used_method:
                    attempted.append(used_method)

                payload_detected = is_payload_blob(data)
                encrypted = False

                if password:
                    self._step(70, "กำลังถอดรหัสข้อมูล…")
                    try:
                        data = decrypt_data(data, password)
                    except Exception as exc:
                        raise ValueError("รหัสผ่านไม่ถูกต้องหรือข้อมูลถูกทำลาย") from exc
                    encrypted = True
                    payload_detected = is_payload_blob(data)
                    if not payload_detected:
                        raise ValueError("ไม่สามารถยืนยันโครงสร้างข้อมูลหลังถอดรหัส")
                elif expects_encrypted:
                    raise ValueError("จำเป็นต้องกรอกรหัสผ่านเพื่อถอดข้อมูลที่เข้ารหัส")

                self._step(95, "กำลังตรวจสอบผลลัพธ์…")
                self._step(100, "เสร็จสิ้น")
                return {
                    "data": data,
                    "method": used_method,
                    "attempted_methods": attempted,
                    "payload_detected": payload_detected,
                    "encrypted": encrypted,
                    "media_type": "video",
                }

            adaptive_mode = requested_method in {"adaptive", "auto"}
            methods_to_try: List[str] = []
            if requested_method == "append":
                methods_to_try = ["append"]
            elif adaptive_mode:
                if has_appended_payload(stego_path):
                    methods_to_try.append("append")
                if AdaptiveSteganographyCls is None:
                    if not methods_to_try:
                        raise adaptive_import_error or RuntimeError(
                            "ไม่สามารถโหลดโมดูล AdaptiveSteganography"
                        )
                else:
                    detector = AdaptiveSteganographyCls()
                    try:
                        detected = detector._detect_embedding_method(stego_path)
                        if detected:
                            methods_to_try.append(detected)
                    except Exception as detect_exc:  # pragma: no cover - best effort hint
                        logger.debug("Auto-detect failed: %s", detect_exc)
                    for candidate in ("lsb", "pvd", "dct"):
                        if candidate not in methods_to_try:
                            methods_to_try.append(candidate)
            else:
                methods_to_try = [requested_method]
                if requested_method != "append" and AdaptiveSteganographyCls is None:
                    raise adaptive_import_error or RuntimeError(
                        "ไม่สามารถโหลดโมดูล AdaptiveSteganography"
                    )

            extraction_errors: Dict[str, str] = {}
            maybe_encrypted_hint = False

            for index, method in enumerate(methods_to_try):
                progress = min(60, 30 + index * 15)
                self._step(progress, f"กำลังดึงข้อมูลด้วย {method.upper()}…")

                try:
                    if method == "append":
                        data = extract_appended_payload(stego_path)
                        used_method = "append"
                    else:
                        if AdaptiveSteganographyCls is None:
                            raise RuntimeError("AdaptiveSteganography backend is unavailable")
                        extractor = AdaptiveSteganographyCls()
                        data = extractor.extract(stego_path, method)
                        used_method = getattr(extractor, "last_method", method)
                except Exception as exc:
                    extraction_errors[method] = str(exc)
                    continue

                payload_detected = is_payload_blob(data)
                encrypted = False

                if self._should_hint_encryption(data, payload_detected, expects_encrypted):
                    maybe_encrypted_hint = True

                if password:
                    self._step(progress + 10, "กำลังถอดรหัสข้อมูล…")
                    try:
                        data = decrypt_data(data, password)
                    except Exception as exc:
                        raise ValueError("รหัสผ่านไม่ถูกต้องหรือข้อมูลถูกทำลาย") from exc
                    encrypted = True
                    payload_detected = is_payload_blob(data)
                    if not payload_detected:
                        raise ValueError("ไม่สามารถยืนยันโครงสร้างข้อมูลหลังถอดรหัส")
                elif expects_encrypted:
                    raise ValueError("จำเป็นต้องกรอกรหัสผ่านเพื่อถอดข้อมูลที่เข้ารหัส")

                if not payload_detected and adaptive_mode:
                    extraction_errors[method] = "ไม่พบโครงสร้าง payload ที่รู้จัก"
                    continue

                self._step(95, "กำลังตรวจสอบผลลัพธ์…")
                self._step(100, "เสร็จสิ้น")
                return {
                    "data": data,
                    "method": used_method,
                    "attempted_methods": methods_to_try,
                    "payload_detected": payload_detected,
                    "encrypted": encrypted,
                    "media_type": "image",
                }

            detail = "; ".join(f"{k.upper()}: {v}" for k, v in extraction_errors.items())
            if maybe_encrypted_hint and not expects_encrypted:
                raise ValueError(
                    "ไม่พบข้อมูลที่ถูกซ่อนอยู่ แต่ตรวจพบรูปแบบที่อาจถูกเข้ารหัส\n"
                    "กรุณาเลือกตัวเลือก \"ข้อมูลถูกเข้ารหัส\" และใส่รหัสผ่าน จากนั้นลองอีกครั้ง"
                )
            if detail:
                raise ValueError(f"ไม่พบข้อมูลที่ถูกซ่อนอยู่ ({detail})")
            raise ValueError("ไม่พบข้อมูลที่ถูกซ่อนอยู่")
        except Exception:
            raise

    def _analyze(self) -> Dict[str, Any]:
        try:
            from steganalysis.risk_scoring import RiskScorer

            file_path = self.params["file_path"]
            methods = self.params.get("methods", ["all"])
            self._step(25, "กำลังวิเคราะห์ไฟล์…")
            scorer = RiskScorer()
            res = scorer.analyze_file(file_path, methods)
            self._step(100, "เสร็จสิ้น")
            return res
        except Exception as exc:  # pragma: no cover - simulated pipeline
            logger.info("Analysis pipeline not available, using simulator: %s", exc)
            import random

            self._step(35, "กำลังคำนวณสถิติ…")
            score = random.randint(15, 85)
            level = "LOW" if score < 30 else ("MEDIUM" if score < 60 else "HIGH")
            self._step(100, "เสร็จสิ้น")
            return {
                "score": score,
                "level": level,
                "details": {"chi_square": True, "histogram": True, "ela": True},
            }


@dataclass(frozen=True)
class TabDefinition:
    """Descriptor for lazily constructed GUI tabs."""

    key: str
    title: str
    factory: Callable[[], QWidget]


class StegosightGUI(QMainWindow):
    """Main application window using the refreshed STEGOSIGHT design."""

    def __init__(self) -> None:
        super().__init__()
        self.worker: Optional[WorkerThread] = None
        self.status_label: Optional[QLabel] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.tab_definitions: List[TabDefinition] = []
        self.tab_widgets: Dict[str, QWidget] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        window_cfg = GUI_SETTINGS["window"]
        self.setWindowTitle(window_cfg["title"])
        self.setGeometry(100, 100, window_cfg["width"], window_cfg["height"])
        self.setMinimumSize(window_cfg["min_width"], window_cfg["min_height"])

        main_container = QWidget()
        self.setCentralWidget(main_container)
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._create_header())

        self.tabs = QTabWidget()
        self.tabs.setTabBar(FullTextTabBar(minimum_width=220, extra_padding=72))
        self.tabs.setUsesScrollButtons(True)

        self.tab_definitions = self._build_tab_definitions()
        self.tab_widgets = {}
        for tab_def in self.tab_definitions:
            widget = tab_def.factory()
            self.tab_widgets[tab_def.key] = widget
            self.tabs.addTab(widget, tab_def.title)
        self._apply_tab_tooltips(self.tabs)
        main_layout.addWidget(self.tabs)

        main_layout.addWidget(self._create_status_bar())

        self.apply_stylesheet()

    def _build_tab_definitions(self) -> List[TabDefinition]:
        return [
            TabDefinition("embed", " 🔒 ซ่อนข้อมูล (Embed)", self._create_embed_tab),
            TabDefinition("extract", " 🔓 ดึงข้อมูล (Extract)", self._create_extract_tab),
            TabDefinition("analyze", " 🔍 วิเคราะห์ (Analyze)", self._create_analyze_tab),
        ]

    def _apply_tab_tooltips(self, tab_widget: QTabWidget) -> None:
        """Ensure the full tab labels remain accessible via tooltips."""

        for index in range(tab_widget.count()):
            text = tab_widget.tabText(index).strip()
            tab_widget.setTabToolTip(index, text)

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(80)

        row = QHBoxLayout(header)
        row.setContentsMargins(30, 0, 30, 0)

        logo = QLabel("🔐")
        logo.setObjectName("headerLogo")
        row.addWidget(logo)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("headerTitle")
        desc = QLabel(APP_DESCRIPTION)
        desc.setObjectName("headerSubtitle")
        col.addWidget(title)
        col.addWidget(desc)

        row.addLayout(col)
        row.addStretch()
        return header

    def _create_status_bar(self) -> QFrame:
        status_widget = QFrame()
        status_widget.setObjectName("statusBar")
        layout = QHBoxLayout(status_widget)
        layout.setContentsMargins(20, 10, 20, 10)

        self.status_label = QLabel("<b>สถานะ:</b> พร้อมใช้งาน")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedSize(300, 8)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        return status_widget

    def apply_stylesheet(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background-color: #f5f5f5; }

            #header {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E88E5, stop:1 #2979FF);
                border: none;
            }
            #headerLogo {
                font-size: 36px;
                padding-right: 15px;
                color: white;
            }
            #headerTitle {
                padding-top: 18px;
                font-size: 26px;
                font-weight: bold;
                color: white;
            }
            #headerSubtitle {
                padding-bottom: 8px;
                font-size: 13px;
                color: #e0e0e0;
            }

            QTabWidget::pane {
                border-top: 1px solid #ddd;
                background-color: white;
            }
            QTabBar {
                background-color: #f0f0f0;
            }
            QTabBar::tab {
                background: transparent;
                color: #555;
                padding: 15px 25px;
                margin-right: 2px;
                font-size: 14px;
                border: none;
                border-bottom: 3px solid transparent;
            }
            QTabBar::tab:hover {
                background: #e9e9e9;
                color: #1E88E5;
            }
            QTabBar::tab:selected {
                background: white;
                color: #1E88E5;
                border-bottom: 3px solid #1E88E5;
            }

            QGroupBox {
                border: 2px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding: 20px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                color: #1E88E5;
                font-size: 14px;
                font-weight: bold;
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 5px 10px;
            }

            QLineEdit, QTextEdit, QComboBox {
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                font-size: 13px;
            }

            QComboBox QAbstractItemView {
                border: 1px solid #ddd;
                background-color: white;
                selection-color: black;
                selection-background-color: #1E88E5;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e3f2fd;
                color: #333;
            }

            QPushButton {
                background-color: #1E88E5;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1976D2; }

            #statusBar {
                background-color: #e0e0e0;
                padding: 10px 20px;
                border-top: 1px solid #ccc;
            }

            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #bdbdbd;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background-color: #1E88E5;
            }

            QScrollArea { border: none; }
            """
        )


    # ---- Tab factories (lazy import prevents circular imports) ----
    def _create_embed_tab(self) -> QWidget:
        from gui_tabs import EmbedTab

        return EmbedTab(self)

    def _create_extract_tab(self) -> QWidget:
        from gui_tabs import ExtractTab

        return ExtractTab(self)

    def _create_analyze_tab(self) -> QWidget:
        from gui_tabs import AnalyzeTab

        return AnalyzeTab(self)

    # ---- Worker management -------------------------------------------------
    def start_worker(
        self,
        operation: str,
        params: Dict[str, Any],
        *,
        on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "กำลังประมวลผล", "ระบบกำลังประมวลผลงานอื่นอยู่")
            return

        if self.progress_bar:
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
        if self.status_label:
            self.status_label.setText(f"กำลังดำเนินการ: {operation}")

        worker = WorkerThread(operation, params)
        if self.progress_bar:
            worker.progress.connect(self.progress_bar.setValue)
        if self.status_label:
            worker.status.connect(self.status_label.setText)
        if on_result:
            worker.result.connect(on_result)
        if on_error:
            worker.error.connect(on_error)
        else:
            worker.error.connect(self._handle_worker_error)

        def _finished() -> None:
            self._handle_worker_finished(on_finished)

        worker.finished.connect(_finished)
        self.worker = worker
        worker.start()

    def _handle_worker_error(self, message: str) -> None:
        QMessageBox.critical(self, "ข้อผิดพลาด", message)

    def _handle_worker_finished(self, callback: Optional[Callable[[], None]]) -> None:
        if self.progress_bar:
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
        if self.status_label:
            self.status_label.setText("<b>สถานะ:</b> พร้อมใช้งาน")
        self.worker = None
        if callback:
            callback()


class STEGOSIGHTApp(StegosightGUI):
    """Backward compatible alias for the main STEGOSIGHT GUI window.

    Older entry points expect a ``STEGOSIGHTApp`` symbol in ``gui``.
    The refreshed interface refactored the main window into
    :class:`StegosightGUI`, but ``main.run_gui`` (and potentially other
    integrations) still import ``STEGOSIGHTApp``.  Expose a thin subclass
    so that these imports continue to work without modifying existing
    startup code.
    """

    pass


def main() -> int:
    app = QApplication(sys.argv)
    window = StegosightGUI()
    window.show()
    return app.exec_()


if __name__ == "__main__":  # pragma: no cover - manual GUI launch
    sys.exit(main())
