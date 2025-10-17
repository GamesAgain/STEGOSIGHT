"""PNG custom chunk steganography utilities."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Iterable, Iterator, Optional, Tuple, Union

__all__ = [
    "PNG_SIGNATURE",
    "PNGChunkInfo",
    "embed_file_into_png_chunk",
    "extract_file_from_png_chunk",
    "extract_payload_from_png_chunk",
]

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHUNK_HEADER = struct.Struct(">I4s")
_CRC_STRUCT = struct.Struct(">I")
_DEFAULT_CHUNK_TYPE = b"stGO"

PNGChunkInfo = Tuple[bytes, int, int, int, int, int]
"""Tuple describing a PNG chunk.

The fields are ``(chunk_type, chunk_start, length, data_start, data_end, crc)``.
All offsets are relative to the beginning of the file bytes.
"""


def _ensure_path(path: Union[str, Path]) -> Path:
    if isinstance(path, Path):
        return path
    return Path(path)


def _read_bytes(path: Union[str, Path]) -> bytes:
    return _ensure_path(path).read_bytes()


def _write_bytes(path: Union[str, Path], data: bytes) -> None:
    _ensure_path(path).write_bytes(data)


def _validate_chunk_type(chunk_type: bytes) -> bytes:
    if not isinstance(chunk_type, (bytes, bytearray, memoryview)):
        raise TypeError("chunk_type must be a bytes-like object")
    chunk_bytes = bytes(chunk_type)
    if len(chunk_bytes) != 4:
        raise ValueError("chunk_type must be exactly 4 ASCII bytes")
    if not all(65 <= c <= 90 or 97 <= c <= 122 for c in chunk_bytes):
        raise ValueError("chunk_type must contain alphabetic ASCII characters only")
    if not (97 <= chunk_bytes[0] <= 122):
        raise ValueError("chunk_type must be ancillary (first letter must be lowercase)")
    return chunk_bytes


def _iter_chunks(data: bytes) -> Iterator[PNGChunkInfo]:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("ไฟล์ไม่ใช่ PNG ที่ถูกต้อง")

    offset = len(PNG_SIGNATURE)
    data_len = len(data)
    while offset + 8 <= data_len:
        chunk_start = offset
        length, chunk_type = _CHUNK_HEADER.unpack_from(data, offset)
        offset += _CHUNK_HEADER.size
        data_start = offset
        data_end = data_start + length
        if data_end > data_len:
            raise ValueError("ข้อมูล PNG ไม่สมบูรณ์ (chunk ยาวเกินไฟล์)")
        offset = data_end
        if offset + 4 > data_len:
            raise ValueError("ข้อมูล PNG ไม่สมบูรณ์ (ไม่มีค่า CRC)")
        (crc,) = _CRC_STRUCT.unpack_from(data, offset)
        offset += _CRC_STRUCT.size
        yield (chunk_type, chunk_start, length, data_start, data_end, crc)
        if chunk_type == b"IEND":
            return
    raise ValueError("ไม่พบ chunk IEND ในไฟล์ PNG")


def _find_chunk(data: bytes, target_types: Iterable[bytes]) -> Optional[PNGChunkInfo]:
    targets = {bytes(t) for t in target_types}
    for info in _iter_chunks(data):
        if info[0] in targets:
            return info
    return None


def _build_payload(filename: str, payload: bytes) -> bytes:
    filename_bytes = filename.encode("utf-8")
    if len(filename_bytes) > 0xFFFF:
        raise ValueError("ชื่อไฟล์ยาวเกินกว่าจะบันทึกใน chunk ได้")
    return struct.pack(">H", len(filename_bytes)) + filename_bytes + payload


def _build_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    chunk_data = chunk_type + payload
    crc = zlib.crc32(chunk_data) & 0xFFFFFFFF
    return _CHUNK_HEADER.pack(len(payload), chunk_type) + payload + _CRC_STRUCT.pack(crc)


def embed_file_into_png_chunk(
    png_path: Union[str, Path],
    file_to_hide: Union[str, Path],
    *,
    output_path: Optional[Union[str, Path]] = None,
    chunk_type: bytes = _DEFAULT_CHUNK_TYPE,
) -> Path:
    """Embed ``file_to_hide`` inside ``png_path`` using a custom ancillary chunk."""

    chunk_type_bytes = _validate_chunk_type(chunk_type)
    png_bytes = _read_bytes(png_path)
    iend_info = _find_chunk(png_bytes, [b"IEND"])
    if iend_info is None:
        raise ValueError("ไม่พบ chunk IEND ในไฟล์ PNG")

    secret_path = _ensure_path(file_to_hide)
    payload = _build_payload(secret_path.name, secret_path.read_bytes())
    custom_chunk = _build_chunk(chunk_type_bytes, payload)

    chunk_insert_offset = iend_info[1]
    new_png_bytes = png_bytes[:chunk_insert_offset] + custom_chunk + png_bytes[chunk_insert_offset:]

    if output_path is None:
        png_file = _ensure_path(png_path)
        output_path = png_file.with_name(png_file.stem + "_stego" + png_file.suffix)
    output_path = _ensure_path(output_path)
    _write_bytes(output_path, new_png_bytes)
    return output_path


def extract_payload_from_png_chunk(
    stego_png_path: Union[str, Path],
    *,
    chunk_type: bytes = _DEFAULT_CHUNK_TYPE,
) -> Tuple[str, bytes]:
    """Return the filename and payload bytes stored in the custom chunk."""

    chunk_type_bytes = _validate_chunk_type(chunk_type)
    png_bytes = _read_bytes(stego_png_path)
    chunk_info = _find_chunk(png_bytes, [chunk_type_bytes])
    if chunk_info is None:
        raise ValueError("ไม่พบ chunk ซ่อนข้อมูลในไฟล์ PNG")

    chunk_type_found, chunk_start, length, data_start, data_end, stored_crc = chunk_info
    calculated_crc = zlib.crc32(chunk_type_found + png_bytes[data_start:data_end]) & 0xFFFFFFFF
    if calculated_crc != stored_crc:
        raise ValueError("ข้อมูลใน chunk เสียหาย (CRC ไม่ตรงกัน)")

    payload = png_bytes[data_start:data_end]
    if len(payload) < 2:
        raise ValueError("payload ใน chunk ไม่ถูกต้อง")

    filename_len = struct.unpack(">H", payload[:2])[0]
    if 2 + filename_len > len(payload):
        raise ValueError("payload ใน chunk ไม่สมบูรณ์")

    filename = payload[2 : 2 + filename_len].decode("utf-8")
    data = payload[2 + filename_len :]
    return filename, data


def extract_file_from_png_chunk(
    stego_png_path: Union[str, Path],
    *,
    output_dir: Optional[Union[str, Path]] = None,
    chunk_type: bytes = _DEFAULT_CHUNK_TYPE,
    prefix: str = "extracted_",
) -> Path:
    """Extract the hidden file from ``stego_png_path`` and return the new file path."""

    filename, data = extract_payload_from_png_chunk(stego_png_path, chunk_type=chunk_type)
    output_directory = _ensure_path(output_dir) if output_dir is not None else _ensure_path(stego_png_path).parent
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{prefix}{filename}"
    _write_bytes(output_path, data)
    return output_path
