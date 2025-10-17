"""Utilities for appending structured payloads to the end of cover files."""

from __future__ import annotations

import dataclasses
import struct
import zlib
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "APPEND_MARKER",
    "APPEND_VERSION",
    "AppendedPayload",
    "append_payload_to_file",
    "extract_appended_payload",
    "has_appended_payload",
]


APPEND_MARKER = b"STEGOSIGHT::APPEND::V1"
APPEND_VERSION = 1
_HEADER_STRUCT = struct.Struct(">BQHI")


@dataclasses.dataclass(frozen=True)
class AppendedPayload:
    """Represents a payload recovered from an appended trailer."""

    data: bytes
    filename: Optional[str]
    checksum: int
    version: int
    payload_length: int

    def is_intact(self) -> bool:
        """Return ``True`` when the payload checksum matches the stored value."""

        return zlib.crc32(self.data) & 0xFFFFFFFF == self.checksum


def _ensure_path(path: Union[str, Path]) -> Path:
    if isinstance(path, Path):
        return path
    return Path(path)


def _ensure_bytes(data: Union[bytes, bytearray, memoryview]) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("payload must be bytes-like")
    return bytes(data)


def _encode_filename(name: Optional[str]) -> bytes:
    if not name:
        return b""
    encoded = name.encode("utf-8")
    if len(encoded) > 0xFFFF:
        raise ValueError("ชื่อไฟล์ยาวเกินไป (ต้องไม่เกิน 65535 ไบต์หลังเข้ารหัส UTF-8)")
    return encoded


def _build_trailer(payload: bytes, filename: Optional[str]) -> bytes:
    """Return the binary trailer that is appended after the cover file bytes."""

    payload_bytes = _ensure_bytes(payload)
    filename_bytes = _encode_filename(filename)
    payload_length = len(payload_bytes)
    checksum = zlib.crc32(payload_bytes) & 0xFFFFFFFF
    header = _HEADER_STRUCT.pack(
        APPEND_VERSION, payload_length, len(filename_bytes), checksum
    )
    return APPEND_MARKER + header + filename_bytes + payload_bytes


def append_payload_to_file(
    cover_path: Union[str, Path],
    payload: Union[bytes, bytearray, memoryview],
    *,
    output_path: Optional[Union[str, Path]] = None,
    payload_name: Optional[str] = None,
) -> str:
    """Append *payload* to *cover_path* and return the path to the stego file.

    ``payload_name`` is stored alongside the payload so the original filename can
    be restored during extraction.
    """

    src = _ensure_path(cover_path)
    if output_path is None:
        output_path = src.with_name(src.stem + "_stego" + src.suffix)
    dst = _ensure_path(output_path)

    dst.write_bytes(src.read_bytes() + _build_trailer(payload, payload_name))
    return str(dst)


def _parse_trailer(data: bytes) -> AppendedPayload:
    marker_index = data.rfind(APPEND_MARKER)
    if marker_index == -1:
        raise ValueError("ไม่พบข้อมูลที่ถูกพ่วงต่อท้ายไฟล์")

    header_start = marker_index + len(APPEND_MARKER)
    header_end = header_start + _HEADER_STRUCT.size
    if header_end > len(data):
        raise ValueError("ส่วนหัวของข้อมูลต่อท้ายไม่สมบูรณ์")

    version, payload_length, name_length, checksum = _HEADER_STRUCT.unpack(
        data[header_start:header_end]
    )
    if version != APPEND_VERSION:
        raise ValueError(f"ไม่รองรับรูปแบบข้อมูลต่อท้ายเวอร์ชัน {version}")

    name_start = header_end
    name_end = name_start + name_length
    payload_start = name_end
    payload_end = payload_start + payload_length
    if payload_end > len(data):
        raise ValueError("ขนาดข้อมูลต่อท้ายไม่ถูกต้อง")

    filename_bytes = data[name_start:name_end]
    if filename_bytes:
        try:
            filename = filename_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("ชื่อไฟล์ที่บันทึกไว้ไม่ใช่ UTF-8") from exc
    else:
        filename = None

    payload_bytes = data[payload_start:payload_end]
    result = AppendedPayload(
        data=payload_bytes,
        filename=filename,
        checksum=checksum,
        version=version,
        payload_length=payload_length,
    )

    if not result.is_intact():
        raise ValueError("ข้อมูลที่ถูกพ่วงต่อท้ายมีการเปลี่ยนแปลงหรือเสียหาย (checksum mismatch)")

    return result


def extract_appended_payload(
    stego_path: Union[str, Path],
    *,
    include_metadata: bool = False,
) -> Union[bytes, AppendedPayload]:
    """Return the payload that was appended to *stego_path*.

    When ``include_metadata`` is ``True`` an :class:`AppendedPayload` instance
    containing the recovered metadata is returned. Otherwise only the payload
    bytes are returned.
    """

    path = _ensure_path(stego_path)
    data = path.read_bytes()
    payload = _parse_trailer(data)
    return payload if include_metadata else payload.data


def has_appended_payload(stego_path: Union[str, Path]) -> bool:
    """Return ``True`` if *stego_path* appears to contain an appended payload."""

    try:
        _ = extract_appended_payload(stego_path, include_metadata=True)
    except Exception:
        return False
    return True

