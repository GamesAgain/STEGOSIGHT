"""STEGOSIGHT GUI Tabs (v0.1.0)
Embed / Extract / Analyze / Neutralize tabs matching the first-design layout.
- Uses WorkerThread from gui.py
- Updates main window status/progress
- Safe fallbacks so the GUI remains usable without backend modules
"""

from pathlib import Path
from typing import List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QFileDialog, QTextEdit, QComboBox, QGroupBox,
    QCheckBox, QSpinBox, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

# Config fallbacks
try:
    from config import STEGO_SETTINGS, SUPPORTED_IMAGE_FORMATS
except Exception:
    STEGO_SETTINGS = {}
    SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".bmp", ".wav", ".mp4", ".avi"]

# Logger fallback
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    logger = logging.getLogger(__name__)


# ------------------------------
# Embed Tab
# ------------------------------
class EmbedTab(QWidget):
    """แท็บสำหรับซ่อนข้อมูล"""

    def __init__(self, parent):
        super().__init__()
        self.parent_window = parent
        self.cover_path: Path = None
        self.secret_path: Path = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        left = self._create_input_panel(); splitter.addWidget(left)
        right = self._create_preview_panel(); splitter.addWidget(right)
        splitter.setStretchFactor(0, 3); splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # Action row
        actions = QHBoxLayout(); actions.addStretch()
        self.embed_btn = QPushButton("🔒 เริ่มซ่อนข้อมูล"); self.embed_btn.setMinimumHeight(40)
        self.embed_btn.clicked.connect(self._start_embed)
        actions.addWidget(self.embed_btn)
        layout.addLayout(actions)

    def _create_input_panel(self):
        panel = QWidget(); col = QVBoxLayout(panel)

        # 1) Cover file
        cover_group = QGroupBox("1. เลือกไฟล์ต้นฉบับ (Cover File)")
        v = QVBoxLayout()
        row = QHBoxLayout()
        self.cover_input = QLineEdit(); self.cover_input.setPlaceholderText("เลือกไฟล์ภาพ, เสียง, หรือวิดีโอ…"); self.cover_input.setReadOnly(True)
        row.addWidget(self.cover_input)
        btn = QPushButton("เลือกไฟล์"); btn.clicked.connect(self._browse_cover_file); row.addWidget(btn)
        v.addLayout(row)
        self.cover_info = QLabel("ยังไม่ได้เลือกไฟล์"); self.cover_info.setStyleSheet("color:gray; font-size:10px;")
        v.addWidget(self.cover_info)
        cover_group.setLayout(v); col.addWidget(cover_group)

        # 2) Secret data (file / text toggle)
        secret_group = QGroupBox("2. เลือกข้อมูลลับ (Secret Data)")
        v = QVBoxLayout()
        tabrow = QHBoxLayout()
        self.secret_mode_file = QPushButton("📁 จากไฟล์"); self.secret_mode_text = QPushButton("📝 พิมพ์ข้อความ")
        for b in (self.secret_mode_file, self.secret_mode_text): b.setCheckable(True)
        self.secret_mode_file.setChecked(True)
        self.secret_mode_file.clicked.connect(lambda: self._switch_secret_mode('file'))
        self.secret_mode_text.clicked.connect(lambda: self._switch_secret_mode('text'))
        tabrow.addWidget(self.secret_mode_file); tabrow.addWidget(self.secret_mode_text); tabrow.addStretch(); v.addLayout(tabrow)

        # file widget
        self.secret_file_widget = QWidget(); fr = QHBoxLayout(self.secret_file_widget)
        self.secret_input = QLineEdit(); self.secret_input.setPlaceholderText("เลือกไฟล์ที่ต้องการซ่อน…"); self.secret_input.setReadOnly(True)
        fr.addWidget(self.secret_input)
        sb = QPushButton("เลือกไฟล์"); sb.clicked.connect(self._browse_secret_file); fr.addWidget(sb)
        v.addWidget(self.secret_file_widget)
        # text widget
        self.secret_text_widget = QTextEdit(); self.secret_text_widget.setPlaceholderText("พิมพ์ข้อความที่ต้องการซ่อน…"); self.secret_text_widget.setVisible(False); self.secret_text_widget.setMaximumHeight(100)
        v.addWidget(self.secret_text_widget)
        secret_group.setLayout(v); col.addWidget(secret_group)

        # 3) Method
        method_group = QGroupBox("3. เลือกวิธีการซ่อนข้อมูล")
        v = QVBoxLayout()
        self.method_combo = QComboBox(); self.method_combo.addItems([
            "Adaptive (แนะนำ - ปรับตามเนื้อหา)",
            "LSB Matching (เหมาะกับภาพ PNG, BMP)",
            "PVD (Pixel Value Differencing)",
            "DCT (สำหรับ JPEG)"
        ])
        self.method_combo.currentIndexChanged.connect(self._update_method_info)
        v.addWidget(self.method_combo)
        self.method_info = QLabel("วิธีนี้จะวิเคราะห์ภาพและเลือกพื้นที่ที่เหมาะสมที่สุดในการซ่อนข้อมูล")
        self.method_info.setWordWrap(True); self.method_info.setStyleSheet("color:#666; font-size:10px; padding:5px;")
        v.addWidget(self.method_info)
        method_group.setLayout(v); col.addWidget(method_group)

        # 4) Encryption
        crypto_group = QGroupBox("4. การเข้ารหัส (Encryption)")
        v = QVBoxLayout()
        self.use_encryption = QCheckBox("ใช้การเข้ารหัส AES-256-GCM"); self.use_encryption.setChecked(True); self.use_encryption.toggled.connect(self._toggle_encryption)
        v.addWidget(self.use_encryption)
        r1 = QHBoxLayout(); r1.addWidget(QLabel("รหัสผ่าน:")); self.password_input = QLineEdit(); self.password_input.setEchoMode(QLineEdit.Password); self.password_input.setPlaceholderText("กรอกรหัสผ่าน…"); r1.addWidget(self.password_input); v.addLayout(r1)
        r2 = QHBoxLayout(); r2.addWidget(QLabel("ยืนยัน:")); self.password_confirm = QLineEdit(); self.password_confirm.setEchoMode(QLineEdit.Password); self.password_confirm.setPlaceholderText("ยืนยันรหัสผ่าน…"); r2.addWidget(self.password_confirm); v.addLayout(r2)
        crypto_group.setLayout(v); col.addWidget(crypto_group)

        # 5) Auto-analysis
        analysis_group = QGroupBox("5. การวิเคราะห์อัตโนมัติ")
        v = QVBoxLayout()
        self.auto_analyze = QCheckBox("วิเคราะห์ความเสี่ยงอัตโนมัติหลังซ่อนข้อมูล"); self.auto_analyze.setChecked(True)
        self.auto_neutralize = QCheckBox("ทำให้เป็นกลางอัตโนมัติหากพบความเสี่ยงสูง")
        v.addWidget(self.auto_analyze); v.addWidget(self.auto_neutralize)
        analysis_group.setLayout(v); col.addWidget(analysis_group)

        col.addStretch()
        return panel

    def _create_preview_panel(self):
        panel = QWidget(); col = QVBoxLayout(panel)
        group = QGroupBox("ตัวอย่างไฟล์"); v = QVBoxLayout()
        self.preview_label = QLabel("ยังไม่ได้เลือกไฟล์"); self.preview_label.setAlignment(Qt.AlignCenter); self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("QLabel{border:2px dashed #ccc; border-radius:5px; background:#f5f5f5;}")
        v.addWidget(self.preview_label)
        self.file_info_text = QTextEdit(); self.file_info_text.setReadOnly(True); self.file_info_text.setMaximumHeight(150); self.file_info_text.setPlaceholderText("ข้อมูลไฟล์จะแสดงที่นี่…")
        v.addWidget(self.file_info_text)
        group.setLayout(v)
        col.addWidget(group)
        return panel

    # ---- interactions ----
    def _switch_secret_mode(self, mode: str):
        if mode == 'file':
            self.secret_mode_file.setChecked(True); self.secret_mode_text.setChecked(False)
            self.secret_file_widget.setVisible(True); self.secret_text_widget.setVisible(False)
        else:
            self.secret_mode_file.setChecked(False); self.secret_mode_text.setChecked(True)
            self.secret_file_widget.setVisible(False); self.secret_text_widget.setVisible(True)

    def _browse_cover_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์ต้นฉบับ", "",
                                           "Image Files (*.png *.jpg *.jpeg *.bmp);;Audio Files (*.wav);;Video Files (*.mp4 *.avi);;All Files (*.*)")
        if f:
            self.cover_path = Path(f)
            self.cover_input.setText(str(self.cover_path))
            self._update_cover_info(); self._update_preview()

    def _browse_secret_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์ข้อมูลลับ", "", "All Files (*.*)")
        if f:
            self.secret_path = Path(f)
            self.secret_input.setText(str(self.secret_path))

    def _update_cover_info(self):
        if not self.cover_path or not self.cover_path.exists():
            return
        size_mb = self.cover_path.stat().st_size / (1024*1024)
        info = f"ชื่อไฟล์: {self.cover_path.name}\nขนาด: {size_mb:.2f} MB\nประเภท: {self.cover_path.suffix}"
        self.cover_info.setText(info)
        self.file_info_text.setText(info)

    def _update_preview(self):
        if not self.cover_path or not self.cover_path.exists():
            return
        if self.cover_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp"]:
            pix = QPixmap(str(self.cover_path))
            self.preview_label.setPixmap(pix.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.preview_label.setText(f"ไฟล์: {self.cover_path.name}\nประเภท: {self.cover_path.suffix}")

    def _update_method_info(self):
        texts = {
            0: "วิเคราะห์ภาพและเลือกบริเวณที่เหมาะสม (ขอบ/พื้นผิวรายละเอียด) เพื่อลดการตรวจจับ",
            1: "แก้ไข LSB โดยตรง เหมาะ PNG/BMP",
            2: "ใช้ค่าความต่างพิกเซล PVD เพื่อกำหนดจำนวนบิตที่ฝัง",
            3: "ซ่อนในโดเมนความถี่ของ JPEG (DCT) ทนการบีบอัด",
        }
        self.method_info.setText(texts.get(self.method_combo.currentIndex(), ""))

    def _toggle_encryption(self, checked: bool):
        self.password_input.setEnabled(checked)
        self.password_confirm.setEnabled(checked)

    def _start_embed(self):
        if not self.cover_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์ต้นฉบับ")
            return
        # gather secret
        if self.secret_mode_file.isChecked():
            if not self.secret_path:
                QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์ข้อมูลลับ")
                return
            secret_data = Path(self.secret_path).read_bytes()
        else:
            txt = self.secret_text_widget.toPlainText()
            if not txt:
                QMessageBox.warning(self, "คำเตือน", "กรุณากรอกข้อความที่ต้องการซ่อน")
                return
            secret_data = txt.encode('utf-8')
        # password
        password = None
        if self.use_encryption.isChecked():
            p1 = self.password_input.text(); p2 = self.password_confirm.text()
            if not p1:
                QMessageBox.warning(self, "คำเตือน", "กรุณากรอกรหัสผ่าน")
                return
            if p1 != p2:
                QMessageBox.warning(self, "คำเตือน", "รหัสผ่านไม่ตรงกัน")
                return
            password = p1
        # method
        method = {0: 'adaptive', 1: 'lsb', 2: 'pvd', 3: 'dct'}[self.method_combo.currentIndex()]

        from gui import WorkerThread  # lazy import
        params = {
            'cover_path': str(self.cover_path),
            'secret_data': secret_data,
            'password': password,
            'method': method,
            'auto_analyze': self.auto_analyze.isChecked(),
        }
        self.parent_window.worker = WorkerThread('embed', params)
        self.parent_window.worker.progress.connect(self.parent_window.progress_bar.setValue)
        self.parent_window.worker.status.connect(self.parent_window.status_label.setText)
        self.parent_window.worker.result.connect(self._on_embed_result)
        self.parent_window.worker.error.connect(self._on_error)
        self.parent_window.worker.finished.connect(self._on_finished)

        self.embed_btn.setEnabled(False)
        self.parent_window.progress_bar.setVisible(True)
        self.parent_window.worker.start()

    def _on_embed_result(self, result: dict):
        stego_path = result['stego_path']
        risk = result.get('risk_score')
        msg = f"ซ่อนข้อมูลสำเร็จ!\n\nไฟล์ที่สร้าง: {stego_path}"
        if risk:
            msg += f"\n\nคะแนนความเสี่ยง: {risk['score']}/100\nระดับ: {risk['level']}"
        QMessageBox.information(self, "สำเร็จ", msg)

    def _on_error(self, err: str):
        QMessageBox.critical(self, "ข้อผิดพลาด", f"เกิดข้อผิดพลาด:\n{err}")

    def _on_finished(self):
        self.embed_btn.setEnabled(True)
        self.parent_window.progress_bar.setVisible(False)


# ------------------------------
# Extract Tab
# ------------------------------
class ExtractTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent_window = parent
        self.stego_path: Path = None
        self.extracted_data: bytes = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 1) File selection
        file_group = QGroupBox("1. เลือกไฟล์ที่มีข้อมูลซ่อนอยู่")
        v = QVBoxLayout(); row = QHBoxLayout()
        self.file_input = QLineEdit(); self.file_input.setPlaceholderText("เลือกไฟล์…"); self.file_input.setReadOnly(True)
        row.addWidget(self.file_input)
        b = QPushButton("เลือกไฟล์"); b.clicked.connect(self._browse_file); row.addWidget(b)
        v.addLayout(row); file_group.setLayout(v); layout.addWidget(file_group)

        # 2) Method
        method_group = QGroupBox("2. เลือกวิธีการที่ใช้ซ่อนข้อมูล")
        v = QVBoxLayout()
        self.method_combo = QComboBox(); self.method_combo.addItems([
            "Adaptive (อัตโนมัติ)", "LSB Matching", "PVD", "DCT (JPEG)"
        ])
        v.addWidget(self.method_combo); method_group.setLayout(v); layout.addWidget(method_group)

        # 3) Decryption
        dec_group = QGroupBox("3. การถอดรหัส")
        v = QVBoxLayout()
        self.use_decryption = QCheckBox("ข้อมูลถูกเข้ารหัส"); self.use_decryption.setChecked(True); v.addWidget(self.use_decryption)
        row = QHBoxLayout(); row.addWidget(QLabel("รหัสผ่าน:")); self.password_input = QLineEdit(); self.password_input.setEchoMode(QLineEdit.Password); row.addWidget(self.password_input); v.addLayout(row)
        dec_group.setLayout(v); layout.addWidget(dec_group)

        # 4) Output
        out_group = QGroupBox("4. ผลลัพธ์"); v = QVBoxLayout()
        self.output_text = QTextEdit(); self.output_text.setReadOnly(True); self.output_text.setPlaceholderText("ข้อมูลที่ดึงออกมาจะแสดงที่นี่…")
        v.addWidget(self.output_text)
        save_btn = QPushButton("💾 บันทึกเป็นไฟล์"); save_btn.clicked.connect(self._save_extracted)
        v.addWidget(save_btn)
        out_group.setLayout(v); layout.addWidget(out_group)

        actions = QHBoxLayout(); actions.addStretch()
        self.extract_btn = QPushButton("🔓 ดึงข้อมูล"); self.extract_btn.setMinimumHeight(40); self.extract_btn.clicked.connect(self._start_extract)
        actions.addWidget(self.extract_btn)
        layout.addLayout(actions)

    def _browse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์", "", "All Files (*.*)")
        if f:
            self.stego_path = Path(f)
            self.file_input.setText(str(self.stego_path))

    def _start_extract(self):
        if not self.stego_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์")
            return
        password = None
        if self.use_decryption.isChecked():
            password = self.password_input.text()
            if not password:
                QMessageBox.warning(self, "คำเตือน", "กรุณากรอกรหัสผ่าน")
                return
        method = {0: 'adaptive', 1: 'lsb', 2: 'pvd', 3: 'dct'}[self.method_combo.currentIndex()]

        from gui import WorkerThread
        params = {'stego_path': str(self.stego_path), 'password': password, 'method': method}
        self.parent_window.worker = WorkerThread('extract', params)
        self.parent_window.worker.progress.connect(self.parent_window.progress_bar.setValue)
        self.parent_window.worker.status.connect(self.parent_window.status_label.setText)
        self.parent_window.worker.result.connect(self._on_result)
        self.parent_window.worker.error.connect(self._on_error)
        self.parent_window.worker.finished.connect(self._on_finished)
        self.extract_btn.setEnabled(False)
        self.parent_window.progress_bar.setVisible(True)
        self.parent_window.worker.start()

    def _on_result(self, result: dict):
        self.extracted_data = result['data']
        try:
            self.output_text.setText(self.extracted_data.decode('utf-8'))
        except Exception:
            self.output_text.setText(f"ดึงข้อมูลไบนารีสำเร็จ ({len(self.extracted_data)} bytes)\n\nกรุณาบันทึกเป็นไฟล์")
        QMessageBox.information(self, "สำเร็จ", "ดึงข้อมูลสำเร็จ!")

    def _save_extracted(self):
        if not self.extracted_data:
            QMessageBox.warning(self, "คำเตือน", "ยังไม่มีข้อมูลที่ดึงออกมา")
            return
        f, _ = QFileDialog.getSaveFileName(self, "บันทึกไฟล์", "", "All Files (*.*)")
        if f:
            Path(f).write_bytes(self.extracted_data)
            QMessageBox.information(self, "สำเร็จ", f"บันทึกไฟล์สำเร็จ: {f}")

    def _on_error(self, err: str):
        QMessageBox.critical(self, "ข้อผิดพลาด", f"เกิดข้อผิดพลาด:\n{err}")

    def _on_finished(self):
        self.extract_btn.setEnabled(True)
        self.parent_window.progress_bar.setVisible(False)


