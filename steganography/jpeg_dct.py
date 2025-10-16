"""JPEG luminance-channel steganography implementation."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Tuple

import numpy as np
from PIL import Image

from utils.logger import log_operation, setup_logger

logger = setup_logger(__name__)


_BITS_PER_PIXEL = 1


class JPEGDCTSteganography:
    """Embed data inside the DCT coefficients of JPEG-compatible images."""

    def __init__(self, coefficients: Sequence[Tuple[int, int]] | None = None) -> None:
        # ``coefficients`` is accepted for backward compatibility but no longer used
        self.coefficients: Sequence[Tuple[int, int]] = tuple(coefficients or [])
        logger.debug("JPEG luminance stego initialized (coefficients ignored)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @log_operation("JPEG DCT Embed")
    def embed(
        self,
        cover_path: Path | str,
        secret_data: bytes,
        output_path: Path | str | None = None,
        *,
        coefficients: Sequence[Tuple[int, int]] | None = None,
    ) -> str:
        cover_path = Path(cover_path)
        coefficients = tuple(coefficients or self.coefficients)

        image = Image.open(cover_path)
        original_mode = image.mode
        luminance = image.convert("L")
        y_array = np.array(luminance, dtype=np.uint8)

        payload = len(secret_data).to_bytes(4, byteorder="big") + secret_data
        bit_stream = _bytes_to_bits(payload)
        logger.debug("Embedding %d bits into JPEG luminance channel", len(bit_stream))

        flat = y_array.flatten()
        capacity_bits = flat.size * _BITS_PER_PIXEL
        if len(bit_stream) > capacity_bits:
            raise ValueError("Secret data too large for cover image using JPEG method.")

        bit_index = 0
        for i in range(flat.size):
            if bit_index >= len(bit_stream):
                break
            pixel = int(flat[i])
            bit = int(bit_stream[bit_index])
            flat[i] = (pixel & ~1) | bit
            bit_index += 1

        y_array = flat.reshape(y_array.shape).astype(np.uint8)
        stego_image = Image.fromarray(y_array, mode="L")
        if original_mode == "RGB":
            stego_image = stego_image.convert("RGB")
        elif original_mode == "RGBA":
            stego_image = stego_image.convert("RGBA")

        if output_path is None:
            suffix = cover_path.suffix.lower()
            if suffix not in {".png", ".bmp", ".tiff"}:
                suffix = ".png"
            output_path = cover_path.with_name(f"{cover_path.stem}_dct{suffix}")

        if str(output_path).lower().endswith(('.png', '.bmp', '.tiff')):
            stego_image.save(output_path)
        else:
            stego_image.save(output_path, quality=95)

        logger.info("JPEG DCT embedded %d bytes into %s", len(secret_data), output_path)
        return str(output_path)

    @log_operation("JPEG DCT Extract")
    def extract(
        self,
        stego_path: Path | str,
        *,
        coefficients: Sequence[Tuple[int, int]] | None = None,
    ) -> bytes:
        stego_path = Path(stego_path)
        coefficients = tuple(coefficients or self.coefficients)

        image = Image.open(stego_path)
        luminance = image.convert("L")
        y_array = np.array(luminance, dtype=np.uint8)

        bits_collected = ""
        target_bits = None

        flat = y_array.flatten()
        for pixel in flat:
            bits_collected += "1" if (int(pixel) & 1) else "0"

            if target_bits is None and len(bits_collected) >= 32:
                data_length = int(bits_collected[:32], 2)
                target_bits = 32 + data_length * 8

            if target_bits is not None and len(bits_collected) >= target_bits:
                break

        if len(bits_collected) < 32:
            raise ValueError("Stego file does not contain a valid DCT payload")

        if target_bits is None:
            data_length = int(bits_collected[:32], 2)
            target_bits = 32 + data_length * 8

        payload_bits = bits_collected[:target_bits]
        payload = _bits_to_bytes(payload_bits)
        return payload[4:]

    def calculate_capacity(
        self,
        cover_path: Path | str,
        *,
        coefficients: Sequence[Tuple[int, int]] | None = None,
    ) -> int:
        cover_path = Path(cover_path)
        coefficients = tuple(coefficients or self.coefficients)

        image = Image.open(cover_path).convert("L")
        width, height = image.size

        bits = width * height * _BITS_PER_PIXEL
        return max(0, (bits // 8) - 4)


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
