"""Validation helpers shared between the CLI and GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

IMAGE_EXTENSIONS = {".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg"}
AUDIO_EXTENSIONS = {".wav", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


class ValidationError(ValueError):
    """Raised when validation cannot be completed."""


@dataclass(frozen=True)
class ValidationResult:
    """Simple structure describing a validation outcome."""

    valid: bool
    message: str = ""


def _ensure_path(path: Path | str) -> Path:
    if isinstance(path, Path):
        return path
    return Path(path)


def _normalize_extension(path: Path) -> str:
    return path.suffix.lower()


def validate_carrier_path(path: Path | str) -> ValidationResult:
    """Check whether *path* refers to a supported carrier file."""

    candidate = _ensure_path(path)
    if not candidate.exists():
        return ValidationResult(False, "File not found")

    suffix = _normalize_extension(candidate)
    if suffix not in SUPPORTED_EXTENSIONS:
        return ValidationResult(False, f"Unsupported file type: {suffix or 'unknown'}")

    return ValidationResult(True, "OK")


def estimate_capacity(path: Path | str) -> int:
    """Return a conservative payload capacity estimate for *path* in bytes."""

    candidate = _ensure_path(path)
    if not candidate.exists():
        raise ValidationError(f"Carrier file does not exist: {candidate}")

    suffix = _normalize_extension(candidate)
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValidationError(f"Unsupported carrier type: {suffix or 'unknown'}")

    file_size = candidate.stat().st_size

    if suffix in IMAGE_EXTENSIONS:
        multiplier = 4
    elif suffix in AUDIO_EXTENSIONS:
        multiplier = 2
    else:
        multiplier = 3

    capacity = max(1024, int(file_size * multiplier))
    return capacity


def supported_extensions() -> Iterable[str]:
    """Return the collection of supported carrier file extensions."""

    return sorted(SUPPORTED_EXTENSIONS)


__all__ = [
    "ValidationError",
    "ValidationResult",
    "estimate_capacity",
    "supported_extensions",
    "validate_carrier_path",
]