# ------------------------------
# Analyze Tab
# ------------------------------
class AnalyzeTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent_window = parent
        self.file_path: Path = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # file
        g = QGroupBox("1. เลือกไฟล์สำหรับวิเคราะห์"); v = QVBoxLayout(); row = QHBoxLayout()
        self.file_input = QLineEdit(); self.file_input.setPlaceholderText("เลือกไฟล์ภาพ…"); self.file_input.setReadOnly(True)
        row.addWidget(self.file_input)
        b = QPushButton("เลือกไฟล์"); b.clicked.connect(self._browse_file); row.addWidget(b)
        v.addLayout(row); g.setLayout(v); layout.addWidget(g)

        # methods
        g = QGroupBox("2. วิธีการวิเคราะห์"); v = QVBoxLayout()
        self.chi = QCheckBox("Chi-Square Attack (LSB)"); self.chi.setChecked(True)
        self.ela = QCheckBox("Error Level Analysis (JPEG)"); self.ela.setChecked(True)
        self.hist = QCheckBox("Histogram Analysis"); self.hist.setChecked(True)
        self.ml = QCheckBox("Machine Learning (ทดลอง)")
        for w in (self.chi, self.ela, self.hist, self.ml): v.addWidget(w)
        g.setLayout(v); layout.addWidget(g)

        # actions
        actions = QHBoxLayout(); actions.addStretch()
        self.btn = QPushButton("🔍 วิเคราะห์ไฟล์"); self.btn.setMinimumHeight(40); self.btn.clicked.connect(self._start)
        actions.addWidget(self.btn); layout.addLayout(actions)

        # result
        g = QGroupBox("ผลการวิเคราะห์"); v = QVBoxLayout()
        score_row = QHBoxLayout(); score_row.addWidget(QLabel("Risk Score:"))
        self.score_label = QLabel("--"); self.score_label.setStyleSheet("font-size:36px; font-weight:bold; color:#4CAF50; padding:10px;")
        self.level_label = QLabel("No Analysis Yet"); self.level_label.setStyleSheet("font-size:14px; padding:5px;")
        score_row.addWidget(self.score_label); score_row.addWidget(self.level_label); score_row.addStretch()
        self.result_text = QTextEdit(); self.result_text.setReadOnly(True); self.result_text.setPlaceholderText("Analysis results will appear here…")
        v.addLayout(score_row); v.addWidget(self.result_text); g.setLayout(v); layout.addWidget(g)

    def _browse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์", "", "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)")
        if f: self.file_input.setText(f); self.file_path = Path(f)

    def _start(self):
        if not self.file_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์ที่จะวิเคราะห์")
            return
        methods: List[str] = []
        if self.chi.isChecked(): methods.append('chi-square')
        if self.ela.isChecked(): methods.append('ela')
        if self.hist.isChecked(): methods.append('histogram')
        if self.ml.isChecked(): methods.append('ml')
        if not methods: methods = ['all']

        from gui import WorkerThread
        params = {'file_path': str(self.file_path), 'methods': methods}
        self.parent_window.worker = WorkerThread('analyze', params)
        self.parent_window.worker.progress.connect(self.parent_window.progress_bar.setValue)
        self.parent_window.worker.status.connect(self.parent_window.status_label.setText)
        self.parent_window.worker.result.connect(self._on_result)
        self.parent_window.worker.error.connect(self._on_error)
        self.parent_window.worker.finished.connect(self._on_finished)
        self.btn.setEnabled(False); self.parent_window.progress_bar.setVisible(True)
        self.parent_window.worker.start()

    def _on_result(self, res: dict):
        # normalize result (support simulator)
        score = res.get('score')
        level = res.get('level')
        if score is None:
            score = 42; level = 'MEDIUM'
        color = '#4CAF50' if score < 30 else ('#FF9800' if score < 60 else '#F44336')
        self.score_label.setText(str(score))
        self.score_label.setStyleSheet(f"font-size:36px; font-weight:bold; color:{color}; padding:10px;")
        self.level_label.setText(level)
        self.level_label.setStyleSheet(f"font-size:14px; padding:5px; color:{color};")
        details = res.get('details', {})
        self.result_text.setText(f"Chi-Square: {details.get('chi_square', '—')}\nHistogram: {details.get('histogram', '—')}\nELA: {details.get('ela', '—')}")

    def _on_error(self, err: str):
        QMessageBox.critical(self, "ข้อผิดพลาด", f"วิเคราะห์ล้มเหลว:\n{err}")

    def _on_finished(self):
        self.btn.setEnabled(True); self.parent_window.progress_bar.setVisible(False)


