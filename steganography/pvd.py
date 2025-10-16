"""Pixel Value Differencing (PVD) steganography implementation."""
from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
from PIL import Image

from utils.logger import log_operation, setup_logger

logger = setup_logger(__name__)


class PVDSteganography:
    """Pair-based data hiding inspired by PVD techniques.

    To guarantee robust extraction across different environments the
    implementation uses a fixed number of payload bits per pixel pair.
    While this is a simplification compared to the original Wu-Tsai PVD
    algorithm, it retains the concept of distributing payload across
    neighbouring pixels to minimise distortion.
    """

    _BITS_PER_PAIR = 4

    def __init__(self, pair_skip: int = 1) -> None:
        self.pair_skip = max(1, pair_skip)
        logger.debug("PVD initialized: pair_skip=%s", self.pair_skip)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @log_operation("PVD Embed")
    def embed(
        self,
        cover_path: Path | str,
        secret_data: bytes,
        output_path: Path | str | None = None,
        *,
        pair_skip: int | None = None,
    ) -> str:
        """Embed ``secret_data`` inside ``cover_path``.

        Args:
            cover_path: Path to the cover image.
            secret_data: Arbitrary bytes to hide.
            output_path: Destination for the stego image.  When ``None``
                the image is written next to the cover file with a
                ``_pvd`` suffix.
            pair_skip: Process one pixel pair out of ``pair_skip`` pairs.
                Larger values increase stealth at the cost of capacity.
        """

        cover_path = Path(cover_path)
        pair_skip = max(1, pair_skip or self.pair_skip)

        image = Image.open(cover_path)
        if image.mode != "RGB":
            logger.info("Converting %s from %s to RGB for PVD", cover_path, image.mode)
            image = image.convert("RGB")

        pixels = np.array(image, dtype=np.uint8)
        flat = pixels.reshape(-1)

        payload = len(secret_data).to_bytes(4, byteorder="big") + secret_data
        bit_stream = _bytes_to_bits(payload)

        capacity_bits = self._estimate_capacity(flat, pair_skip)
        if len(bit_stream) > capacity_bits:
            raise ValueError(
                "Secret data too large for cover image using PVD (available "
                f"{capacity_bits // 8} bytes, need {len(bit_stream) // 8})."
            )

        logger.debug("Embedding %d bits using PVD", len(bit_stream))

        bit_index = 0
        for pair_index, pos in enumerate(range(0, len(flat) - 1, 2)):
            if pair_index % pair_skip != 0:
                continue
            if bit_index >= len(bit_stream):
                break

            a_idx = pos
            b_idx = pos + 1
            bits_per_pair = self._BITS_PER_PAIR

            chunk = bit_stream[bit_index : bit_index + bits_per_pair]
            if not chunk:
                break
            if len(chunk) < bits_per_pair:
                chunk = chunk.ljust(bits_per_pair, "0")
            bit_index += len(chunk)

            first_len = (bits_per_pair + 1) // 2
            second_len = bits_per_pair - first_len

            if first_len:
                mask = (1 << first_len) - 1
                value = int(chunk[:first_len], 2)
                pixel_a = (int(flat[a_idx]) & ~mask) | value
            if second_len:
                mask = (1 << second_len) - 1
                value = int(chunk[first_len:], 2)
                pixel_b = (int(flat[b_idx]) & ~mask) | value

            flat[a_idx] = np.uint8(pixel_a)
            flat[b_idx] = np.uint8(pixel_b)

        if bit_index < len(bit_stream):
            raise ValueError("Failed to embed full payload using PVD algorithm")

        stego_pixels = flat.reshape(pixels.shape)
        stego_image = Image.fromarray(stego_pixels, mode="RGB")

        if output_path is None:
            output_path = cover_path.with_name(f"{cover_path.stem}_pvd{cover_path.suffix}")
        stego_image.save(output_path)

        logger.info("PVD embedded %d bytes into %s", len(secret_data), output_path)
        return str(output_path)

    @log_operation("PVD Extract")
    def extract(self, stego_path: Path | str, *, pair_skip: int | None = None) -> bytes:
        stego_path = Path(stego_path)
        pair_skip = max(1, pair_skip or self.pair_skip)

        image = Image.open(stego_path)
        if image.mode != "RGB":
            image = image.convert("RGB")

        pixels = np.array(image, dtype=np.uint8)
        flat = pixels.reshape(-1)

        bits_collected = ""
        target_bits = None
        for pair_index, pos in enumerate(range(0, len(flat) - 1, 2)):
            if pair_index % pair_skip != 0:
                continue

            a_idx = pos
            b_idx = pos + 1
            pixel_a = int(flat[a_idx])
            pixel_b = int(flat[b_idx])
            bits_per_pair = self._BITS_PER_PAIR

            first_len = (bits_per_pair + 1) // 2
            second_len = bits_per_pair - first_len

            bits = ""
            if first_len:
                mask = (1 << first_len) - 1
                bits += format(pixel_a & mask, f"0{first_len}b")
            if second_len:
                mask = (1 << second_len) - 1
                bits += format(pixel_b & mask, f"0{second_len}b")

            chunk = bits

            if target_bits is None and len(bits_collected) + len(chunk) >= 32:
                prefix_needed = 32 - len(bits_collected)
                bits_collected += chunk[:prefix_needed]
                data_length = int(bits_collected[:32], 2)
                target_bits = 32 + data_length * 8
                bits_collected += chunk[prefix_needed:]
            else:
                bits_collected += chunk

            if target_bits is not None and len(bits_collected) >= target_bits:
                break

        if len(bits_collected) < 32:
            raise ValueError("Stego file does not contain a valid PVD payload")

        if target_bits is None:
            data_length = int(bits_collected[:32], 2)
            target_bits = 32 + data_length * 8

        payload_bits = bits_collected[:target_bits]
        payload = _bits_to_bytes(payload_bits)
        return payload[4:]

    def calculate_capacity(
        self, cover_path: Path | str, *, pair_skip: int | None = None
    ) -> int:
        cover_path = Path(cover_path)
        pair_skip = max(1, pair_skip or self.pair_skip)

        image = Image.open(cover_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        pixels = np.array(image, dtype=np.uint8)
        flat = pixels.reshape(-1)

        bits = self._estimate_capacity(flat, pair_skip)
        return max(0, (bits // 8) - 4)  # subtract header space

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _estimate_capacity(self, flat: np.ndarray, pair_skip: int) -> int:
        capacity = 0
        for pair_index, pos in enumerate(range(0, len(flat) - 1, 2)):
            if pair_index % pair_skip != 0:
                continue
            bits = self._BITS_PER_PAIR
            capacity += bits
        return capacity

def _bytes_to_bits(data: bytes) -> str:
    return "".join(format(byte, "08b") for byte in data)


def _bits_to_bytes(bits: str) -> bytes:
    chunks: List[bytes] = []
    for start in range(0, len(bits), 8):
        chunk = bits[start : start + 8]
        if len(chunk) < 8:
            chunk = chunk.ljust(8, "0")
        chunks.append(int(chunk, 2).to_bytes(1, byteorder="big"))
    return b"".join(chunks)
