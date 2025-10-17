import base64
import struct
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steganography.png_chunk import (
    PNG_SIGNATURE,
    embed_file_into_png_chunk,
    extract_file_from_png_chunk,
    extract_payload_from_png_chunk,
)


MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
)


def test_embed_and_extract_file(tmp_path: Path) -> None:
    cover = tmp_path / "cover.png"
    cover.write_bytes(MINIMAL_PNG)

    secret = tmp_path / "proposal.txt"
    secret.write_text("top secret proposal", encoding="utf-8")

    stego_path = embed_file_into_png_chunk(cover, secret)
    assert stego_path.exists()

    stego_bytes = stego_path.read_bytes()
    chunk_index = stego_bytes.index(b"stGO")
    iend_index = stego_bytes.rfind(b"IEND") - 4
    assert chunk_index > len(PNG_SIGNATURE)
    assert chunk_index < iend_index

    extracted_path = extract_file_from_png_chunk(stego_path)
    assert extracted_path.read_bytes() == secret.read_bytes()

    filename, payload = extract_payload_from_png_chunk(stego_path)
    assert filename == secret.name
    assert payload == secret.read_bytes()


def test_extract_payload_missing_chunk(tmp_path: Path) -> None:
    cover = tmp_path / "cover.png"
    cover.write_bytes(MINIMAL_PNG)

    with pytest.raises(ValueError):
        extract_payload_from_png_chunk(cover)


def test_crc_mismatch_detection(tmp_path: Path) -> None:
    cover = tmp_path / "cover.png"
    cover.write_bytes(MINIMAL_PNG)
    secret = tmp_path / "plan.txt"
    secret.write_text("stealth", encoding="utf-8")

    stego_path = embed_file_into_png_chunk(cover, secret)
    stego_bytes = bytearray(stego_path.read_bytes())

    chunk_type_index = stego_bytes.index(b"stGO")
    length = struct.unpack(">I", stego_bytes[chunk_type_index - 4 : chunk_type_index])[0]
    payload_start = chunk_type_index + 4
    payload_end = payload_start + length
    stego_bytes[payload_end - 1] ^= 0xFF

    corrupted_path = tmp_path / "corrupted.png"
    corrupted_path.write_bytes(stego_bytes)

    with pytest.raises(ValueError):
        extract_payload_from_png_chunk(corrupted_path)
