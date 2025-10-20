"""Pixel Value Differencing (PVD) steganography implementation."""
from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
from PIL import Image

from utils.logger import log_operation, setup_logger

logger = setup_logger(__name__)


class PVDSteganography:
    """Simplified PVD steganography for RGB images.

    The implementation adapts the number of bits embedded per pixel pair
    based on the pixel-value difference range.  This keeps the visual
    distortion low for smooth regions while still providing capacity for
    textured areas.  The encoder stores a 4-byte length header before the
    payload so that extraction knows when to stop reading bits.
    """

    #: Difference ranges and the number of payload bits per pair
    _RANGES: Sequence[Tuple[int, int, int]] = (
        (0, 7, 3),
        (8, 15, 4),
        (16, 31, 5),
        (32, 63, 6),
        (64, 127, 7),
        (128, 255, 8),
    )

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
            diff = abs(int(flat[a_idx]) - int(flat[b_idx]))
            lower, _, bits_per_pair = self._range_for_difference(diff)

            chunk = bit_stream[bit_index : bit_index + bits_per_pair]
            if not chunk:
                break
            if len(chunk) < bits_per_pair:
                chunk = chunk.ljust(bits_per_pair, "0")
            bit_index += len(chunk)

            first_len = (bits_per_pair + 1) // 2
            second_len = bits_per_pair // 2

            flat[a_idx] = self._write_bits(flat[a_idx], chunk[:first_len])
            flat[b_idx] = self._write_bits(flat[b_idx], chunk[first_len:])

            # Re-adjust difference to stay within the range lower bound.
            new_diff = abs(int(flat[a_idx]) - int(flat[b_idx]))
            if new_diff < lower:
                adjust = lower - new_diff
                if flat[a_idx] >= flat[b_idx]:
                    flat[a_idx] = np.uint8(min(255, int(flat[a_idx]) + adjust))
                else:
                    flat[b_idx] = np.uint8(min(255, int(flat[b_idx]) + adjust))

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
            diff = abs(int(flat[a_idx]) - int(flat[b_idx]))
            _lower, _, bits_per_pair = self._range_for_difference(diff)

            first_len = (bits_per_pair + 1) // 2
            second_len = bits_per_pair // 2

            chunk = (
                self._read_bits(flat[a_idx], first_len)
                + self._read_bits(flat[b_idx], second_len)
            )

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
            diff = abs(int(flat[pos]) - int(flat[pos + 1]))
            _, _, bits = self._range_for_difference(diff)
            capacity += bits
        return capacity

    @classmethod
    def _range_for_difference(cls, diff: int) -> Tuple[int, int, int]:
        for lower, upper, bits in cls._RANGES:
            if lower <= diff <= upper:
                return lower, upper, bits
        return cls._RANGES[-1]

    @staticmethod
    def _write_bits(value: np.uint8, bits: str) -> np.uint8:
        if not bits:
            return value
        width = len(bits)
        mask = (1 << width) - 1
        new_value = (int(value) & ~mask) | int(bits, 2)
        return np.uint8(max(0, min(255, new_value)))

    @staticmethod
    def _read_bits(value: np.uint8, width: int) -> str:
        if width <= 0:
            return ""
        mask = (1 << width) - 1
        return format(int(value) & mask, f"0{width}b")


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
