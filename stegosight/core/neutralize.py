"""Neutralization engine interface."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol


class INeutralizer(Protocol):
    """Protocol describing neutralization pipelines."""

    def neutralize(self, file: Path, tier: Literal["light", "standard", "aggressive"]) -> Path:
        """Return a sanitized version of *file* given the selected *tier*."""
