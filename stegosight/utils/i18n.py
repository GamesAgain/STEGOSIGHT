"""Internationalisation stubs."""
from __future__ import annotations

from functools import lru_cache


def set_language(language: str) -> None:
    """Persist the selected *language* for future sessions."""

    # Placeholder implementation until a full translation system is wired up.
    _ = language


@lru_cache(maxsize=None)
def translate(key: str) -> str:
    """Return a translation for *key* or the key itself if missing."""

    return key
