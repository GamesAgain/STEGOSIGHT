"""Shared dataclasses and enums used across STEGOSIGHT."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol


@dataclass(slots=True)
class OperationResult:
    """Represents the outcome of an operation executed by the application."""

    operation: Literal["embed", "extract", "analyze", "neutralize"]
    target: Path
    success: bool
    message: str
    duration_s: float
    risk_score: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class SupportsCancellation(Protocol):
    """Protocol for long-running operations that support cancellation."""

    def cancel(self) -> None:
        """Request cancellation of the operation."""
