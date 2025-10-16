"""Utilities for packaging secret payloads with metadata for extraction."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = [
    "create_text_payload",
    "create_file_payload",
    "unpack_payload",
]

_MAGIC = b"STEGOSIGHT"
_VERSION = 1
_HEADER_LEN = len(_MAGIC) + 1 + 4  # magic + version + metadata length


def _pack_payload(metadata: Dict[str, Any], data: bytes) -> bytes:
    """Pack metadata and payload bytes into a binary blob."""
    meta = dict(metadata)
    meta.setdefault("size", len(data))
    meta.setdefault("schema", "stegosight")
    meta.setdefault("version", _VERSION)
    meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    header = _MAGIC + bytes([_VERSION]) + struct.pack(">I", len(meta_bytes))
    return header + meta_bytes + data


def create_text_payload(text: str, *, encrypted: bool = False, encoding: str = "utf-8") -> bytes:
    """Create a payload blob representing a text secret."""
    data = text.encode(encoding)
    metadata = {
        "type": "text",
        "encoding": encoding,
        "encrypted": encrypted,
    }
    return _pack_payload(metadata, data)


def create_file_payload(
    data: bytes,
    *,
    name: str,
    encrypted: bool = False,
) -> bytes:
    """Create a payload blob representing a file secret."""
    suffix = Path(name).suffix
    metadata = {
        "type": "file",
        "name": name,
        "extension": suffix.lstrip("."),
        "encrypted": encrypted,
    }
    return _pack_payload(metadata, data)


def unpack_payload(blob: bytes) -> Dict[str, Any]:
    """Extract metadata and payload bytes from the packed blob.

    Returns a dictionary with keys:
        - ``kind``: ``"text"`` or ``"file"`` (``"binary"`` as fallback)
        - ``metadata``: decoded metadata dictionary
        - ``data``: raw payload bytes
        - ``text``: decoded text (only for text payloads)
    """
    if len(blob) >= _HEADER_LEN and blob.startswith(_MAGIC):
        version = blob[len(_MAGIC)]
        if version != _VERSION:
            raise ValueError(f"Unsupported payload version: {version}")
        start = len(_MAGIC) + 1
        meta_len = struct.unpack(">I", blob[start : start + 4])[0]
        meta_start = start + 4
        meta_end = meta_start + meta_len
        if meta_end > len(blob):
            raise ValueError("Payload metadata is incomplete")
        meta_bytes = blob[meta_start:meta_end]
        metadata = json.loads(meta_bytes.decode("utf-8"))
        data = blob[meta_end:]
        metadata.setdefault("size", len(data))
        kind = metadata.get("type", "binary")
        text: Optional[str] = None
        if kind == "text":
            encoding = metadata.get("encoding", "utf-8")
            try:
                text = data.decode(encoding)
            except Exception:
                text = data.decode("utf-8", errors="replace")
        return {"kind": kind, "metadata": metadata, "data": data, "text": text}

    # Fallback for legacy payloads without structured metadata
    try:
        text = blob.decode("utf-8")
        metadata = {
            "type": "text",
            "encoding": "utf-8",
            "size": len(blob),
            "encrypted": False,
        }
        return {"kind": "text", "metadata": metadata, "data": blob, "text": text}
    except UnicodeDecodeError:
        metadata = {
            "type": "binary",
            "size": len(blob),
            "encrypted": False,
        }
        return {"kind": "binary", "metadata": metadata, "data": blob, "text": None}
