"""STEGOSIGHT Steganography Module."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "AdaptiveSteganography",
    "JPEGDCTSteganography",
    "LSBSteganography",
    "PVDSteganography",
    "AudioSteganography",
    "VideoSteganography",
    "APPEND_MARKER",
    "APPEND_VERSION",
    "AppendedPayload",
    "append_payload_to_file",
    "extract_appended_payload",
    "has_appended_payload",
    "CUSTOM_CHUNK_TYPE",
    "embed_data_in_chunk",
    "extract_data_from_chunk",
]


if TYPE_CHECKING:  # pragma: no cover - only for typing
    from .adaptive import AdaptiveSteganography
    from .appender import (
        APPEND_MARKER,
        APPEND_VERSION,
        AppendedPayload,
        append_payload_to_file,
        extract_appended_payload,
        has_appended_payload,
    )
    from .jpeg_dct import JPEGDCTSteganography
    from .lsb import LSBSteganography
    from .pvd import PVDSteganography
    from .audio import AudioSteganography
    from .video import VideoSteganography
    from .png_chunks import (
        CUSTOM_CHUNK_TYPE,
        embed_data_in_chunk,
        extract_data_from_chunk,
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
    if name == "AudioSteganography":
        return import_module(".audio", __name__).AudioSteganography
    if name == "VideoSteganography":
        return import_module(".video", __name__).VideoSteganography
    if name in {
        "APPEND_MARKER",
        "APPEND_VERSION",
        "AppendedPayload",
        "append_payload_to_file",
        "extract_appended_payload",
        "has_appended_payload",
    }:
        module = import_module(".appender", __name__)
        return getattr(module, name)
    if name in {
        "CUSTOM_CHUNK_TYPE",
        "embed_data_in_chunk",
        "extract_data_from_chunk",
    }:
        module = import_module(".png_chunks", __name__)
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
