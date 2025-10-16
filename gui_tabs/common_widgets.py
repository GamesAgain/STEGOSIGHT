"""Common reusable widgets for the STEGOSIGHT GUI tabs."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout


class MethodCard(QFrame):
    """A clickable card widget for selecting a steganography method."""

    clicked = pyqtSignal(object)

    def __init__(self, title: str, description: str, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("methodCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("methodCardTitle")
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setObjectName("methodCardDesc")

        layout.addWidget(title_label)
        layout.addWidget(desc_label)

        self.setAutoFillBackground(True)
        self.setSelected(False)

    def mousePressEvent(self, event):  # type: ignore[override]
        self.clicked.emit(self)
        super().mousePressEvent(event)

    def setSelected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        # trigger style refresh
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class RiskScoreWidget(QFrame):
    """A compact widget that shows a risk score and level."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("riskScoreWidget")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        layout.addWidget(self._create_label("Risk Score", "riskScoreLabel"))
        self.score_label = self._create_label("—", "riskScoreNumber")
        layout.addWidget(self.score_label)
        self.level_label = self._create_label("NOT ANALYZED", "riskScoreLevel")
        layout.addWidget(self.level_label)
        self.desc_label = self._create_label(
            "เลือกไฟล์และกดวิเคราะห์เพื่อดูผลลัพธ์", "riskScoreDesc", True
        )
        layout.addWidget(self.desc_label)

    def _create_label(self, text: str, object_name: str, word_wrap: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(word_wrap)
        return label

    def set_score(self, score: int, level: str, description: str, color: str) -> None:
        self.score_label.setText(str(score))
        self.level_label.setText(level)
        self.desc_label.setText(description)

        style = f"color: {color};"
        self.score_label.setStyleSheet(style)
        self.level_label.setStyleSheet(style)


class InfoPanel(QFrame):
    """A styled panel that aligns file information in a grid layout."""

    def __init__(self, labels, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("infoPanel")
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(6)
        layout.setColumnStretch(1, 1)

        self.value_labels = {}
        for row, text in enumerate(labels):
            key = QLabel(f"{text}:")
            value = QLabel("—")
            value.setStyleSheet("font-weight: bold;")

            layout.addWidget(key, row, 0)
            layout.addWidget(value, row, 1)
            self.value_labels[text] = value

    def set_value(self, label: str, value: str) -> None:
        if label in self.value_labels:
            self.value_labels[label].setText(value)
