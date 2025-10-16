"""
Adaptive Steganography
วิธีการซ่อนข้อมูลแบบปรับตัวตามเนื้อหาของภาพ
"""

import numpy as np
from PIL import Image
from pathlib import Path
import cv2
from utils.logger import setup_logger, log_operation
from .lsb import LSBSteganography

logger = setup_logger(__name__)


class AdaptiveSteganography:
    """
    Adaptive Steganography ที่เลือกวิธีการและพื้นที่ซ่อนข้อมูล
    โดยอัตโนมัติตามลักษณะของภาพ
    """
    
    def __init__(self):
        """Initialize adaptive steganography"""
        self.lsb = LSBSteganography(mode='adaptive')
        self.last_method = 'adaptive'
        logger.debug("AdaptiveSteganography initialized")
    
    @log_operation("Adaptive Embed")
    def embed(
        self,
        cover_path,
        secret_data,
        method='auto',
        output_path=None,
        *,
        options=None,
    ):
        """
        ซ่อนข้อมูลโดยเลือกวิธีที่เหมาะสมอัตโนมัติ
        
        Args:
            cover_path: path ของไฟล์ต้นฉบับ
            secret_data: ข้อมูลที่จะซ่อน (bytes)
            method: วิธีการ ('auto', 'lsb', 'pvd', 'dct')
            output_path: path สำหรับบันทึกไฟล์ผลลัพธ์
        
        Returns:
            str: path ของไฟล์ที่มีข้อมูลซ่อนอยู่
        """
        cover_path = Path(cover_path)
        
        # Analyze cover file
        file_type = self._detect_file_type(cover_path)
        logger.info(f"Cover file type: {file_type}")
        
        # Auto-select method if needed
        if method == 'auto' or method == 'adaptive':
            method = self._select_best_method(cover_path, secret_data)
            logger.info(f"Auto-selected method: {method}")

        self.last_method = method
        options = options or {}

        # Delegate to appropriate method
        if method == 'lsb':
            lsb_bits = options.get('lsb_bits')
            lsb_mode = options.get('lsb_mode', self.lsb.mode)
            bits = lsb_bits if lsb_bits is not None else self.lsb.bits_per_channel
            stego = LSBSteganography(bits_per_channel=bits, mode=lsb_mode)
            return stego.embed(cover_path, secret_data, output_path)
        elif method == 'pvd':
            from .pvd import PVDSteganography
            pair_skip = options.get('pair_skip')
            pvd = PVDSteganography(pair_skip=pair_skip or 1)
            return pvd.embed(cover_path, secret_data, output_path, pair_skip=pair_skip)
        elif method == 'dct':
            from .jpeg_dct import JPEGDCTSteganography
            coefficients = options.get('coefficients')
            dct = JPEGDCTSteganography(coefficients=coefficients)
            return dct.embed(
                cover_path,
                secret_data,
                output_path,
                coefficients=coefficients,
            )
        else:
            raise ValueError(f"Unknown method: {method}")
    
    @log_operation("Adaptive Extract")
    def extract(self, stego_path, method='auto'):
        """
        ดึงข้อมูลออกจากไฟล์
        
        Args:
            stego_path: path ของไฟล์ที่มีข้อมูลซ่อนอยู่
            method: วิธีการที่ใช้ซ่อน
        
        Returns:
            bytes: ข้อมูลที่ดึงออกมา
        """
        stego_path = Path(stego_path)
        
        # Auto-detect method if needed
        if method == 'auto' or method == 'adaptive':
            method = self._detect_embedding_method(stego_path)
            logger.info(f"Auto-detected method: {method}")
        
        # Delegate to appropriate method
        if method == 'lsb':
            return self.lsb.extract(stego_path)
        elif method == 'pvd':
            from .pvd import PVDSteganography
            pvd = PVDSteganography()
            return pvd.extract(stego_path)
        elif method == 'dct':
            from .jpeg_dct import JPEGDCTSteganography
            dct = JPEGDCTSteganography()
            return dct.extract(stego_path)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def _detect_file_type(self, file_path):
        """ตรวจสอบประเภทของไฟล์"""
        suffix = file_path.suffix.lower()
        
        if suffix in ['.png', '.bmp', '.tiff']:
            return 'lossless_image'
        elif suffix in ['.jpg', '.jpeg']:
            return 'lossy_image'
        elif suffix in ['.wav', '.flac']:
            return 'audio'
        elif suffix in ['.mp4', '.avi', '.mkv']:
            return 'video'
        else:
            return 'unknown'
    
    def _select_best_method(self, cover_path, secret_data):
        """
        เลือกวิธีการที่เหมาะสมที่สุดตามลักษณะของไฟล์และข้อมูล
        
        Args:
            cover_path: path ของไฟล์ต้นฉบับ
            secret_data: ข้อมูลที่จะซ่อน
        
        Returns:
            str: ชื่อวิธีการ
        """
        file_type = self._detect_file_type(cover_path)
        data_size = len(secret_data)
        
        # For JPEG, use DCT
        if file_type == 'lossy_image':
            return 'dct'
        
        # For lossless images, analyze complexity
        if file_type == 'lossless_image':
            complexity = self._analyze_image_complexity(cover_path)
            logger.debug(f"Image complexity: {complexity:.2f}")
            
            # High complexity images can use PVD for higher capacity
            if complexity > 50 and data_size > 10000:
                return 'pvd'
            else:
                return 'lsb'
        
        # Default to LSB
        return 'lsb'
    
    def _analyze_image_complexity(self, image_path):
        """
        วิเคราะห์ความซับซ้อนของภาพ
        
        Args:
            image_path: path ของภาพ
        
        Returns:
            float: คะแนนความซับซ้อน (0-100)
        """
        try:
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                image = np.array(Image.open(image_path))
            
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Calculate edge density using Canny
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.sum(edges > 0) / edges.size * 100
            
            # Calculate texture complexity using Laplacian variance
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            texture_complexity = laplacian.var()
            
            # Normalize texture complexity to 0-100 scale
            texture_score = min(100, texture_complexity / 50)
            
            # Combined complexity score
            complexity = (edge_density * 0.6 + texture_score * 0.4)
            
            return complexity
            
        except Exception as e:
            logger.warning(f"Failed to analyze complexity: {e}")
            return 50  # Default medium complexity
    
    def _detect_embedding_method(self, stego_path):
        """
        พยายามตรวจจับวิธีการที่ใช้ซ่อนข้อมูล
        (ในกรณีที่ไม่รู้ว่าใช้วิธีใด)
        
        Args:
            stego_path: path ของไฟล์ที่มีข้อมูลซ่อนอยู่
        
        Returns:
            str: วิธีการที่คาดว่าใช้
        """
        file_type = self._detect_file_type(stego_path)
        
        # JPEG most likely uses DCT
        if file_type == 'lossy_image':
            return 'dct'
        
        # For lossless images, default to LSB
        # (In practice, would need more sophisticated detection)
        return 'lsb'
    
    def calculate_capacity(self, cover_path, method='auto'):
        """
        คำนวณความจุของไฟล์
        
        Args:
            cover_path: path ของไฟล์
            method: วิธีการ
        
        Returns:
            int: ความจุเป็น bytes
        """
        if method == 'auto' or method == 'adaptive':
            method = self._select_best_method(cover_path, b'')
        
        if method == 'lsb':
            return self.lsb.calculate_capacity(cover_path)
        elif method == 'pvd':
            from .pvd import PVDSteganography
            pvd = PVDSteganography()
            return pvd.calculate_capacity(cover_path)
        elif method == 'dct':
            from .jpeg_dct import JPEGDCTSteganography
            dct = JPEGDCTSteganography()
            return dct.calculate_capacity(cover_path)
        
        return 0
    
    def get_recommended_settings(self, cover_path, secret_data):
        """
        แนะนำการตั้งค่าที่เหมาะสม
        
        Args:
            cover_path: path ของไฟล์ต้นฉบับ
            secret_data: ข้อมูลที่จะซ่อน
        
        Returns:
            dict: การตั้งค่าที่แนะนำ
        """
        method = self._select_best_method(cover_path, secret_data)
        capacity = self.calculate_capacity(cover_path, method)
        complexity = self._analyze_image_complexity(cover_path)
        
        # Calculate embedding rate
        data_size = len(secret_data)
        embedding_rate = (data_size / capacity * 100) if capacity > 0 else 0
        
        # Determine risk level
        if embedding_rate < 30:
            risk_level = 'low'
            recommendation = 'ปลอดภัย - อัตราการฝังต่ำ'
        elif embedding_rate < 60:
            risk_level = 'medium'
            recommendation = 'ปานกลาง - ควรใช้ภาพที่มีความซับซ้อนสูง'
        else:
            risk_level = 'high'
            recommendation = 'เสี่ยงสูง - ควรใช้ไฟล์ขนาดใหญ่กว่า หรือบีบอัดข้อมูล'
        
        return {
            'method': method,
            'capacity': capacity,
            'data_size': data_size,
            'embedding_rate': embedding_rate,
            'complexity': complexity,
            'risk_level': risk_level,
            'recommendation': recommendation
        }