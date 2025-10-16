"""
Chi-Square Attack
การวิเคราะห์ทางสถิติเพื่อตรวจจับ LSB Steganography
"""

import numpy as np
from PIL import Image
from pathlib import Path
from scipy import stats
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ChiSquareAttack:
    """Chi-Square Attack สำหรับตรวจจับ Sequential LSB"""
    
    def __init__(self, sample_size=1000):
        """
        Initialize Chi-Square attack
        
        Args:
            sample_size: จำนวน pairs ที่จะใช้วิเคราะห์
        """
        self.sample_size = sample_size
    
    def analyze(self, image_path):
        """
        วิเคราะห์ภาพด้วย Chi-Square test
        
        Args:
            image_path: path ของภาพ
        
        Returns:
            float: คะแนนความเสี่ยง (0-100)
        """
        image_path = Path(image_path)
        
        try:
            # Load image
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            pixels = np.array(image)
            
            # Test each channel
            channel_scores = []
            for c in range(3):
                channel_data = pixels[:, :, c].flatten()
                score = self._chi_square_test(channel_data)
                channel_scores.append(score)
            
            # Average score across channels
            avg_score = np.mean(channel_scores)
            
            logger.debug(f"Chi-Square scores: R={channel_scores[0]:.2f}, "
                        f"G={channel_scores[1]:.2f}, B={channel_scores[2]:.2f}")
            
            return avg_score
            
        except Exception as e:
            logger.error(f"Chi-square analysis failed: {e}")
            return 0
    
    def _chi_square_test(self, data):
        """
        ทำ Chi-Square test บนข้อมูล
        
        Args:
            data: array ของค่าพิกเซล
        
        Returns:
            float: คะแนนความเสี่ยง (0-100)
        """
        # Sample data if too large
        if len(data) > self.sample_size * 2:
            indices = np.random.choice(len(data), self.sample_size * 2, replace=False)
            data = data[indices]
        
        # Count pairs of values (2i, 2i+1)
        observed = {}
        expected = {}
        
        for i in range(0, 256, 2):
            # Count occurrences of value pairs
            count_even = np.sum(data == i)
            count_odd = np.sum(data == i + 1)
            
            # Observed frequency
            observed[i] = count_even
            observed[i + 1] = count_odd
            
            # Expected frequency (should be equal if no LSB embedding)
            total = count_even + count_odd
            expected[i] = total / 2
            expected[i + 1] = total / 2
        
        # Calculate chi-square statistic
        chi_square = 0
        for i in range(0, 256, 2):
            if expected[i] > 0:
                chi_square += ((observed[i] - expected[i]) ** 2) / expected[i]
            if expected[i + 1] > 0:
                chi_square += ((observed[i + 1] - expected[i + 1]) ** 2) / expected[i + 1]
        
        # Degrees of freedom
        dof = 127  # (256/2) - 1
        
        # Calculate p-value
        p_value = 1 - stats.chi2.cdf(chi_square, dof)
        
        # Convert to risk score (lower p-value = higher risk)
        # p-value < 0.05 indicates significant deviation
        if p_value < 0.001:
            risk_score = 90
        elif p_value < 0.01:
            risk_score = 75
        elif p_value < 0.05:
            risk_score = 60
        elif p_value < 0.1:
            risk_score = 40
        else:
            risk_score = max(0, (1 - p_value) * 100)
        
        return risk_score
    
    def detect_embedding_length(self, image_path):
        """
        พยายามประมาณความยาวของข้อมูลที่ซ่อนอยู่
        
        Args:
            image_path: path ของภาพ
        
        Returns:
            dict: ข้อมูลการประมาณ
        """
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        pixels = np.array(image).flatten()
        
        # Test different lengths
        test_lengths = [100, 500, 1000, 5000, 10000, 50000]
        results = []
        
        for length in test_lengths:
            if length > len(pixels):
                break
            
            sample = pixels[:length]
            score = self._chi_square_test(sample)
            results.append({
                'length': length,
                'score': score
            })
        
        # Find the length where score starts to increase significantly
        if len(results) > 1:
            max_increase = 0
            estimated_length = 0
            
            for i in range(1, len(results)):
                increase = results[i]['score'] - results[i-1]['score']
                if increase > max_increase:
                    max_increase = increase
                    estimated_length = results[i]['length']
            
            return {
                'estimated_length': estimated_length,
                'confidence': min(100, max_increase * 2),
                'all_results': results
            }
        
        return {'estimated_length': 0, 'confidence': 0, 'all_results': results}