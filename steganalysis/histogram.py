"""Histogram Analysis
วิเคราะห์ความผิดปกติของฮิสโตแกรมแบบง่าย แล้วสเกลคะแนน 0..100
"""
from pathlib import Path
import numpy as np
from PIL import Image
from utils.logger import setup_logger

logger = setup_logger(__name__)

class HistogramAnalyzer:
    """Compute a basic histogram anomaly score (0-100). Higher = more suspicious."""
    def __init__(self, bins: int = 256):
        self.bins = bins

    def analyze(self, image_path: Path) -> int:
        image_path = Path(image_path)
        try:
            img = Image.open(image_path).convert('RGB')
        except Exception as e:
            logger.warning(f"Histogram: cannot open {image_path}: {e}")
            return 0

        arr = np.asarray(img)
        score_acc = 0.0
        for ch in range(3):
            hist, _ = np.histogram(arr[:,:,ch], bins=self.bins, range=(0,255), density=True)
            smooth = np.convolve(hist, np.ones(5)/5.0, mode='same')
            dev = np.abs(hist - smooth)
            score_acc += float(dev.mean())
        normalized = min(1.0, score_acc / 0.06)
        return int(normalized * 100)
