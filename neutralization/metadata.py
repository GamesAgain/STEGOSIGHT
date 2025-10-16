"""
Metadata Stripping Module
ลบข้อมูล metadata ออกจากไฟล์
"""

from PIL import Image
from pathlib import Path
from utils.logger import setup_logger, log_operation

logger = setup_logger(__name__)


@log_operation("Strip Metadata")
def strip_metadata(file_path, output_path=None):
    """
    ลบ metadata ออกจากไฟล์ภาพ
    
    Args:
        file_path: path ของไฟล์ต้นฉบับ
        output_path: path สำหรับบันทึกไฟล์ผลลัพธ์
    
    Returns:
        str: path ของไฟล์ที่ลบ metadata แล้ว
    """
    file_path = Path(file_path)
    
    try:
        # Load image
        image = Image.open(file_path)
        
        # Get image data without metadata
        data = list(image.getdata())
        
        # Create new image without metadata
        clean_image = Image.new(image.mode, image.size)
        clean_image.putdata(data)
        
        # Determine output path
        if output_path is None:
            output_path = file_path.parent / f"{file_path.stem}_clean{file_path.suffix}"
        
        # Save without EXIF and other metadata
        clean_image.save(output_path)
        
        logger.info(f"Metadata stripped: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Failed to strip metadata: {e}")
        raise


def get_metadata(file_path):
    """
    ดึงข้อมูล metadata จากไฟล์
    
    Args:
        file_path: path ของไฟล์
    
    Returns:
        dict: metadata information
    """
    try:
        image = Image.open(file_path)
        
        metadata = {
            'format': image.format,
            'mode': image.mode,
            'size': image.size,
        }
        
        # Get EXIF data if available
        exif_data = image.getexif()
        if exif_data:
            metadata['exif'] = dict(exif_data)
        
        # Get info
        if hasattr(image, 'info'):
            metadata['info'] = image.info
        
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to get metadata: {e}")
        return {}


def compare_metadata(original_path, stripped_path):
    """
    เปรียบเทียบ metadata ระหว่างไฟล์ต้นฉบับและไฟล์ที่ลบแล้ว
    
    Args:
        original_path: path ของไฟล์ต้นฉบับ
        stripped_path: path ของไฟล์ที่ลบ metadata
    
    Returns:
        dict: ผลการเปรียบเทียบ
    """
    original_meta = get_metadata(original_path)
    stripped_meta = get_metadata(stripped_path)
    
    return {
        'original': original_meta,
        'stripped': stripped_meta,
        'removed_fields': len(original_meta.get('exif', {}))
    }