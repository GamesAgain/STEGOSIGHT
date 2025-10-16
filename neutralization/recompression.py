"""
File Re-compression Module
บีบอัดไฟล์ซ้ำเพื่อทำลายข้อมูลที่ซ่อนอยู่
"""

from PIL import Image
from pathlib import Path
from utils.logger import setup_logger, log_operation
from config import NEUTRALIZATION_SETTINGS

logger = setup_logger(__name__)


@log_operation("Recompress File")
def recompress_file(file_path, output_path=None, quality=None):
    """
    บีบอัดไฟล์ซ้ำ
    
    Args:
        file_path: path ของไฟล์ต้นฉบับ
        output_path: path สำหรับบันทึกไฟล์ผลลัพธ์
        quality: คุณภาพของการบีบอัด (1-100)
    
    Returns:
        str: path ของไฟล์ที่บีบอัดแล้ว
    """
    file_path = Path(file_path)
    
    if quality is None:
        quality = NEUTRALIZATION_SETTINGS['recompression']['jpeg_quality']
    
    try:
        # Load image
        image = Image.open(file_path)
        
        # Determine output path and format
        if output_path is None:
            # If PNG/BMP, convert to JPEG for lossy compression
            if file_path.suffix.lower() in ['.png', '.bmp']:
                output_path = file_path.parent / f"{file_path.stem}_recompressed.jpg"
            else:
                output_path = file_path.parent / f"{file_path.stem}_recompressed{file_path.suffix}"
        
        output_path = Path(output_path)
        
        # Convert RGBA to RGB if necessary (for JPEG)
        if image.mode == 'RGBA' and output_path.suffix.lower() in ['.jpg', '.jpeg']:
            # Create white background
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[3])  # Use alpha channel as mask
            image = rgb_image
        
        # Save with compression
        if output_path.suffix.lower() in ['.jpg', '.jpeg']:
            image.save(output_path, 'JPEG', quality=quality, optimize=True)
        elif output_path.suffix.lower() == '.png':
            png_compression = NEUTRALIZATION_SETTINGS['recompression']['png_compression']
            image.save(output_path, 'PNG', compress_level=png_compression, optimize=True)
        else:
            image.save(output_path, quality=quality, optimize=True)
        
        logger.info(f"File recompressed: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Failed to recompress file: {e}")
        raise


def convert_to_lossy(file_path, output_path=None, quality=85):
    """
    แปลงภาพ lossless เป็น lossy format
    
    Args:
        file_path: path ของไฟล์ต้นฉบับ
        output_path: path สำหรับบันทึกไฟล์ผลลัพธ์
        quality: คุณภาพของการบีบอัด
    
    Returns:
        str: path ของไฟล์ที่แปลงแล้ว
    """
    file_path = Path(file_path)
    
    try:
        image = Image.open(file_path)
        
        if output_path is None:
            output_path = file_path.parent / f"{file_path.stem}_lossy.jpg"
        
        # Convert to RGB if necessary
        if image.mode in ['RGBA', 'P', 'LA']:
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'RGBA':
                rgb_image.paste(image, mask=image.split()[3])
            else:
                rgb_image.paste(image)
            image = rgb_image
        
        image.save(output_path, 'JPEG', quality=quality, optimize=True)
        
        logger.info(f"Converted to lossy format: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Failed to convert to lossy: {e}")
        raise


def multiple_recompression(file_path, iterations=3, quality=90):
    """
    บีบอัดซ้ำหลายรอบ
    
    Args:
        file_path: path ของไฟล์ต้นฉบับ
        iterations: จำนวนรอบ
        quality: คุณภาพของการบีบอัด
    
    Returns:
        str: path ของไฟล์สุดท้าย
    """
    current_path = file_path
    
    for i in range(iterations):
        logger.debug(f"Recompression iteration {i+1}/{iterations}")
        temp_output = Path(file_path).parent / f"temp_recomp_{i}.jpg"
        current_path = recompress_file(current_path, temp_output, quality)
    
    # Final output
    final_output = Path(file_path).parent / f"{Path(file_path).stem}_multi_recompressed.jpg"
    Path(current_path).rename(final_output)
    
    # Clean up temp files
    for i in range(iterations - 1):
        temp_file = Path(file_path).parent / f"temp_recomp_{i}.jpg"
        if temp_file.exists():
            temp_file.unlink()
    
    logger.info(f"Multiple recompression complete: {final_output}")
    return str(final_output)