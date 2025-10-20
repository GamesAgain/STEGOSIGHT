"""Stylesheet helpers for the analyze tab."""

from PyQt5.QtWidgets import QWidget

from .shared import COMMON_COMPONENT_STYLES, combine_styles


ANALYZE_SPECIFIC = """
#visualRiskGauge {
    background-color: #ffffff;
    border: 1px solid #e0e7ff;
    border-radius: 12px;
    padding: 18px;
}
#visualRiskGauge QLabel {
    color: #1f2937;
}

#visualMetricsFrame {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px;
}
#visualMetricLabel {
    font-weight: 600;
    color: #374151;
}

#liveLogConsole {
    background-color: #111827;
    color: #e5e7eb;
    border-radius: 10px;
    padding: 12px;
    font-family: 'JetBrains Mono', 'Cascadia Code', monospace;
    font-size: 12px;
}

#summaryContainer {
    background-color: #eef2ff;
    border: 1px solid #c7d2fe;
    border-radius: 12px;
    padding: 18px;
}
#summaryTitle {
    font-weight: 700;
    font-size: 15px;
    color: #312e81;
}

#guidanceFrame {
    background-color: #ecfdf5;
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 18px;
}

#riskScoreWidget {
    background-color: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
}
#riskScoreLabel {
    font-size: 14px;
    color: #4b5563;
}
#riskScoreNumber {
    font-size: 60px;
    font-weight: 800;
}
#riskScoreLevel {
    font-size: 16px;
    font-weight: 700;
}
#riskScoreDesc {
    font-size: 13px;
    color: #6b7280;
    margin-top: 6px;
}
"""


def apply_analyze_styles(widget: QWidget) -> None:
    """Apply the stylesheet for the analyze tab."""

    widget.setStyleSheet(combine_styles(COMMON_COMPONENT_STYLES, ANALYZE_SPECIFIC))
