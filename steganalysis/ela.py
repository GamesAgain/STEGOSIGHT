"""Error Level Analysis (ELA)
วิเคราะห์ JPEG/ภาพทั่วไปโดยเปรียบเทียบข้อผิดพลาดหลังบันทึกใหม่ แล้วสเกลคะแนน 0..100
"""
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageChops, ImageStat
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ELAAnalyzer:
    """Compute a normalized ELA score (0-100). Higher means more suspicious."""
    def __init__(self, quality: int = 95, scale: float = 10.0):
        self.quality = quality
        self.scale = scale

    def analyze(self, image_path: Path) -> int:
        image_path = Path(image_path)
        try:
            img = Image.open(image_path).convert("RGB")
        except Exception as e:
            logger.warning(f"ELA: cannot open {image_path}: {e}")
            return 0

        buf = BytesIO()
        try:
            img.save(buf, "JPEG", quality=self.quality)
            buf.seek(0)
            jpg = Image.open(buf)
        except Exception as e:
            logger.warning(f"ELA: JPEG recompress failed: {e}")
            return 0

        ela = ImageChops.difference(img, jpg)

        extrema = ela.getextrema()
        max_diff = max([mx for (_, mx) in extrema])
        if max_diff == 0:
            return 0
        factor = self.scale * 255.0 / max_diff

        # scale channels via point()
        def scale_channel(c):
            return c.point(lambda v: min(255, int(v * factor)))
        ela_scaled = Image.merge("RGB", [scale_channel(ela.split()[i]) for i in range(3)])

        stat = ImageStat.Stat(ela_scaled.convert('L'))
        mean_val = stat.mean[0]  # 0..255
        score = int(max(0, min(100, (mean_val / 255.0) * 100)))
        return score
