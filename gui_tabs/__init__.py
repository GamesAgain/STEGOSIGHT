"""Modular GUI tabs for the STEGOSIGHT application."""

from .embed_tab import EmbedTab
from .extract_tab import ExtractTab
from .analyze_tab import AnalyzeTab
from .neutralize_tab import NeutralizeTab
from .workbench_tab import WorkbenchTab

__all__ = [
    "EmbedTab",
    "ExtractTab",
    "AnalyzeTab",
    "NeutralizeTab",
    "WorkbenchTab",
]
