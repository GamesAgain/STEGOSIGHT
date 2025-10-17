from __future__ import annotations

import math
import wave
from pathlib import Path

import pytest

from steganography.audio import AudioSteganography


def _generate_wav(path: Path, *, duration: float = 0.2) -> None:
    sample_rate = 44100
    total_samples = int(sample_rate * duration)
    amplitude = 16000

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.setcomptype("NONE", "not compressed")

        frames = bytearray()
        for index in range(total_samples):
            value = int(amplitude * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames += int(value).to_bytes(2, byteorder="little", signed=True)

        wav.writeframes(bytes(frames))


def test_audio_embed_and_extract_roundtrip(tmp_path: Path) -> None:
    cover = tmp_path / "cover.wav"
    _generate_wav(cover)

    payload = b"STEGOSIGHT audio payload"
    audio = AudioSteganography()
    stego_path = Path(audio.embed(cover, payload))

    extracted = audio.extract(stego_path)
    assert extracted == payload


def test_audio_capacity_limit(tmp_path: Path) -> None:
    cover = tmp_path / "cover.wav"
    _generate_wav(cover, duration=0.05)

    audio = AudioSteganography()
    capacity = audio.calculate_capacity(cover)

    with pytest.raises(ValueError):
        audio.embed(cover, b"X" * (capacity + 10))
