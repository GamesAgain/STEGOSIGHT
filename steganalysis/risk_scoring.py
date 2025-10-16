"""
Risk Scoring Engine
ระบบประเมินความเสี่ยงของการซ่อนข้อมูล
"""

from pathlib import Path
from typing import Dict, Iterable, Tuple

from config import ANALYSIS_SETTINGS
from utils.logger import setup_logger, log_operation

logger = setup_logger(__name__)


class RiskScorer:
    """ระบบประเมินคะแนนความเสี่ยง"""

    def __init__(self):
        """Initialize risk scorer"""
        settings = ANALYSIS_SETTINGS or {}
        default_weights = {
            "chi_square": 0.4,
            "histogram": 0.3,
            "ela": 0.3,
            "ml": 0.2,
        }
        self.weights = settings.get("weights", default_weights)
        self.thresholds = {
            "low": 30,
            "medium": 60,
            "high": 80,
        }
        self.thresholds.update(settings.get("risk_thresholds", {}))
        self.default_methods = settings.get(
            "default_methods", ["chi-square", "histogram", "ela"]
        )
        logger.debug("RiskScorer initialized")

    @log_operation("Calculate Risk Score")
    def calculate_risk(self, file_path):
        """
        คำนวณคะแนนความเสี่ยงของไฟล์

        Args:
            file_path: path ของไฟล์

        Returns:
            dict: {'score': int, 'level': str, 'details': dict}
        """
        file_path = Path(file_path)
        methods = self._default_methods_for_file(file_path)
        scores, errors = self._run_methods(file_path, methods)
        summary = self._summarize(scores)
        summary["details"] = scores
        if errors:
            summary["errors"] = errors
        return summary

    def analyze_file(self, file_path, methods=["all"]):
        """
        วิเคราะห์ไฟล์ด้วยวิธีที่ระบุ

        Args:
            file_path: path ของไฟล์
            methods: รายการวิธีการวิเคราะห์

        Returns:
            dict: ผลการวิเคราะห์
        """
        file_path = Path(file_path)
        method_list = self._normalize_methods(methods, file_path)
        scores, errors = self._run_methods(file_path, method_list)
        summary = self._summarize(scores)
        result = {
            "score": summary["score"],
            "level": summary["level"],
            "details": scores,
            "recommendation": summary["recommendation"],
        }
        if errors:
            result["errors"] = errors
        return result

    def compare_before_after(self, original_path, stego_path):
        """
        เปรียบเทียบภาพก่อนและหลังการซ่อนข้อมูล

        Args:
            original_path: path ของภาพต้นฉบับ
            stego_path: path ของภาพที่มีข้อมูลซ่อนอยู่

        Returns:
            dict: ผลการเปรียบเทียบ
        """
        import numpy as np
        from PIL import Image

        original = np.array(Image.open(original_path))
        stego = np.array(Image.open(stego_path))

        # Calculate differences
        diff = np.abs(original.astype(float) - stego.astype(float))

        # Statistics
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        std_diff = np.std(diff)
        modified_pixels = np.sum(diff > 0)
        total_pixels = diff.size
        modification_rate = (modified_pixels / total_pixels) * 100

        # PSNR (Peak Signal-to-Noise Ratio)
        mse = np.mean((original.astype(float) - stego.astype(float)) ** 2)
        if mse == 0:
            psnr = 100
        else:
            max_pixel = 255.0
            psnr = 20 * np.log10(max_pixel / np.sqrt(mse))

        result = {
            "max_difference": float(max_diff),
            "mean_difference": float(mean_diff),
            "std_difference": float(std_diff),
            "modified_pixels": int(modified_pixels),
            "modification_rate": float(modification_rate),
            "psnr": float(psnr),
            "quality_assessment": self._assess_quality(psnr, modification_rate),
        }

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_methods(
        self, file_path: Path, methods: Iterable[str]
    ) -> Tuple[Dict[str, float], Dict[str, str]]:
        scores: Dict[str, float] = {}
        errors: Dict[str, str] = {}

        for method in methods:
            try:
                score = self._dispatch_method(method, file_path)
                scores[method.replace("-", "_")] = round(float(score), 2)
            except Exception as exc:
                logger.warning(f"{method} analysis failed: {exc}")
                errors[method] = str(exc)
                scores[method.replace("-", "_")] = 0.0

        return scores, errors

    def _dispatch_method(self, method: str, file_path: Path) -> float:
        if method == "chi-square":
            from .chi_square import ChiSquareAttack

            analyzer = ChiSquareAttack()
            return analyzer.analyze(file_path)
        if method == "histogram":
            from .histogram import HistogramAnalysis

            analyzer = HistogramAnalysis()
            return analyzer.analyze(file_path)
        if method == "ela":
            from .ela import ErrorLevelAnalysis

            analyzer = ErrorLevelAnalysis()
            return analyzer.analyze(file_path)
        if method == "ml":
            from .ml_detector import MLDetector

            analyzer = MLDetector()
            return analyzer.analyze(file_path)
        raise ValueError(f"Unknown analysis method: {method}")

    def _summarize(self, scores: Dict[str, float]) -> Dict[str, object]:
        if not scores:
            return {
                "score": 0,
                "level": "LOW",
                "recommendation": "ไม่พบข้อมูลเพียงพอสำหรับการประเมิน",
            }

        total_weight = 0.0
        weighted_score = 0.0
        default_weight = self.weights.get("default", 0.2)

        for method, score in scores.items():
            weight = self.weights.get(method, default_weight)
            weighted_score += score * weight
            total_weight += weight

        final_score = weighted_score / total_weight if total_weight else 0.0
        final_score = max(0.0, min(100.0, final_score))

        level = self._determine_level(final_score)
        recommendation = self._get_recommendation(final_score, scores)

        return {
            "score": round(final_score, 2),
            "level": level,
            "recommendation": recommendation,
        }

    def _determine_level(self, score):
        if score < self.thresholds["low"]:
            return "LOW"
        if score < self.thresholds["medium"]:
            return "MEDIUM"
        if score < self.thresholds["high"]:
            return "HIGH"
        return "CRITICAL"

    def _get_recommendation(self, score, details):
        level = self._determine_level(score)

        recommendations = {
            "LOW": "ปลอดภัย - ไม่พบร่องรอยที่น่าสงสัยหรือพบน้อยมาก",
            "MEDIUM": "ปานกลาง - พบร่องรอยบางอย่างที่อาจตรวจจับได้ ควรพิจารณาใช้การทำให้เป็นกลาง",
            "HIGH": "เสี่ยงสูง - พบร่องรอยหลายอย่างที่ตรวจจับได้ง่าย แนะนำให้ทำให้เป็นกลางหรือเปลี่ยนวิธีการซ่อน",
            "CRITICAL": "วิกฤต - พบร่องรอยชัดเจนมาก ควรใช้ไฟล์ใหม่และวิธีการที่แตกต่าง",
        }

        base_rec = recommendations.get(level, "")

        if details.get("chi_square", 0) > 70:
            base_rec += "\n- พบความผิดปกติทางสถิติสูง ควรใช้วิธี Adaptive หรือ PVD แทน LSB"

        if details.get("histogram", 0) > 70:
            base_rec += "\n- พบความผิดปกติในฮิสโตแกรม ควรใช้ภาพที่มีความซับซ้อนสูงกว่า"

        if details.get("ela", 0) > 70:
            base_rec += "\n- พบความคลาดเคลื่อนสูงใน ELA ควรบีบอัดภาพซ้ำก่อนส่ง"

        if details.get("ml", 0) > 70:
            base_rec += "\n- ตัวตรวจจับ ML ให้คะแนนสูง แนะนำให้ทดสอบด้วยวิธีอื่นก่อนเผยแพร่"

        return base_rec

    def _default_methods_for_file(self, file_path: Path) -> Iterable[str]:
        methods = list(self.default_methods)
        if file_path.suffix.lower() not in [".jpg", ".jpeg"] and "ela" in methods:
            methods = [m for m in methods if m != "ela"]
        return methods

    def _normalize_methods(
        self, methods: Iterable[str], file_path: Path
    ) -> Iterable[str]:
        if not methods or "all" in methods:
            return self._default_methods_for_file(file_path)
        normalized = []
        for method in methods:
            method = method.lower()
            if method == "all":
                normalized.extend(self._default_methods_for_file(file_path))
            else:
                normalized.append(method)
        seen = set()
        result = []
        for method in normalized:
            if method not in seen:
                if method != "ela" or file_path.suffix.lower() in [".jpg", ".jpeg"]:
                    result.append(method)
                    seen.add(method)
        return result

    def _assess_quality(self, psnr, mod_rate):
        if psnr > 40 and mod_rate < 10:
            return "Excellent - แทบไม่มีความแตกต่างที่มองเห็นได้"
        elif psnr > 35 and mod_rate < 20:
            return "Good - ความแตกต่างเล็กน้อยที่มองไม่เห็น"
        elif psnr > 30:
            return "Fair - อาจมีความแตกต่างเล็กน้อย"
        else:
            return "Poor - มีความแตกต่างที่มองเห็นได้"
