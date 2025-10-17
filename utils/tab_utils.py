"""Helper widgets and utilities for consistent tab presentations in the GUI."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTabBar


class FullTextTabBar(QTabBar):
    """A ``QTabBar`` subclass that keeps tab text fully visible.

    The default ``QTabBar`` in Qt tends to elide (replace with ellipses) or
    truncate long tab labels when there is not enough horizontal space.  The
    STEGOSIGHT interface makes heavy use of descriptive (and multilingual)
    labels which can easily get cropped.  This helper tab bar calculates the
    minimum size required for each tab based on the text width and applies a
    bit of extra padding so that the labels remain readable.  Scroll buttons
    are automatically enabled when the combined width exceeds the available
    space.
    """

    def __init__(
        self,
        *,
        minimum_width: int = 160,
        extra_padding: int = 48,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._minimum_width = minimum_width
        self._extra_padding = extra_padding
        self.setElideMode(Qt.ElideNone)
        self.setUsesScrollButtons(True)
        self.setExpanding(False)

    def tabSizeHint(self, index: int):  # type: ignore[override]
        size = super().tabSizeHint(index)
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(self.tabText(index))
        desired_width = max(self._minimum_width, text_width + self._extra_padding)
        size.setWidth(desired_width)
        size.setHeight(max(size.height(), metrics.height() + 18))
        return size
