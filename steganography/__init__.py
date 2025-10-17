"""STEGOSIGHT Steganography Module."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "AdaptiveSteganography",
    "JPEGDCTSteganography",
    "LSBSteganography",
    "PVDSteganography",
    "APPEND_MARKER",
    "append_payload_to_file",
    "extract_appended_payload",
    "has_appended_payload",
    "embed_file_into_png_chunk",
    "extract_file_from_png_chunk",
    "extract_payload_from_png_chunk",
]


if TYPE_CHECKING:  # pragma: no cover - only for typing
    from .adaptive import AdaptiveSteganography
    from .appender import (
        APPEND_MARKER,
        append_payload_to_file,
        extract_appended_payload,
        has_appended_payload,
    )
    from .jpeg_dct import JPEGDCTSteganography
    from .lsb import LSBSteganography
    from .pvd import PVDSteganography
    from .png_chunk import (
        embed_file_into_png_chunk,
        extract_file_from_png_chunk,
        extract_payload_from_png_chunk,
    )


def __getattr__(name: str) -> Any:
    if name == "AdaptiveSteganography":
        return import_module(".adaptive", __name__).AdaptiveSteganography
    if name == "JPEGDCTSteganography":
        return import_module(".jpeg_dct", __name__).JPEGDCTSteganography
    if name == "LSBSteganography":
        return import_module(".lsb", __name__).LSBSteganography
    if name == "PVDSteganography":
        return import_module(".pvd", __name__).PVDSteganography
    if name in {
        "APPEND_MARKER",
        "append_payload_to_file",
        "extract_appended_payload",
        "has_appended_payload",
    }:
        module = import_module(".appender", __name__)
        return getattr(module, name)
    if name in {
        "embed_file_into_png_chunk",
        "extract_file_from_png_chunk",
        "extract_payload_from_png_chunk",
    }:
        module = import_module(".png_chunk", __name__)
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
