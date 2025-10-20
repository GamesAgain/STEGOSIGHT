from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steganography_module.appender import (
    APPEND_MARKER,
    AppendedPayload,
    append_payload_to_file,
    extract_appended_payload,
    has_appended_payload,
)
from utils.payloads import create_file_payload, create_text_payload, is_payload_blob


def test_append_and_extract_payload(tmp_path: Path) -> None:
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"PNGDATA")

    payload = create_text_payload("secret message")
    output_path = tmp_path / "stego.png"

    result_path = append_payload_to_file(
        cover, payload, output_path=output_path, payload_name="message.txt"
    )
    assert Path(result_path) == output_path

    stego_bytes = output_path.read_bytes()
    assert APPEND_MARKER in stego_bytes

    extracted = extract_appended_payload(output_path, include_metadata=True)
    assert isinstance(extracted, AppendedPayload)
    assert extracted.data == payload
    assert extracted.filename == "message.txt"
    assert extracted.payload_length == len(payload)
    assert extracted.is_intact() is True

    # The default behaviour still returns raw bytes for backwards compatibility.
    raw = extract_appended_payload(output_path)
    assert raw == payload
    assert is_payload_blob(raw)


def test_has_appended_payload(tmp_path: Path) -> None:
    cover = tmp_path / "cover.bmp"
    cover.write_bytes(b"BMHEADER")

    payload = create_file_payload(b"DATA123", name="payload.bin")
    result = append_payload_to_file(cover, payload, payload_name="payload.bin")

    assert has_appended_payload(result) is True

    # File without marker should return False
    clean = tmp_path / "clean.png"
    clean.write_bytes(b"CLEANFILE")
    assert has_appended_payload(clean) is False


def test_extract_appended_payload_errors(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.bin"
    # Missing header/payload should trigger an error.
    file_path.write_bytes(APPEND_MARKER)

    with pytest.raises(ValueError):
        extract_appended_payload(file_path)

    # Create a valid file then corrupt the payload to trigger checksum failure.
    cover = tmp_path / "cover.dat"
    cover.write_bytes(b"COVER")
    payload = create_text_payload("tamper test")
    stego_path = Path(append_payload_to_file(cover, payload))
    data = bytearray(stego_path.read_bytes())
    data[-1] ^= 0xFF
    stego_path.write_bytes(bytes(data))

    with pytest.raises(ValueError):
        extract_appended_payload(stego_path)
