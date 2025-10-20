"""Video steganography helpers based on frame-wise LSB embedding."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from utils.logger import log_operation, setup_logger

logger = setup_logger(__name__)


class VideoSteganography:
    """Embed data into raw video frames using sequential 1-bit LSB."""

    def __init__(self) -> None:
        logger.debug("VideoSteganography initialized")

    @log_operation("Video Embed")
    def embed(
        self,
        cover_path: str | Path,
        secret_data: bytes,
        output_path: str | Path | None = None,
    ) -> str:
        cover_path = Path(cover_path)
        capture = cv2.VideoCapture(str(cover_path))
        if not capture.isOpened():
            raise ValueError(f"Unable to open video file: {cover_path}")

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        fourcc = int(capture.get(cv2.CAP_PROP_FOURCC))
        if fourcc == 0:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        capacity_bits = frame_count * width * height * 3 if frame_count else None
        payload = len(secret_data).to_bytes(4, byteorder="big") + secret_data
        bit_stream = _bytes_to_bits(payload)
        if capacity_bits is not None and len(bit_stream) > capacity_bits:
            available_bytes = max((capacity_bits // 8) - 4, 0)
            capture.release()
            raise ValueError(
                "Secret data too large for cover video (available "
                f"{available_bytes} bytes, need {len(secret_data)})."
            )

        if output_path is None:
            suffix = cover_path.suffix or ".mp4"
            output_path = cover_path.with_name(f"{cover_path.stem}_stego{suffix}")

        writer = cv2.VideoWriter(
            str(output_path),
            fourcc,
            fps,
            (width, height),
            True,
        )
        if not writer.isOpened():
            capture.release()
            raise ValueError("Unable to open video writer for output file")

        logger.debug(
            "Embedding %d bits into video with %d frames", len(bit_stream), frame_count
        )

        bit_index = 0
        success, frame = capture.read()
        while success:
            if bit_index < len(bit_stream):
                flat = frame.reshape(-1)
                remaining = len(bit_stream) - bit_index
                chunk = min(remaining, flat.size)
                bits = bit_stream[bit_index : bit_index + chunk]
                bit_values = np.frombuffer(bits.encode("ascii"), dtype=np.uint8) - ord("0")
                flat[:chunk] = (flat[:chunk] & 0xFE) | bit_values
                bit_index += chunk
            writer.write(frame)
            success, frame = capture.read()

        capture.release()
        writer.release()

        if bit_index < len(bit_stream):
            raise ValueError("Failed to embed entire payload into video")

        logger.info("Video embedding complete: %s", output_path)
        return str(output_path)

    @log_operation("Video Extract")
    def extract(self, stego_path: str | Path) -> bytes:
        stego_path = Path(stego_path)
        capture = cv2.VideoCapture(str(stego_path))
        if not capture.isOpened():
            raise ValueError(f"Unable to open video file: {stego_path}")

        bits = ""
        target_bits = None

        success, frame = capture.read()
        while success:
            flat = frame.reshape(-1)
            bits += "".join(str(int(value) & 1) for value in flat)

            if target_bits is None and len(bits) >= 32:
                data_length = int(bits[:32], 2)
                target_bits = 32 + data_length * 8

            if target_bits is not None and len(bits) >= target_bits:
                break

            success, frame = capture.read()

        capture.release()

        if len(bits) < 32:
            raise ValueError("Video file does not contain a valid payload")

        if target_bits is None:
            data_length = int(bits[:32], 2)
            target_bits = 32 + data_length * 8

        if len(bits) < target_bits:
            raise ValueError("Video payload truncated or corrupted")

        payload = _bits_to_bytes(bits[:target_bits])
        return payload[4:]

    def calculate_capacity(self, cover_path: str | Path) -> int:
        cover_path = Path(cover_path)
        capture = cv2.VideoCapture(str(cover_path))
        if not capture.isOpened():
            raise ValueError(f"Unable to open video file: {cover_path}")

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        capture.release()

        capacity_bits = frame_count * width * height * 3
        return max(0, (capacity_bits // 8) - 4)


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
