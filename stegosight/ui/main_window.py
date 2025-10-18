"""Main window implementation for STEGOSIGHT."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSettings,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.analysis import IAnalyzer
from ..core.neutralize import INeutralizer
from ..core.stego_engine import IStegoEngine
from ..core.types import OperationResult
from ..utils.i18n import translate
from .views.analyze_view import AnalyzeView
from .views.embed_view import EmbedView
from .views.extract_view import ExtractView
from .views.history_view import HistoryView
from .views.neutralize_view import NeutralizeView
from .views.settings_view import SettingsView


NAV_ITEMS = [
    ("Embed", "icons/embed.png"),
    ("Extract", "icons/extract.png"),
    ("Analyze", "icons/analyze.png"),
    ("Neutralize", "icons/neutralize.png"),
    ("Settings", "icons/settings.png"),
    ("History", "icons/history.png"),
]


@dataclass(slots=True)
class ViewRecord:
    name: str
    widget: QWidget


class MainWindow(QMainWindow):
    """Application main window with navigation sidebar."""

    def __init__(
        self,
        engine: IStegoEngine,
        analyzer: IAnalyzer,
        neutralizer: INeutralizer,
        settings_factory: Callable[[], QSettings],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("STEGOSIGHT")
        self.resize(1200, 800)

        self._engine = engine
        self._analyzer = analyzer
        self._neutralizer = neutralizer
        self._settings_factory = settings_factory

        self._views: Dict[str, ViewRecord] = {}

        self._history_view = HistoryView()
        self._stack = QStackedWidget()
        self._nav_list = QListWidget()
        self._nav_list.setIconSize(QSize(24, 24))
        self._nav_list.setSpacing(8)
        self._nav_list.setFixedWidth(180)

        container = QWidget()
        root_layout = QVBoxLayout(container)
        splitter = QSplitter()
        splitter.addWidget(self._nav_list)
        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(container)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._build_views()
        self._build_navigation()
        self._nav_list.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav_list.setCurrentRow(0)

    def _build_views(self) -> None:
        embed_view = EmbedView(self._engine)
        embed_view.operationFinished.connect(self._record_history)
        embed_view.analyzeRequested.connect(self._handle_analyze_request)
        self._add_view("Embed", embed_view)

        extract_view = ExtractView(self._engine)
        extract_view.operationFinished.connect(self._record_history)
        self._add_view("Extract", extract_view)

        analyze_view = AnalyzeView(self._analyzer)
        analyze_view.operationFinished.connect(self._record_history)
        self._add_view("Analyze", analyze_view)

        neutralize_view = NeutralizeView(self._neutralizer, self._analyzer)
        neutralize_view.operationFinished.connect(self._record_history)
        self._add_view("Neutralize", neutralize_view)

        settings_view = SettingsView(self._settings_factory())
        self._add_view("Settings", settings_view)

        self._add_view("History", self._history_view)

    def _build_navigation(self) -> None:
        for idx, (name, icon_path) in enumerate(NAV_ITEMS):
            icon = QIcon(icon_path) if Path(icon_path).exists() else QIcon()
            item = QListWidgetItem(icon, translate(name))
            self._nav_list.addItem(item)
            self._stack.insertWidget(idx, self._views[name].widget)

    def _add_view(self, name: str, widget: QWidget) -> None:
        self._views[name] = ViewRecord(name=name, widget=widget)

    def _record_history(self, result: OperationResult) -> None:
        self._status_bar.showMessage(f"{result.operation.title()} completed: {result.message}", 5000)
        self._history_view.add_entry(result)

    def _handle_analyze_request(self, path: Path) -> None:
        for idx, (name, _) in enumerate(NAV_ITEMS):
            if name == "Analyze":
                self._nav_list.setCurrentRow(idx)
                break
        # Future wiring: pre-populate analyze view with the provided path.

    @classmethod
    def create_with_interfaces(
        cls,
        engine: IStegoEngine,
        analyzer: IAnalyzer,
        neutralizer: INeutralizer,
        settings_factory: Callable[[], QSettings],
    ) -> "MainWindow":
        """Convenience constructor aligning with dependency inversion."""

        return cls(engine=engine, analyzer=analyzer, neutralizer=neutralizer, settings_factory=settings_factory)
