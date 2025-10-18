"""Analysis engine interfaces used by the GUI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class AnalysisResult:
    """Represents the result of an analysis scan."""

    risk_score: int
    flags: dict[str, float]
    metadata: dict


class IAnalyzer(Protocol):
    """Protocol for analyzer implementations."""

    def scan(self, file: Path, techniques: list[str] | None = None) -> AnalysisResult:
        """Perform an analysis scan on *file*."""
