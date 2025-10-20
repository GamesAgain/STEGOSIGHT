"""High-level helpers for the steganography module."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .appender import (
    AppendedPayload,
    append_payload_to_file,
    extract_appended_payload,
    has_appended_payload,
)

__all__ = [
    "embed_with_file_appending",
    "recover_appended_payload",
    "has_appended_payload",
]


def embed_with_file_appending(
    cover_path: Union[str, Path],
    payload: Union[bytes, bytearray, memoryview],
    *,
    payload_name: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Embed ``payload`` at the end of ``cover_path`` using the append method."""

    return append_payload_to_file(
        cover_path,
        payload,
        payload_name=payload_name,
        output_path=output_path,
    )


def recover_appended_payload(
    stego_path: Union[str, Path],
    *,
    include_metadata: bool = True,
) -> Union[bytes, AppendedPayload]:
    """Recover a payload embedded via the append method."""

    return extract_appended_payload(stego_path, include_metadata=include_metadata)
