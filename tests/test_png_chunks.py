from pathlib import Path
import struct
import sys
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steganography_module.png_chunks import embed_data_in_chunk, extract_data_from_chunk


def _minimal_png_bytes() -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = (
        struct.pack(">I", len(ihdr_data))
        + b"IHDR"
        + ihdr_data
        + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    )

    pixel_data = b"\x00\xff\x00\x00"  # filter byte + RGB pixel
    idat_data = zlib.compress(pixel_data)
    idat = (
        struct.pack(">I", len(idat_data))
        + b"IDAT"
        + idat_data
        + struct.pack(">I", zlib.crc32(b"IDAT" + idat_data) & 0xFFFFFFFF)
    )

    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    return signature + ihdr + idat + iend


def _write_minimal_png(path: Path) -> Path:
    path.write_bytes(_minimal_png_bytes())
    return path


def test_embed_and_extract_roundtrip(tmp_path: Path) -> None:
    cover_png = _write_minimal_png(tmp_path / "cover.png")
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("classified data", encoding="utf-8")

    stego_path = embed_data_in_chunk(cover_png, secret_file, tmp_path / "stego.png")
    output_path = extract_data_from_chunk(stego_path, output_dir=tmp_path)

    extracted = Path(output_path)
    assert extracted.read_text(encoding="utf-8") == "classified data"


def test_extract_without_chunk_raises(tmp_path: Path) -> None:
    cover_png = _write_minimal_png(tmp_path / "cover.png")

    with pytest.raises(ValueError, match="ไม่พบข้อมูลที่ซ่อนไว้"):
        extract_data_from_chunk(cover_png)


def test_embed_rejects_existing_chunk(tmp_path: Path) -> None:
    cover_png = _write_minimal_png(tmp_path / "cover.png")
    secret_file = tmp_path / "secret.bin"
    secret_file.write_bytes(b"payload")

    stego_path = embed_data_in_chunk(cover_png, secret_file, tmp_path / "stego.png")

    with pytest.raises(ValueError, match="มีข้อมูล stGO อยู่แล้ว"):
        embed_data_in_chunk(stego_path, secret_file, tmp_path / "stego2.png")


def test_extract_detects_crc_mismatch(tmp_path: Path) -> None:
    cover_png = _write_minimal_png(tmp_path / "cover.png")
    secret_file = tmp_path / "secret.bin"
    secret_file.write_bytes(b"payload")

    stego_path = Path(embed_data_in_chunk(cover_png, secret_file, tmp_path / "stego.png"))
    stego_bytes = bytearray(stego_path.read_bytes())

    chunk_index = stego_bytes.index(b"stGO") + 4
    stego_bytes[chunk_index] ^= 0xFF
    (tmp_path / "tampered.png").write_bytes(stego_bytes)

    with pytest.raises(ValueError, match="CRC checksum ไม่ตรงกัน"):
        extract_data_from_chunk(tmp_path / "tampered.png")

