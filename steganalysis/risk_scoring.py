"""
Risk Scoring Engine
ระบบประเมินความเสี่ยงของการซ่อนข้อมูล
"""

import numpy as np
from PIL import Image
from pathlib import Path
from utils.logger import setup_logger, log_operation
from config import ANALYSIS_SETTINGS

logger = setup_logger(__name__)


class RiskScorer:
    """ระบบประเมินคะแนนความเสี่ยง"""
    
    def __init__(self):
        """Initialize risk scorer"""
        settings = ANALYSIS_SETTINGS or {}
        default_thresholds = {'low': 25, 'medium': 50, 'high': 75}
        self.thresholds = settings.get('risk_thresholds', default_thresholds)
        self.weights = settings.get('weights', {'chi_square': 0.4, 'ela': 0.3, 'histogram': 0.3})
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
        
        # Run different analysis methods
        scores = {}
        
        try:
            from .chi_square import ChiSquareAttack
            chi = ChiSquareAttack()
            scores['chi_square'] = chi.analyze(file_path)
        except Exception as e:
            logger.warning(f"Chi-square analysis failed: {e}")
            scores['chi_square'] = 0
        
        try:
            from .histogram import HistogramAnalysis
            hist = HistogramAnalysis()
            scores['histogram'] = hist.analyze(file_path)
        except Exception as e:
            logger.warning(f"Histogram analysis failed: {e}")
            scores['histogram'] = 0
        
        # For JPEG files, run ELA
        if file_path.suffix.lower() in ['.jpg', '.jpeg']:
            try:
                from .ela import ErrorLevelAnalysis
                ela = ErrorLevelAnalysis()
                scores['ela'] = ela.analyze(file_path)
            except Exception as e:
                logger.warning(f"ELA analysis failed: {e}")
                scores['ela'] = 0
        
        # Calculate weighted average
        total_weight = 0
        weighted_score = 0

        for method, score in scores.items():
            weight = self.weights.get(method, 0.2)
            weighted_score += score * weight
            total_weight += weight
        
        final_score = weighted_score / total_weight if total_weight > 0 else 0
        final_score = min(100, max(0, final_score))
        
        # Determine risk level
        level = self._determine_level(final_score)
        
        result = {
            'score': round(final_score, 2),
            'level': level,
            'details': scores,
            'recommendation': self._get_recommendation(final_score, scores)
        }
        
        logger.info(f"Risk score: {final_score:.2f} ({level})")
        return result
    
    def analyze_file(self, file_path, methods=['all']):
        """
        วิเคราะห์ไฟล์ด้วยวิธีที่ระบุ
        
        Args:
            file_path: path ของไฟล์
            methods: รายการวิธีการวิเคราะห์
        
        Returns:
            dict: ผลการวิเคราะห์
        """
        file_path = Path(file_path)
        results = {}
        
        if 'all' in methods or 'chi-square' in methods:
            try:
                from .chi_square import ChiSquareAttack
                chi = ChiSquareAttack()
                results['chi_square'] = chi.analyze(file_path)
            except Exception as e:
                logger.error(f"Chi-square failed: {e}")
                results['chi_square'] = {'score': 0, 'error': str(e)}
        
        if 'all' in methods or 'histogram' in methods:
            try:
                from .histogram import HistogramAnalysis
                hist = HistogramAnalysis()
                results['histogram'] = hist.analyze(file_path)
            except Exception as e:
                logger.error(f"Histogram failed: {e}")
                results['histogram'] = {'score': 0, 'error': str(e)}
        
        if 'all' in methods or 'ela' in methods:
            if file_path.suffix.lower() in ['.jpg', '.jpeg']:
                try:
                    from .ela import ErrorLevelAnalysis
                    ela = ErrorLevelAnalysis()
                    results['ela'] = ela.analyze(file_path)
                except Exception as e:
                    logger.error(f"ELA failed: {e}")
                    results['ela'] = {'score': 0, 'error': str(e)}
        
        if 'all' in methods or 'ml' in methods:
            try:
                from .ml_detector import MLDetector
                ml = MLDetector()
                results['ml'] = ml.analyze(file_path)
            except Exception as e:
                logger.error(f"ML detection failed: {e}")
                results['ml'] = {'score': 0, 'error': str(e)}
        
        return results
    
    def _determine_level(self, score):
        """กำหนดระดับความเสี่ยงจากคะแนน"""
        if score < self.thresholds['low']:
            return 'LOW'
        elif score < self.thresholds['medium']:
            return 'MEDIUM'
        elif score < self.thresholds['high']:
            return 'HIGH'
        else:
            return 'CRITICAL'
    
    def _get_recommendation(self, score, details):
        """สร้างคำแนะนำตามคะแนน"""
        level = self._determine_level(score)
        
        recommendations = {
            'LOW': 'ปลอดภัย - ไม่พบร่องรอยที่น่าสงสัยหรือพบน้อยมาก',
            'MEDIUM': 'ปานกลาง - พบร่องรอยบางอย่างที่อาจตรวจจับได้ ควรพิจารณาใช้การทำให้เป็นกลาง',
            'HIGH': 'เสี่ยงสูง - พบร่องรอยหลายอย่างที่ตรวจจับได้ง่าย แนะนำให้ทำให้เป็นกลางหรือเปลี่ยนวิธีการซ่อน',
            'CRITICAL': 'วิกฤต - พบร่องรอยชัดเจนมาก ควรใช้ไฟล์ใหม่และวิธีการที่แตกต่าง'
        }
        
        base_rec = recommendations.get(level, '')
        
        # Add specific recommendations based on high-scoring methods
        if details.get('chi_square', 0) > 70:
            base_rec += '\n- พบความผิดปกติทางสถิติสูง ควรใช้วิธี Adaptive หรือ PVD แทน LSB'
        
        if details.get('histogram', 0) > 70:
            base_rec += '\n- พบความผิดปกติในฮิสโตแกรม ควรใช้ภาพที่มีความซับซ้อนสูงกว่า'
        
        if details.get('ela', 0) > 70:
            base_rec += '\n- พบความคลาดเคลื่อนสูงใน ELA ควรบีบอัดภาพซ้ำก่อนส่ง'
        
        return base_rec
    
    def compare_before_after(self, original_path, stego_path):
        """
        เปรียบเทียบภาพก่อนและหลังการซ่อนข้อมูล
        
        Args:
            original_path: path ของภาพต้นฉบับ
            stego_path: path ของภาพที่มีข้อมูลซ่อนอยู่
        
        Returns:
            dict: ผลการเปรียบเทียบ
        """
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
            'max_difference': float(max_diff),
            'mean_difference': float(mean_diff),
            'std_difference': float(std_diff),
            'modified_pixels': int(modified_pixels),
            'modification_rate': float(modification_rate),
            'psnr': float(psnr),
            'quality_assessment': self._assess_quality(psnr, modification_rate)
        }
        
        return result
    
    def _assess_quality(self, psnr, mod_rate):
        """ประเมินคุณภาพของการซ่อนข้อมูล"""
        if psnr > 40 and mod_rate < 10:
            return 'Excellent - แทบไม่มีความแตกต่างที่มองเห็นได้'
        elif psnr > 35 and mod_rate < 20:
            return 'Good - ความแตกต่างเล็กน้อยที่มองไม่เห็น'
        elif psnr > 30:
            return 'Fair - อาจมีความแตกต่างเล็กน้อย'
        else:
            return 'Poor - มีความแตกต่างที่มองเห็นได้'