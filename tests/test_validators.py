"""Tests for validator helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from stegosight.utils.validators import ValidationError, estimate_capacity, validate_carrier_path


def test_validate_carrier_path_accepts_supported(tmp_path: Path) -> None:
    supported = tmp_path / "sample.png"
    supported.write_bytes(b"data")
    result = validate_carrier_path(supported)
    assert result.valid


def test_validate_carrier_path_rejects_unknown(tmp_path: Path) -> None:
    unknown = tmp_path / "unsupported.xyz"
    unknown.write_bytes(b"data")
    result = validate_carrier_path(unknown)
    assert not result.valid
    assert "Unsupported" in result.message


def test_estimate_capacity_requires_existing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"
    with pytest.raises(ValidationError):
        estimate_capacity(missing)


def test_estimate_capacity_returns_minimum(tmp_path: Path) -> None:
    tiny = tmp_path / "tiny.png"
    tiny.write_bytes(b"abc")
    capacity = estimate_capacity(tiny)
    assert capacity == 1024


def test_estimate_capacity_scales_with_file(tmp_path: Path) -> None:
    large = tmp_path / "large.png"
    large.write_bytes(b"a" * 10_000)
    capacity = estimate_capacity(large)
    assert capacity > 1024
