"""Validation helpers for STEGOSIGHT inputs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SUPPORTED_IMAGE_TYPES = {"png", "jpeg", "jpg", "bmp"}
SUPPORTED_AUDIO_TYPES = {"wav", "mp3", "flac", "wma", "aac"}
SUPPORTED_VIDEO_TYPES = {"avi", "mp4", "mkv", "mov", "ogg"}


@dataclass(slots=True)
class ValidationResult:
    """Result of validating user input."""

    valid: bool
    message: str = ""


class ValidationError(ValueError):
    """Raised when validation fails."""


def _normalize_extension(file_path: Path) -> str:
    return file_path.suffix.lower().lstrip(".")


def validate_carrier_path(file_path: Path) -> ValidationResult:
    """Validate that *file_path* corresponds to a supported carrier."""

    ext = _normalize_extension(file_path)
    for category in (SUPPORTED_IMAGE_TYPES, SUPPORTED_AUDIO_TYPES, SUPPORTED_VIDEO_TYPES):
        if ext in category:
            return ValidationResult(True)
    return ValidationResult(False, f"Unsupported carrier format: {ext or 'unknown'}")


def estimate_capacity(file_path: Path) -> int:
    """Provide a deterministic mock capacity estimation based on file size."""

    if not file_path.exists():
        raise ValidationError(f"Carrier file does not exist: {file_path}")
    size = file_path.stat().st_size
    if size <= 0:
        raise ValidationError("Carrier file is empty")
    base_capacity = int(size * 0.25)
    return max(base_capacity, 1024)


def ensure_methods_allowed(media_type: str, techniques: Iterable[str]) -> ValidationResult:
    """Ensure that selected techniques are compatible with the media type."""

    media_type = media_type.lower()
    unsupported: set[str] = set()
    if media_type == "image":
        unsupported = {"audio_wave_injection"}
    elif media_type == "audio":
        unsupported = {"metadata_exif"}
    elif media_type == "video":
        unsupported = {"image_palette_swap"}
    invalid = sorted(set(techniques) & unsupported)
    if invalid:
        return ValidationResult(False, f"Techniques not supported for {media_type}: {', '.join(invalid)}")
    return ValidationResult(True)
