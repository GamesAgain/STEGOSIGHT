from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steganography.appender import (
    APPEND_MARKER,
    append_payload_to_file,
    extract_appended_payload,
    has_appended_payload,
)
from utils.payloads import create_text_payload, is_payload_blob


def test_append_and_extract_payload(tmp_path: Path) -> None:
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"PNGDATA")

    payload = create_text_payload("secret message")
    output_path = tmp_path / "stego.png"

    result_path = append_payload_to_file(cover, payload, output_path=output_path)
    assert Path(result_path) == output_path

    stego_bytes = output_path.read_bytes()
    assert APPEND_MARKER in stego_bytes

    extracted = extract_appended_payload(output_path)
    assert extracted == payload
    assert is_payload_blob(extracted)


def test_has_appended_payload(tmp_path: Path) -> None:
    cover = tmp_path / "cover.bmp"
    cover.write_bytes(b"BMHEADER")

    payload = create_text_payload("another secret")
    result = append_payload_to_file(cover, payload)

    assert has_appended_payload(result) is True

    # File without marker should return False
    clean = tmp_path / "clean.png"
    clean.write_bytes(b"CLEANFILE")
    assert has_appended_payload(clean) is False


def test_extract_appended_payload_errors(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.bin"
    file_path.write_bytes(APPEND_MARKER + b"\x00\x00\x00\x05abc")

    with pytest.raises(ValueError):
        extract_appended_payload(file_path)
