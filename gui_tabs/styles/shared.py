"""Shared style helpers for STEGOSIGHT GUI tabs."""

from __future__ import annotations

def combine_styles(*styles: str) -> str:
    """Join style fragments into a single stylesheet string."""

    normalized = []
    for style in styles:
        if not style:
            continue
        text = style.strip()
        if text:
            normalized.append(text)
    return "\n\n".join(normalized)


COMMON_COMPONENT_STYLES = """
#actionButton {
    background-color: #1E88E5;
    color: white;
    border: none;
    padding: 12px 26px;
    border-radius: 8px;
    font-size: 15px;
    font-weight: 600;
}
#actionButton:disabled {
    background-color: #b0bec5;
    color: #eceff1;
}

#toggleButton {
    background-color: white;
    color: #333;
    border: 2px solid #ddd;
    border-radius: 6px;
    padding: 8px 18px;
}
#toggleButton:hover {
    border-color: #1E88E5;
}
#toggleButton:checked {
    background-color: #1E88E5;
    color: white;
    border-color: #1E88E5;
}

#infoBox {
    background-color: #e3f2fd;
    border: 1px solid #bbdefb;
    border-left: 4px solid #1E88E5;
    padding: 12px;
    border-radius: 6px;
    font-size: 12px;
    color: #0d47a1;
}

#infoPanel {
    background-color: white;
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #ddd;
    margin-top: 10px;
}

#previewArea {
    border: 2px dashed #ccc;
    border-radius: 10px;
    background-color: #f9f9f9;
    color: #999;
}

#methodCard {
    background-color: white;
    border: 2px solid #ddd;
    border-radius: 10px;
    padding: 16px;
}
#methodCard:hover {
    border-color: #1E88E5;
    background-color: #f0f7ff;
}
#methodCard[selected="true"] {
    background-color: #e3f2fd;
    border: 2px solid #1E88E5;
}
#methodCardTitle {
    color: #1E88E5;
    font-weight: 700;
    font-size: 14px;
}
#methodCardDesc {
    color: #666;
    font-size: 12px;
}
"""
