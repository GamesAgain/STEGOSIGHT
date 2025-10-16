"""
Transformation & Denoising Module
แปลงรูปแบบและเพิ่มสัญญาณรบกวนเพื่อทำลายข้อมูลที่ซ่อนอยู่
"""

import numpy as np
from PIL import Image
import cv2
from pathlib import Path
from utils.logger import setup_logger, log_operation
from config import NEUTRALIZATION_SETTINGS

logger = setup_logger(__name__)


@log_operation("Apply Transformations")
def apply_transforms(file_path, output_path=None, methods=None):
    """
    ใช้การแปลงรูปแบบต่างๆ
    
    Args:
        file_path: path ของไฟล์ต้นฉบับ
        output_path: path สำหรับบันทึกไฟล์ผลลัพธ์
        methods: รายการวิธีการ ['resize', 'noise', 'blur', 'rotate']
    
    Returns:
        str: path ของไฟล์ที่แปลงแล้ว
    """
    if methods is None:
        methods = ['resize', 'noise']
    
    file_path = Path(file_path)
    
    try:
        # Load image
        image = np.array(Image.open(file_path))
        
        # Apply transformations
        if 'resize' in methods:
            image = slight_resize(image)
        
        if 'noise' in methods:
            image = add_noise(image)
        
        if 'blur' in methods:
            image = slight_blur(image)
        
        if 'rotate' in methods:
            image = slight_rotate(image)
        
        # Determine output path
        if output_path is None:
            output_path = file_path.parent / f"{file_path.stem}_transformed{file_path.suffix}"
        
        # Save
        result_image = Image.fromarray(image.astype('uint8'))
        result_image.save(output_path)
        
        logger.info(f"Transformations applied: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Failed to apply transformations: {e}")
        raise


def slight_resize(image, tolerance=None):
    """
    ปรับขนาดเล็กน้อย
    
    Args:
        image: numpy array ของภาพ
        tolerance: ความคลาดเคลื่อนที่อนุญาต (0.0-1.0)
    
    Returns:
        numpy array: ภาพที่ปรับขนาดแล้ว
    """
    if tolerance is None:
        tolerance = NEUTRALIZATION_SETTINGS['transform']['resize_tolerance']
    
    height, width = image.shape[:2]
    
    # Slightly resize (98-102% of original)
    scale = 1.0 + (np.random.random() * tolerance * 2 - tolerance)
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    # Resize
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    
    # Resize back to original size
    result = cv2.resize(resized, (width, height), interpolation=cv2.INTER_LINEAR)
    
    logger.debug(f"Resized with scale factor: {scale:.4f}")
    return result


def add_noise(image, level=None):
    """
    เพิ่มสัญญาณรบกวนเล็กน้อย
    
    Args:
        image: numpy array ของภาพ
        level: ระดับของสัญญาณรบกวน (0-10)
    
    Returns:
        numpy array: ภาพที่มีสัญญาณรบกวน
    """
    if level is None:
        level = NEUTRALIZATION_SETTINGS['transform']['noise_level']
    
    # Generate Gaussian noise
    noise = np.random.normal(0, level, image.shape)
    
    # Add noise
    noisy = image.astype(float) + noise
    
    # Clip values
    noisy = np.clip(noisy, 0, 255)
    
    logger.debug(f"Added noise with level: {level}")
    return noisy.astype('uint8')


def slight_blur(image, kernel_size=3):
    """
    เบลอเล็กน้อย
    
    Args:
        image: numpy array ของภาพ
        kernel_size: ขนาดของ kernel
    
    Returns:
        numpy array: ภาพที่เบลอแล้ว
    """
    blurred = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
    
    logger.debug(f"Applied Gaussian blur with kernel size: {kernel_size}")
    return blurred


def slight_rotate(image, max_angle=0.5):
    """
    หมุนเล็กน้อย
    
    Args:
        image: numpy array ของภาพ
        max_angle: มุมสูงสุด (degrees)
    
    Returns:
        numpy array: ภาพที่หมุนแล้ว
    """
    height, width = image.shape[:2]
    
    # Random angle
    angle = np.random.uniform(-max_angle, max_angle)
    
    # Rotation matrix
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Rotate
    rotated = cv2.warpAffine(image, matrix, (width, height))
    
    logger.debug(f"Rotated by {angle:.4f} degrees")
    return rotated


def jpeg_compression_attack(file_path, output_path=None, quality=85):
    """
    โจมตีด้วยการบีบอัด JPEG
    
    Args:
        file_path: path ของไฟล์ต้นฉบับ
        output_path: path สำหรับบันทึกไฟล์ผลลัพธ์
        quality: คุณภาพของการบีบอัด
    
    Returns:
        str: path ของไฟล์ที่โจมตีแล้ว
    """
    file_path = Path(file_path)
    
    if output_path is None:
        output_path = file_path.parent / f"{file_path.stem}_jpeg_attacked.jpg"
    
    image = Image.open(file_path)
    
    # Convert to RGB if necessary
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Save as JPEG
    image.save(output_path, 'JPEG', quality=quality)
    
    logger.info(f"JPEG compression attack applied: {output_path}")
    return str(output_path)


def median_filter(image, kernel_size=3):
    """
    ใช้ median filter
    
    Args:
        image: numpy array ของภาพ
        kernel_size: ขนาดของ kernel
    
    Returns:
        numpy array: ภาพที่กรองแล้ว
    """
    filtered = cv2.medianBlur(image, kernel_size)
    
    logger.debug(f"Applied median filter with kernel size: {kernel_size}")
    return filtered


def salt_and_pepper_noise(image, amount=0.005):
    """
    เพิ่ม salt and pepper noise
    
    Args:
        image: numpy array ของภาพ
        amount: ปริมาณของ noise (0.0-1.0)
    
    Returns:
        numpy array: ภาพที่มี noise
    """
    noisy = image.copy()
    
    # Salt noise
    num_salt = int(amount * image.size / 2)
    coords = [np.random.randint(0, i - 1, num_salt) for i in image.shape[:2]]
    noisy[coords[0], coords[1]] = 255
    
    # Pepper noise
    num_pepper = int(amount * image.size / 2)
    coords = [np.random.randint(0, i - 1, num_pepper) for i in image.shape[:2]]
    noisy[coords[0], coords[1]] = 0
    
    logger.debug(f"Added salt and pepper noise with amount: {amount}")
    return noisy