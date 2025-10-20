"""Utilities for embedding data in custom PNG chunks."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union

__all__ = [
    "CUSTOM_CHUNK_TYPE",
    "embed_data_in_chunk",
    "extract_data_from_chunk",
]


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CUSTOM_CHUNK_TYPE = b"stGO"
_CHUNK_HEADER_STRUCT = struct.Struct(">I4s")
_FILENAME_LENGTH_STRUCT = struct.Struct(">H")


class PNGStructureError(ValueError):
    """Raised when the PNG file structure is invalid."""


@dataclass(frozen=True)
class _PNGChunk:
    start_offset: int
    chunk_type: bytes
    data: bytes
    crc: int


def _ensure_path(path: Union[str, Path]) -> Path:
    if isinstance(path, Path):
        return path
    return Path(path)


def _normalize_chunk_type(chunk_type: Union[bytes, bytearray, memoryview]) -> bytes:
    if not isinstance(chunk_type, (bytes, bytearray, memoryview)):
        raise TypeError("chunk_type ต้องเป็น bytes-like")
    chunk_bytes = bytes(chunk_type)
    if len(chunk_bytes) != 4:
        raise ValueError("chunk_type ต้องยาว 4 ไบต์")
    return chunk_bytes


def _iter_png_chunks(png_bytes: bytes) -> Iterator[_PNGChunk]:
    if not png_bytes.startswith(PNG_SIGNATURE):
        raise PNGStructureError("ไฟล์ที่ระบุไม่ใช่ PNG ที่ถูกต้อง")

    offset = len(PNG_SIGNATURE)
    total_length = len(png_bytes)

    while offset + _CHUNK_HEADER_STRUCT.size <= total_length:
        chunk_start = offset
        length, chunk_type = _CHUNK_HEADER_STRUCT.unpack_from(png_bytes, offset)
        offset += _CHUNK_HEADER_STRUCT.size

        data_end = offset + length
        if data_end > total_length:
            raise PNGStructureError("ข้อมูล chunk ของ PNG ไม่สมบูรณ์")

        chunk_data = png_bytes[offset:data_end]
        offset = data_end

        if offset + 4 > total_length:
            raise PNGStructureError("ข้อมูล chunk ของ PNG ไม่สมบูรณ์")

        (stored_crc,) = struct.unpack_from(">I", png_bytes, offset)
        offset += 4

        yield _PNGChunk(chunk_start, chunk_type, chunk_data, stored_crc)


def _build_custom_payload(filename: str, file_data: bytes) -> bytes:
    filename_bytes = filename.encode("utf-8")
    if len(filename_bytes) > 0xFFFF:
        raise ValueError("ชื่อไฟล์ยาวเกินไปสำหรับการฝังใน chunk")

    return _FILENAME_LENGTH_STRUCT.pack(len(filename_bytes)) + filename_bytes + file_data


def _compose_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    chunk_length = len(payload)
    chunk_crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return (
        struct.pack(">I", chunk_length)
        + chunk_type
        + payload
        + struct.pack(">I", chunk_crc)
    )


def embed_data_in_chunk(
    png_filepath: Union[str, Path],
    file_to_hide_path: Union[str, Path],
    output_filepath: Optional[Union[str, Path]] = None,
    *,
    chunk_type: bytes = CUSTOM_CHUNK_TYPE,
) -> str:
    """Embed *file_to_hide_path* inside a custom chunk of *png_filepath*."""

    png_path = _ensure_path(png_filepath)
    hide_path = _ensure_path(file_to_hide_path)

    chunk_type = _normalize_chunk_type(chunk_type)

    png_bytes = png_path.read_bytes()
    hide_bytes = hide_path.read_bytes()

    iend_start: Optional[int] = None
    for chunk in _iter_png_chunks(png_bytes):
        if chunk.chunk_type == chunk_type:
            raise ValueError("ไฟล์ PNG มีข้อมูล stGO อยู่แล้ว")
        if chunk.chunk_type == b"IEND":
            iend_start = chunk.start_offset
            break

    if iend_start is None:
        raise PNGStructureError("ไม่พบ IEND chunk ในไฟล์ PNG")

    filename = hide_path.name
    payload = _build_custom_payload(filename, hide_bytes)
    custom_chunk = _compose_chunk(chunk_type, payload)

    stego_bytes = png_bytes[:iend_start] + custom_chunk + png_bytes[iend_start:]

    if output_filepath is None:
        output_filepath = png_path.with_name(png_path.stem + "_stego" + png_path.suffix)

    output_path = _ensure_path(output_filepath)
    output_path.write_bytes(stego_bytes)
    return str(output_path)


def extract_data_from_chunk(
    stego_png_filepath: Union[str, Path],
    *,
    output_dir: Optional[Union[str, Path]] = None,
    prefix: str = "extracted_",
    overwrite: bool = False,
    chunk_type: bytes = CUSTOM_CHUNK_TYPE,
) -> str:
    """Extract the hidden file stored in the custom chunk."""

    stego_path = _ensure_path(stego_png_filepath)
    if not isinstance(prefix, str):
        raise TypeError("prefix ต้องเป็นสตริง")

    chunk_type = _normalize_chunk_type(chunk_type)

    png_bytes = stego_path.read_bytes()

    for chunk in _iter_png_chunks(png_bytes):
        if chunk.chunk_type != chunk_type:
            continue

        calculated_crc = zlib.crc32(chunk.chunk_type + chunk.data) & 0xFFFFFFFF
        if calculated_crc != chunk.crc:
            raise ValueError("ข้อผิดพลาด: ข้อมูลอาจเสียหาย (CRC checksum ไม่ตรงกัน)")

        if len(chunk.data) < _FILENAME_LENGTH_STRUCT.size:
            raise ValueError("โครงสร้าง payload ของ chunk ไม่ถูกต้อง")

        (filename_length,) = _FILENAME_LENGTH_STRUCT.unpack_from(chunk.data, 0)
        header_end = _FILENAME_LENGTH_STRUCT.size + filename_length
        if header_end > len(chunk.data):
            raise ValueError("โครงสร้าง payload ของ chunk ไม่ถูกต้อง")

        filename_bytes = chunk.data[_FILENAME_LENGTH_STRUCT.size:header_end]
        try:
            filename = filename_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("ไม่สามารถถอดรหัสชื่อไฟล์จาก payload ได้") from exc

        if not filename:
            raise ValueError("payload ไม่ได้ระบุชื่อไฟล์")

        file_data = chunk.data[header_end:]
        destination_dir = _ensure_path(output_dir) if output_dir is not None else stego_path.parent
        destination_dir.mkdir(parents=True, exist_ok=True)

        output_path = destination_dir / f"{prefix}{filename}"
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"ไฟล์ {output_path} มีอยู่แล้ว")

        output_path.write_bytes(file_data)
        return str(output_path)

    raise ValueError("ไม่พบข้อมูลที่ซ่อนไว้ (ไม่พบ stGO chunk)")

