"""Audio steganography utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np

from utils.logger import log_operation, setup_logger

logger = setup_logger(__name__)


class AudioSteganography:
    """Embed and extract data from uncompressed PCM WAV files using LSB."""

    def __init__(self) -> None:
        logger.debug("AudioSteganography initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @log_operation("Audio Embed")
    def embed(
        self,
        cover_path: str | Path,
        secret_data: bytes,
        output_path: str | Path | None = None,
    ) -> str:
        """Embed ``secret_data`` into ``cover_path`` using 1-bit LSB."""

        cover_path = Path(cover_path)
        params, samples = _read_pcm_samples(cover_path)

        payload = len(secret_data).to_bytes(4, byteorder="big") + secret_data
        bit_stream = _bytes_to_bits(payload)

        capacity_bits = len(samples)
        if len(bit_stream) > capacity_bits:
            available_bytes = max((capacity_bits // 8) - 4, 0)
            raise ValueError(
                "Secret data too large for cover audio (available "
                f"{available_bytes} bytes, need {len(secret_data)})."
            )

        logger.debug("Embedding %d bits into audio", len(bit_stream))

        samples = samples.copy()
        for index, bit in enumerate(bit_stream):
            value = int(samples[index])
            samples[index] = (value & ~1) | int(bit)

        stego_bytes = _samples_to_bytes(samples)

        if output_path is None:
            output_path = cover_path.with_name(f"{cover_path.stem}_stego{cover_path.suffix}")

        _write_pcm_samples(Path(output_path), params, stego_bytes)
        logger.info("Audio embedding complete: %s", output_path)
        return str(output_path)

    @log_operation("Audio Extract")
    def extract(self, stego_path: str | Path) -> bytes:
        """Extract the hidden payload from ``stego_path``."""

        stego_path = Path(stego_path)
        _params, samples = _read_pcm_samples(stego_path)

        bits = ""
        start_index = 0
        for idx, value in enumerate(samples):
            bits += str(int(value) & 1)
            if len(bits) >= 32:
                start_index = idx + 1
                break

        if len(bits) < 32:
            raise ValueError("Audio file does not contain a valid payload")

        data_length = int(bits[:32], 2)
        target_bits = 32 + data_length * 8

        for value in samples[start_index:]:
            if len(bits) >= target_bits:
                break
            bits += str(int(value) & 1)

        if len(bits) < target_bits:
            raise ValueError("Audio payload truncated or corrupted")

        payload = _bits_to_bytes(bits[:target_bits])
        return payload[4:]

    def calculate_capacity(self, cover_path: str | Path) -> int:
        """Return the maximum payload capacity in bytes."""

        _, samples = _read_pcm_samples(Path(cover_path))
        capacity_bytes = (len(samples) // 8) - 4
        return max(0, capacity_bytes)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------
def _read_pcm_samples(path: Path) -> Tuple[Tuple[int, int, int, int, int, int], np.ndarray]:
    import wave

    with wave.open(str(path), "rb") as wav:
        params = wav.getparams()
        nchannels, sampwidth, framerate, nframes, comptype, compname = params
        if comptype != "NONE":
            raise ValueError("Only uncompressed PCM WAV files are supported")
        if sampwidth not in (1, 2):
            raise ValueError("Only 8-bit or 16-bit PCM WAV files are supported")

        raw_frames = wav.readframes(nframes)

    dtype = np.uint8 if sampwidth == 1 else np.int16
    samples = np.frombuffer(raw_frames, dtype=dtype)
    return params, samples


def _write_pcm_samples(path: Path, params, data: bytes) -> None:
    import wave

    with wave.open(str(path), "wb") as wav:
        wav.setparams(params)
        wav.writeframes(data)


def _samples_to_bytes(samples: np.ndarray) -> bytes:
    if samples.dtype == np.uint8:
        return samples.tobytes()
    return samples.astype(np.int16).tobytes()


def _bytes_to_bits(data: bytes) -> str:
    return "".join(format(byte, "08b") for byte in data)


def _bits_to_bytes(bits: str) -> bytes:
    result = bytearray()
    for index in range(0, len(bits), 8):
        chunk = bits[index : index + 8]
        if len(chunk) < 8:
            chunk = chunk.ljust(8, "0")
        result.append(int(chunk, 2))
    return bytes(result)