# ------------------------------
# Neutralize Tab
# ------------------------------
class NeutralizeTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent_window = parent
        self.file_path: Path = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # file
        g = QGroupBox("1. เลือกไฟล์ที่จะทำให้เป็นกลาง"); v = QVBoxLayout(); row = QHBoxLayout()
        self.file_input = QLineEdit(); self.file_input.setPlaceholderText("เลือกไฟล์…"); self.file_input.setReadOnly(True)
        row.addWidget(self.file_input)
        b = QPushButton("เลือกไฟล์"); b.clicked.connect(self._browse); row.addWidget(b)
        v.addLayout(row); g.setLayout(v); layout.addWidget(g)

        # methods
        g = QGroupBox("2. วิธีการทำให้เป็นกลาง"); v = QVBoxLayout()
        self.m_meta = QCheckBox("Strip EXIF/Metadata"); self.m_meta.setChecked(True)
        self.m_recomp = QCheckBox("Re-compress Image"); self.m_recomp.setChecked(True)
        self.m_transform = QCheckBox("Transform (resize / noise)")
        for w in (self.m_meta, self.m_recomp, self.m_transform): v.addWidget(w)
        g.setLayout(v); layout.addWidget(g)

        # actions
        actions = QHBoxLayout(); actions.addStretch()
        self.btn = QPushButton("🛡️ ทำให้เป็นกลาง"); self.btn.setMinimumHeight(40); self.btn.clicked.connect(self._start)
        actions.addWidget(self.btn); layout.addLayout(actions)

        # result
        g = QGroupBox("ผลการประมวลผล"); v = QVBoxLayout()
        self.result_text = QTextEdit(); self.result_text.setReadOnly(True); self.result_text.setPlaceholderText("Neutralization log will appear here…")
        v.addWidget(self.result_text); g.setLayout(v); layout.addWidget(g)

    def _browse(self):
        f, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์", "", "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)")
        if f: self.file_input.setText(f); self.file_path = Path(f)

    def _start(self):
        if not self.file_path:
            QMessageBox.warning(self, "คำเตือน", "กรุณาเลือกไฟล์")
            return
        methods = []
        if self.m_meta.isChecked(): methods.append('metadata')
        if self.m_recomp.isChecked(): methods.append('recompress')
        if self.m_transform.isChecked(): methods.append('transform')
        if not methods: methods = ['metadata']

        from gui import WorkerThread
        params = {'file_path': str(self.file_path), 'methods': methods}
        self.parent_window.worker = WorkerThread('neutralize', params)
        self.parent_window.worker.progress.connect(self.parent_window.progress_bar.setValue)
        self.parent_window.worker.status.connect(self.parent_window.status_label.setText)
        self.parent_window.worker.result.connect(self._on_result)
        self.parent_window.worker.error.connect(self._on_error)
        self.parent_window.worker.finished.connect(self._on_finished)
        self.btn.setEnabled(False); self.parent_window.progress_bar.setVisible(True)
        self.parent_window.worker.start()

    def _on_result(self, res: dict):
        out = res.get('output_path', 'neutralized_output.png')
        used = ", ".join(res.get('methods', []))
        self.result_text.setText(f"=== NEUTRALIZATION COMPLETE ===\nMethods: {used}\nOutput: {out}")
        QMessageBox.information(self, "สำเร็จ", "ไฟล์ถูกทำให้เป็นกลางเรียบร้อย")

    def _on_error(self, err: str):
        QMessageBox.critical(self, "ข้อผิดพลาด", f"Neutralization ล้มเหลว:\n{err}")

    def _on_finished(self):
        self.btn.setEnabled(True); self.parent_window.progress_bar.setVisible(False)