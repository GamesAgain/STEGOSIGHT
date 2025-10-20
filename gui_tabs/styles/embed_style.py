"""Stylesheet helpers for the embed tab."""

from PyQt5.QtWidgets import QWidget

from .shared import COMMON_COMPONENT_STYLES, combine_styles


EMBED_SPECIFIC = """
#previewArea {
    min-height: 240px;
}
"""


def apply_embed_styles(widget: QWidget) -> None:
    """Apply the stylesheet for the embed tab."""

    widget.setStyleSheet(combine_styles(COMMON_COMPONENT_STYLES, EMBED_SPECIFIC))
