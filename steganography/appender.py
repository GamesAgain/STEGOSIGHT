"""Utilities for appending structured payloads to the end of cover files."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "APPEND_MARKER",
    "append_payload_to_file",
    "extract_appended_payload",
    "has_appended_payload",
]


APPEND_MARKER = b"STEGOSIGHT::APPENDED::PAYLOAD"
_HEADER_STRUCT = struct.Struct(">I")  # stores payload length in bytes (big-endian)


def _ensure_path(path: Union[str, Path]) -> Path:
    if isinstance(path, Path):
        return path
    return Path(path)


def _build_trailer(payload: bytes) -> bytes:
    """Return the binary trailer that is appended after the cover file bytes."""

    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("payload must be bytes-like")
    payload_bytes = bytes(payload)
    return APPEND_MARKER + _HEADER_STRUCT.pack(len(payload_bytes)) + payload_bytes


def append_payload_to_file(
    cover_path: Union[str, Path],
    payload: bytes,
    *,
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Append *payload* to *cover_path* and return the path to the new file.

    The payload is stored with a deterministic marker and a 4-byte length header
    so it can be located and extracted reliably later.
    """

    src = _ensure_path(cover_path)
    if output_path is None:
        output_path = src.with_name(src.stem + "_stego" + src.suffix)
    dst = _ensure_path(output_path)

    dst.write_bytes(src.read_bytes() + _build_trailer(payload))
    return str(dst)


def extract_appended_payload(stego_path: Union[str, Path]) -> bytes:
    """Return the payload that was appended to *stego_path*.

    Raises ``ValueError`` if the marker cannot be located or the recorded size
    is inconsistent with the file contents.
    """

    path = _ensure_path(stego_path)
    data = path.read_bytes()
    marker_index = data.rfind(APPEND_MARKER)
    if marker_index == -1:
        raise ValueError("ไม่พบข้อมูลที่ถูกพ่วงต่อท้ายไฟล์")

    header_start = marker_index + len(APPEND_MARKER)
    header_end = header_start + _HEADER_STRUCT.size
    if header_end > len(data):
        raise ValueError("ส่วนหัวของข้อมูลต่อท้ายไม่สมบูรณ์")

    (payload_length,) = _HEADER_STRUCT.unpack(data[header_start:header_end])
    payload_start = header_end
    payload_end = payload_start + payload_length
    if payload_end > len(data):
        raise ValueError("ขนาดข้อมูลต่อท้ายไม่ถูกต้อง")

    return data[payload_start:payload_end]


def has_appended_payload(stego_path: Union[str, Path]) -> bool:
    """Return ``True`` if *stego_path* appears to contain an appended payload."""

    try:
        _ = extract_appended_payload(stego_path)
    except Exception:
        return False
    return True

