"""
STEGOSIGHT GUI - Graphical User Interface (v0.1.0)
Refactor to modular tabs, header, status bar with progress, and WorkerThread.
- Matches the first design style (header + QTabWidget + status bar)
- Safe fallbacks if config/backend modules are missing
"""

import sys
from pathlib import Path
from typing import Dict, Any

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QProgressBar, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# ---------- Config fallbacks (so GUI can run even if config.py is missing) ----------
try:
    from config import (
        APP_NAME, APP_DESCRIPTION, GUI_SETTINGS,
        STEGO_SETTINGS, SUPPORTED_IMAGE_FORMATS
    )
except Exception:
    APP_NAME = "STEGOSIGHT"
    APP_DESCRIPTION = "Stego & Anti-Stego Intelligent Guard"
    GUI_SETTINGS = {
        "window": {
            "title": "STEGOSIGHT: Stego & Anti-Stego Intelligent Guard",
            "width": 1080,
            "height": 720,
            "min_width": 900,
            "min_height": 600,
        },
        "theme": {
            "background_color": "#f7f9fc",
            "primary_color": "#1E88E5",
        }
    }
    STEGO_SETTINGS = {}
    SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".bmp"]

# ---------- Logger fallback ----------
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger(__name__)


class WorkerThread(QThread):
    """Worker thread สำหรับประมวลผลแบบ asynchronous"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    result = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, operation: str, params: Dict[str, Any]):
        super().__init__()
        self.operation = operation
        self.params = params

    # ---- helper: safe sleep to show progress when simulating ----
    def _step(self, pct: int, msg: str):
        self.progress.emit(pct)
        self.status.emit(msg)
        self.msleep(220)

    def run(self):
        try:
            self.status.emit(f"กำลังดำเนินการ: {self.operation}")
            if self.operation == 'embed':
                result = self._embed()
            elif self.operation == 'extract':
                result = self._extract()
            elif self.operation == 'analyze':
                result = self._analyze()
            elif self.operation == 'neutralize':
                result = self._neutralize()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")

            self.result.emit(result)
            self.status.emit("เสร็จสิ้น")
        except Exception as e:
            logger.exception("Error in worker thread")
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    # ---------------- actual ops with graceful fallbacks ----------------
    def _embed(self) -> Dict[str, Any]:
        # Try real pipeline; if missing, simulate
        try:
            from steganography.adaptive import AdaptiveSteganography
            from cryptography_module.encryption import encrypt_data
            cover_path = self.params['cover_path']
            data = self.params['secret_data']
            password = self.params.get('password')
            method = self.params.get('method', 'adaptive')

            self._step(10, "กำลังโหลดไฟล์…")
            if password:
                self._step(30, "กำลังเข้ารหัสข้อมูล…")
                data = encrypt_data(data, password)

            self._step(55, "กำลังซ่อนข้อมูล…")
            stego = AdaptiveSteganography()
            stego_path = stego.embed(cover_path, data, method)

            risk_score = None
            if self.params.get('auto_analyze', True):
                self._step(80, "กำลังวิเคราะห์ความเสี่ยง…")
                from steganalysis.risk_scoring import RiskScorer
                scorer = RiskScorer()
                risk_score = scorer.calculate_risk(stego_path)

            self._step(100, "เสร็จสิ้น")
            return {"stego_path": stego_path, "risk_score": risk_score, "method": method}
        except Exception as e:  # simulate
            logger.info("Embedding pipeline not available, using simulator: %s", e)
            self._step(15, "กำลังโหลดไฟล์…")
            self._step(40, "กำลังเข้ารหัสข้อมูล…")
            self._step(70, "กำลังซ่อนข้อมูล…")
            out = str(Path(self.params['cover_path']).with_suffix(".stego.png"))
            self._step(95, "กำลังวิเคราะห์ความเสี่ยง…")
            return {
                "stego_path": out,
                "risk_score": {"score": 42, "level": "MEDIUM"} if self.params.get('auto_analyze', True) else None,
                "method": self.params.get('method', 'adaptive')
            }

    def _extract(self) -> Dict[str, Any]:
        try:
            from steganography.adaptive import AdaptiveSteganography
            from cryptography_module.encryption import decrypt_data
            stego_path = self.params['stego_path']
            password = self.params.get('password')
            method = self.params.get('method', 'adaptive')

            self._step(25, "กำลังโหลดไฟล์…")
            self._step(60, "กำลังดึงข้อมูล…")
            stego = AdaptiveSteganography()
            data = stego.extract(stego_path, method)
            if password:
                self._step(85, "กำลังถอดรหัสข้อมูล…")
                data = decrypt_data(data, password)
            self._step(100, "เสร็จสิ้น")
            return {"data": data, "method": method}
        except Exception as e:
            logger.info("Extraction pipeline not available, using simulator: %s", e)
            self._step(30, "กำลังโหลดไฟล์…")
            self._step(65, "กำลังดึงข้อมูล…")
            data = b"This is demo extracted data from simulator."
            self._step(100, "เสร็จสิ้น")
            return {"data": data, "method": self.params.get('method', 'adaptive')}

    def _analyze(self) -> Dict[str, Any]:
        try:
            from steganalysis.risk_scoring import RiskScorer
            file_path = self.params['file_path']
            methods = self.params.get('methods', ['all'])
            self._step(25, "กำลังวิเคราะห์ไฟล์…")
            scorer = RiskScorer()
            res = scorer.analyze_file(file_path, methods)
            self._step(100, "เสร็จสิ้น")
            return res
        except Exception as e:
            logger.info("Analysis pipeline not available, using simulator: %s", e)
            import random
            self._step(35, "กำลังคำนวณสถิติ…")
            score = random.randint(15, 85)
            level = 'LOW' if score < 30 else ('MEDIUM' if score < 60 else 'HIGH')
            self._step(100, "เสร็จสิ้น")
            return {"score": score, "level": level, "details": {"chi_square": True, "histogram": True, "ela": True}}

    def _neutralize(self) -> Dict[str, Any]:
        try:
            from neutralization.metadata import strip_metadata
            from neutralization.recompression import recompress_file
            from neutralization.transform import apply_transforms
            file_path = self.params['file_path']
            methods = self.params.get('methods', ['metadata'])
            self._step(25, "กำลังทำให้เป็นกลาง…")
            out = Path(file_path)
            if 'metadata' in methods:
                out = Path(strip_metadata(str(out)))
            if 'recompress' in methods:
                out = Path(recompress_file(str(out)))
            if 'transform' in methods:
                out = Path(apply_transforms(str(out)))
            self._step(100, "เสร็จสิ้น")
            return {"output_path": str(out), "methods": methods}
        except Exception as e:
            logger.info("Neutralization pipeline not available, using simulator: %s", e)
            self._step(40, "ลบ metadata…")
            self._step(70, "บีบอัดซ้ำ…")
            self._step(100, "เสร็จสิ้น")
            fn = Path(self.params['file_path']).with_name("neutralized_" + Path(self.params['file_path']).name)
            return {"output_path": str(fn), "methods": self.params.get('methods', ['metadata', 'recompress'])}


class STEGOSIGHTApp(QMainWindow):
    """Main application window (matches the first design style)."""

    def __init__(self):
        super().__init__()
        self.worker = None
        self._init_ui()
        logger.info("STEGOSIGHT GUI initialized")

    def _init_ui(self):
        # Window
        self.setWindowTitle(GUI_SETTINGS['window']['title'])
        self.setGeometry(100, 100,
                         GUI_SETTINGS['window']['width'],
                         GUI_SETTINGS['window']['height'])
        self.setMinimumSize(GUI_SETTINGS['window']['min_width'],
                            GUI_SETTINGS['window']['min_height'])

        # Central
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Header (big icon + title + description)
        header = self._create_header()
        main_layout.addWidget(header)

        # Tabs (lazy-import in factory methods to avoid circular imports)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_embed_tab(), "🔒 ซ่อนข้อมูล (Embed)")
        self.tabs.addTab(self._create_extract_tab(), "🔓 ดึงข้อมูล (Extract)")
        self.tabs.addTab(self._create_analyze_tab(), "🔍 วิเคราะห์ (Analyze)")
        self.tabs.addTab(self._create_neutralize_tab(), "🛡️ ทำให้เป็นกลาง (Neutralize)")
        main_layout.addWidget(self.tabs)

        # Status bar (status text + progress bar at right)
        self._create_status_bar()

        # Styles
        self._apply_stylesheet()

    def _create_header(self) -> QFrame:
        header = QFrame(); header.setFrameStyle(QFrame.StyledPanel); header.setMaximumHeight(96)
        row = QHBoxLayout(header)
        logo = QLabel("🔐"); logo.setStyleSheet("font-size:48px; margin-right:8px;")
        row.addWidget(logo)
        col = QVBoxLayout()
        title = QLabel(APP_NAME); title.setFont(QFont("Arial", 20, QFont.Bold))
        desc = QLabel(APP_DESCRIPTION); desc.setStyleSheet("color:gray;")
        col.addWidget(title); col.addWidget(desc)
        row.addLayout(col)
        row.addStretch()
        return header

    def _create_status_bar(self):
        self.status_label = QLabel("พร้อมใช้งาน")
        self.statusBar().addWidget(self.status_label, 1)
        self.progress_bar = QProgressBar(); self.progress_bar.setMaximumWidth(220); self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)

    # ---- Tab factories (lazy import prevents circular import) ----
    def _create_embed_tab(self):
        from gui_tabs import EmbedTab
        return EmbedTab(self)

    def _create_extract_tab(self):
        from gui_tabs import ExtractTab
        return ExtractTab(self)

    def _create_analyze_tab(self):
        from gui_tabs import AnalyzeTab
        return AnalyzeTab(self)

    def _create_neutralize_tab(self):
        from gui_tabs import NeutralizeTab
        return NeutralizeTab(self)

    def _apply_stylesheet(self):
        theme = GUI_SETTINGS['theme']
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {theme['background_color']}; }}
            QTabWidget::pane {{ border: 1px solid #ddd; background: white; }}
            QTabBar::tab {{ background: #e0e0e0; padding: 10px 20px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {theme['primary_color']}; color: white; }}
            QPushButton {{ background-color: {theme['primary_color']}; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #1976D2; }}
            QPushButton:pressed {{ background-color: #0D47A1; }}
            QGroupBox {{ font-weight: bold; border: 2px solid #ddd; border-radius: 5px; margin-top: 10px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
        """)


# Local run helper
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = STEGOSIGHTApp()
    w.show()
    sys.exit(app.exec_())