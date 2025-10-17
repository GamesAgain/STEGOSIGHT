from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from steganography.video import VideoSteganography


def _generate_video(path: Path, *, frames: int = 8) -> None:
    width, height = 32, 32
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(path), fourcc, 10.0, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Failed to create synthetic video for tests")

    for index in range(frames):
        value = (index * 30) % 255
        frame = np.full((height, width, 3), value, dtype=np.uint8)
        writer.write(frame)

    writer.release()


def test_video_embed_and_extract_roundtrip(tmp_path: Path) -> None:
    cover = tmp_path / "cover.avi"
    _generate_video(cover)

    payload = b"Video payload"
    video = VideoSteganography()
    stego_path = Path(video.embed(cover, payload))

    extracted = video.extract(stego_path)
    assert extracted == payload


def test_video_capacity(tmp_path: Path) -> None:
    cover = tmp_path / "cover.avi"
    _generate_video(cover, frames=2)

    video = VideoSteganography()
    capacity = video.calculate_capacity(cover)

    result = video.embed(cover, b"X" * min(8, capacity))
    assert Path(result).exists()
