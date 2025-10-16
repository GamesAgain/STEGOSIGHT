"""Unit tests for extraction helper heuristics."""

import pytest

gui = pytest.importorskip("gui")
WorkerThread = gui.WorkerThread


def test_should_hint_encryption_detects_non_payload_bytes():
    assert WorkerThread._should_hint_encryption(b"\x00" * 32, False, False)


def test_should_hint_encryption_ignores_payload_or_expected_encryption():
    assert not WorkerThread._should_hint_encryption(b"data", True, False)
    assert not WorkerThread._should_hint_encryption(b"data", False, True)
    assert not WorkerThread._should_hint_encryption(b"", False, False)
