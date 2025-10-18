"""Steganography engine interface definitions."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass(slots=True)
class EmbedOptions:
    """Configuration for embedding payload data into carrier media."""

    media_type: Literal["image", "audio", "video"]
    method: Literal["adaptive", "manual", "integrated"]
    techniques: list[str]
    params: dict
    payload_kind: Literal["text", "file"]
    encryption: bool
    kdf: dict
    output_dir: Path


class IStegoEngine(Protocol):
    """Protocol that concrete steganography engines must implement."""

    def estimate_capacity(self, carrier: Path) -> int:
        """Return an estimated capacity in bytes for a carrier file."""

    def embed(self, carrier: Path, payload: bytes, opt: EmbedOptions) -> Path:
        """Embed payload into *carrier* and return the resulting file path."""

    def extract(self, stego_file: Path, password: str | None) -> bytes:
        """Extract the payload from *stego_file*, optionally using *password*."""
