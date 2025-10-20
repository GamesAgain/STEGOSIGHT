"""Lightweight heuristic-based ML detector placeholder.

ในเวอร์ชันนี้ยังไม่มีโมเดล Machine Learning จริง
แต่คำนวณคุณสมบัติบางอย่างของภาพเพื่อประมาณความเสี่ยง 0-100
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from utils.logger import setup_logger

logger = setup_logger(__name__)


class MLDetector:
    """Approximate ML-based detector using handcrafted features."""

    def __init__(self):
        self.version = "heuristic-v1"

    def analyze(self, file_path: Path) -> int:
        file_path = Path(file_path)
        try:
            image = Image.open(file_path).convert("RGB")
        except Exception as exc:
            logger.warning(f"MLDetector: cannot open {file_path}: {exc}")
            return 0

        arr = np.asarray(image).astype(np.float32) / 255.0
        gray = np.dot(arr, [0.2989, 0.5870, 0.1140])

        # Feature 1: high-frequency energy via Laplacian approximation
        laplace = np.abs(np.gradient(np.gradient(gray, axis=0), axis=0)) + np.abs(
            np.gradient(np.gradient(gray, axis=1), axis=1)
        )
        high_freq_energy = float(np.mean(laplace))

        # Feature 2: residual noise level (difference from blurred image)
        blurred = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=1))).astype(np.float32) / 255.0
        residual = np.abs(arr - blurred)
        noise_level = float(np.mean(residual))

        # Combine features into 0-100 score
        combined = (high_freq_energy * 20) + (noise_level * 15)
        score = int(max(0.0, min(100.0, combined * 100)))

        logger.debug(
            "MLDetector features - high_freq: %.4f, noise: %.4f, score: %d",
            high_freq_energy,
            noise_level,
            score,
        )
        return score
