"""Stylesheet helpers for the extract tab."""

from PyQt5.QtWidgets import QWidget

from .shared import COMMON_COMPONENT_STYLES, combine_styles


EXTRACT_SPECIFIC = """
#previewArea {
    min-height: 200px;
}
"""


def apply_extract_styles(widget: QWidget) -> None:
    """Apply the stylesheet for the extract tab."""

    widget.setStyleSheet(combine_styles(COMMON_COMPONENT_STYLES, EXTRACT_SPECIFIC))
