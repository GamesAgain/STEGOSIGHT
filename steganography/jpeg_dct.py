"""JPEG DCT-domain steganography implementation."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from utils.logger import log_operation, setup_logger

logger = setup_logger(__name__)


_DEFAULT_COEFFICIENTS: Sequence[Tuple[int, int]] = ((4, 3), (3, 4))
_BLOCK_SIZE = 8


class JPEGDCTSteganography:
    """Embed data inside the DCT coefficients of JPEG-compatible images."""

    def __init__(self, coefficients: Sequence[Tuple[int, int]] | None = None) -> None:
        self.coefficients: Sequence[Tuple[int, int]] = (
            coefficients if coefficients is not None else _DEFAULT_COEFFICIENTS
        )
        logger.debug("JPEG DCT initialized with %s coefficients", len(self.coefficients))

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
        ycbcr = image.convert("YCbCr")
        y_channel, cb, cr = ycbcr.split()
        y_array = np.array(y_channel, dtype=np.float32)

        payload = len(secret_data).to_bytes(4, byteorder="big") + secret_data
        bit_stream = _bytes_to_bits(payload)
        logger.debug("Embedding %d bits using JPEG DCT", len(bit_stream))

        height, width = y_array.shape
        bit_index = 0
        for row in range(0, height, _BLOCK_SIZE):
            if bit_index >= len(bit_stream):
                break
            for col in range(0, width, _BLOCK_SIZE):
                if bit_index >= len(bit_stream):
                    break
                block = y_array[row : row + _BLOCK_SIZE, col : col + _BLOCK_SIZE]
                if block.shape != (_BLOCK_SIZE, _BLOCK_SIZE):
                    continue

                dct_block = cv2.dct(block)
                for coeff_pos in coefficients:
                    if bit_index >= len(bit_stream):
                        break
                    r, c = coeff_pos
                    coeff_value = _apply_parity(dct_block[r, c], int(bit_stream[bit_index]))
                    dct_block[r, c] = coeff_value
                    bit_index += 1

                y_array[row : row + _BLOCK_SIZE, col : col + _BLOCK_SIZE] = cv2.idct(
                    dct_block
                )

        if bit_index < len(bit_stream):
            raise ValueError(
                "Secret data too large for cover image using JPEG DCT method."
            )

        y_array = np.clip(y_array, 0, 255).astype(np.uint8)
        stego_y = Image.fromarray(y_array, mode="L")
        stego_image = Image.merge("YCbCr", (stego_y, cb, cr)).convert(original_mode)

        if output_path is None:
            output_path = cover_path.with_name(f"{cover_path.stem}_dct{cover_path.suffix}")
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
        ycbcr = image.convert("YCbCr")
        y_channel, _, _ = ycbcr.split()
        y_array = np.array(y_channel, dtype=np.float32)

        bits_collected = ""
        target_bits = None

        height, width = y_array.shape
        for row in range(0, height, _BLOCK_SIZE):
            for col in range(0, width, _BLOCK_SIZE):
                block = y_array[row : row + _BLOCK_SIZE, col : col + _BLOCK_SIZE]
                if block.shape != (_BLOCK_SIZE, _BLOCK_SIZE):
                    continue

                dct_block = cv2.dct(block)
                for r, c in coefficients:
                    bit = "1" if int(round(dct_block[r, c])) & 1 else "0"
                    bits_collected += bit

                    if target_bits is None and len(bits_collected) >= 32:
                        data_length = int(bits_collected[:32], 2)
                        target_bits = 32 + data_length * 8

                    if target_bits is not None and len(bits_collected) >= target_bits:
                        break
                if target_bits is not None and len(bits_collected) >= target_bits:
                    break
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

        image = Image.open(cover_path)
        y_channel = image.convert("YCbCr").split()[0]
        width, height = y_channel.size

        blocks = (height // _BLOCK_SIZE) * (width // _BLOCK_SIZE)
        bits = blocks * len(coefficients)
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


def _apply_parity(value: float, bit: int) -> float:
    integer_value = int(round(value))
    if integer_value == 0:
        integer_value = 1
    if (integer_value & 1) != bit:
        if integer_value > 0:
            integer_value += 1 if bit else -1
        else:
            integer_value -= 1 if bit else 1
        if integer_value == 0:
            integer_value = 1 if bit else -1
    return float(integer_value)
