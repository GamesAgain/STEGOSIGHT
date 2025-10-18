"""Embed view implementation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThreadPool, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.stego_engine import EmbedOptions, IStegoEngine
from ...core.types import OperationResult
from ...utils.threading import Worker, WorkerConfig
from ...utils.validators import estimate_capacity, validate_carrier_path
from ..widgets.file_picker import FilePicker


@dataclass(slots=True)
class EmbedFormData:
    """Aggregated data from the embed form."""

    carrier: Path
    payload_text: str | None
    payload_file: Path | None
    password: str | None
    encryption: bool
    kdf_memory: int
    kdf_iterations: int
    kdf_parallelism: int
    method: str
    techniques: list[str]
    output_dir: Path
    filename_template: str
    media_type: str


class EmbedView(QWidget):
    """UI for embedding payloads into carrier files."""

    analyzeRequested = pyqtSignal(Path)
    operationFinished = pyqtSignal(OperationResult)

    def __init__(self, engine: IStegoEngine, thread_pool: QThreadPool | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._progress_dialog: Optional[QProgressDialog] = None
        self._last_result: Optional[Path] = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Embed payload into carrier media")
        header.setObjectName("viewTitle")
        layout.addWidget(header)

        carrier_box = QGroupBox("Carrier")
        carrier_layout = QFormLayout(carrier_box)
        self._carrier_picker = FilePicker(
            self,
            "Select carrier",
            [
                "Images (*.png *.jpg *.jpeg *.bmp)",
                "Audio (*.wav *.mp3 *.flac *.wma *.aac)",
                "Video (*.avi *.mp4 *.mkv *.mov *.ogg)",
            ],
        )
        self._carrier_picker.pathChanged.connect(self._on_carrier_changed)
        carrier_layout.addRow("Carrier file", self._carrier_picker)
        self._capacity_label = QLabel("Capacity: —")
        carrier_layout.addRow("Estimated capacity", self._capacity_label)
        layout.addWidget(carrier_box)

        payload_box = QGroupBox("Payload")
        payload_layout = QVBoxLayout(payload_box)
        self._payload_mode = QComboBox()
        self._payload_mode.addItems(["Text", "File"])
        payload_layout.addWidget(self._payload_mode)
        self._payload_stack = QStackedWidget()
        self._payload_text_edit = QPlainTextEdit()
        self._payload_text_edit.setPlaceholderText("Enter secret message…")
        self._payload_file_picker = FilePicker(self, "Select payload file")
        self._payload_stack.addWidget(self._payload_text_edit)
        self._payload_stack.addWidget(self._payload_file_picker)
        payload_layout.addWidget(self._payload_stack)
        self._payload_mode.currentIndexChanged.connect(self._payload_stack.setCurrentIndex)
        layout.addWidget(payload_box)

        security_box = QGroupBox("Security")
        security_layout = QGridLayout(security_box)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        security_layout.addWidget(QLabel("Password"), 0, 0)
        security_layout.addWidget(self._password_edit, 0, 1)
        self._encryption_toggle = QCheckBox("Enable AES-256-GCM")
        self._encryption_toggle.setChecked(True)
        security_layout.addWidget(self._encryption_toggle, 1, 0, 1, 2)
        self._kdf_memory = QSpinBox()
        self._kdf_memory.setRange(32, 1024)
        self._kdf_memory.setSuffix(" MB")
        self._kdf_memory.setValue(64)
        self._kdf_iterations = QSpinBox()
        self._kdf_iterations.setRange(1, 10)
        self._kdf_iterations.setValue(3)
        self._kdf_parallelism = QSpinBox()
        self._kdf_parallelism.setRange(1, 16)
        self._kdf_parallelism.setValue(2)
        security_layout.addWidget(QLabel("Memory"), 2, 0)
        security_layout.addWidget(self._kdf_memory, 2, 1)
        security_layout.addWidget(QLabel("Time cost"), 3, 0)
        security_layout.addWidget(self._kdf_iterations, 3, 1)
        security_layout.addWidget(QLabel("Parallelism"), 4, 0)
        security_layout.addWidget(self._kdf_parallelism, 4, 1)
        layout.addWidget(security_box)

        mode_box = QGroupBox("Embedding Strategy")
        mode_layout = QVBoxLayout(mode_box)
        self._method_combo = QComboBox()
        self._method_combo.addItems(["Adaptive", "Manual", "Integrated"])
        mode_layout.addWidget(self._method_combo)
        self._techniques_label = QLabel("Techniques: LSB Matching, Metadata")
        mode_layout.addWidget(self._techniques_label)
        self._imperceptibility_slider = QSlider(Qt.Orientation.Horizontal)
        self._imperceptibility_slider.setRange(0, 100)
        self._imperceptibility_slider.setValue(70)
        mode_layout.addWidget(QLabel("Imperceptibility vs Capacity"))
        mode_layout.addWidget(self._imperceptibility_slider)
        layout.addWidget(mode_box)

        output_box = QGroupBox("Output")
        output_layout = QFormLayout(output_box)
        self._output_dir_picker = FilePicker(self, "Select output folder", select_directory=True)
        output_layout.addRow("Output folder", self._output_dir_picker)
        self._filename_template = QLineEdit("stego_{timestamp}")
        output_layout.addRow("Filename", self._filename_template)
        layout.addWidget(output_box)

        buttons = QHBoxLayout()
        self._embed_button = QPushButton("Embed")
        self._reset_button = QPushButton("Reset")
        self._analyze_button = QPushButton("Analyze Result")
        self._analyze_button.setEnabled(False)
        buttons.addWidget(self._embed_button)
        buttons.addWidget(self._reset_button)
        buttons.addWidget(self._analyze_button)
        layout.addLayout(buttons)
        layout.addStretch(1)

        self._embed_button.clicked.connect(self._handle_embed)
        self._reset_button.clicked.connect(self._reset_form)
        self._analyze_button.clicked.connect(self._emit_analyze)

    def _collect_form_data(self) -> EmbedFormData | None:
        carrier = self._carrier_picker.path
        if not carrier:
            return None
        payload_text: str | None = None
        payload_file: Path | None = None
        if self._payload_mode.currentText().lower() == "text":
            payload_text = self._payload_text_edit.toPlainText()
        else:
            payload_file = self._payload_file_picker.path
        return EmbedFormData(
            carrier=carrier,
            payload_text=payload_text or None,
            payload_file=payload_file,
            password=self._password_edit.text() or None,
            encryption=self._encryption_toggle.isChecked(),
            kdf_memory=self._kdf_memory.value(),
            kdf_iterations=self._kdf_iterations.value(),
            kdf_parallelism=self._kdf_parallelism.value(),
            method=self._method_combo.currentText().lower(),
            techniques=["lsb_match", "metadata"],
            output_dir=self._output_dir_picker.path or carrier.parent,
            filename_template=self._filename_template.text(),
            media_type="image",
        )

    def _on_carrier_changed(self, path: Path) -> None:
        validation = validate_carrier_path(path)
        if not validation.valid:
            self._capacity_label.setText(validation.message)
            return
        try:
            capacity = estimate_capacity(path)
        except Exception as exc:  # pragma: no cover - defensive
            self._capacity_label.setText(str(exc))
        else:
            self._capacity_label.setText(f"Approx. {capacity:,} bytes")

    def _reset_form(self) -> None:
        self._carrier_picker.path = None
        self._payload_text_edit.clear()
        self._payload_file_picker.path = None
        self._password_edit.clear()
        self._encryption_toggle.setChecked(True)
        self._analyze_button.setEnabled(False)
        self._capacity_label.setText("Capacity: —")

    def _handle_embed(self) -> None:
        data = self._collect_form_data()
        if not data:
            return
        validation = validate_carrier_path(data.carrier)
        if not validation.valid:
            self._capacity_label.setText(validation.message)
            return
        if data.payload_file and data.payload_file.exists():
            payload = data.payload_file.read_bytes()
        elif data.payload_text:
            payload = data.payload_text.encode()
        else:
            payload = b""
        options = EmbedOptions(
            media_type=data.media_type,  # type: ignore[arg-type]
            method=data.method,  # type: ignore[arg-type]
            techniques=data.techniques,
            params={"imperceptibility": self._imperceptibility_slider.value()},
            payload_kind="text" if data.payload_text else "file",
            encryption=data.encryption,
            kdf={
                "memory": data.kdf_memory,
                "time_cost": data.kdf_iterations,
                "parallelism": data.kdf_parallelism,
            },
            output_dir=data.output_dir,
        )
        config = WorkerConfig(
            fn=self._engine.embed,
            args=(data.carrier, payload, options),
        )
        worker = Worker(config)
        worker.signals.result.connect(self._on_embed_result)
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.finished.connect(self._close_progress)
        self._thread_pool.start(worker)
        self._show_progress(worker)

    def _show_progress(self, worker: Worker) -> None:
        dialog = QProgressDialog("Embedding…", "Cancel", 0, 0, self)
        dialog.setWindowTitle("Embedding")
        dialog.canceled.connect(worker.cancel)
        dialog.show()
        self._progress_dialog = dialog

    def _close_progress(self) -> None:
        if self._progress_dialog:
            self._progress_dialog.hide()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None

    def _on_worker_error(self, exc: Exception) -> None:
        result = OperationResult(
            operation="embed",
            target=Path(),
            success=False,
            message=str(exc),
            duration_s=0.0,
        )
        self.operationFinished.emit(result)

    def _on_embed_result(self, path: Path) -> None:
        self._analyze_button.setEnabled(True)
        self._last_result = path
        result = OperationResult(
            operation="embed",
            target=path,
            success=True,
            message="Embedding finished",
            duration_s=0.0,
        )
        self.operationFinished.emit(result)

    def _emit_analyze(self) -> None:
        if self._last_result:
            self.analyzeRequested.emit(self._last_result)
