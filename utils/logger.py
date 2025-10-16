"""
STEGOSIGHT Logger
ระบบจัดการ logging สำหรับแอปพลิเคชัน
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from config import LOGGING_SETTINGS


def setup_logger(name, level=None):
    """
    สร้างและตั้งค่า logger
    
    Args:
        name: ชื่อ logger (ปกติใช้ __name__)
        level: ระดับของ log (ถ้าไม่ระบุจะใช้จาก config)
    
    Returns:
        logging.Logger: Logger object
    """
    logger = logging.getLogger(name)

    # ป้องกันการเพิ่ม handler ซ้ำ
    if logger.handlers:
        return logger

    # กำหนดระดับ log
    if level is None:
        level = LOGGING_SETTINGS.get('level', 'INFO')
    logger.setLevel(getattr(logging, level))

    # สร้างโฟลเดอร์ logs ถ้ายังไม่มี
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    # Handler สำหรับไฟล์ (มีระบบหมุนเวียน log)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, level))

    # Handler สำหรับแสดงผลใน console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))

    # รูปแบบ log
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # ผูก handler เข้ากับ logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger  # ✅ สำคัญมาก! ต้องคืน logger กลับไป


def log_operation(logger, operation, status="SUCCESS", details=None):
    """
    ฟังก์ชันช่วยบันทึก log การดำเนินการแบบมาตรฐาน
    """
    msg = f"[{operation}] Status: {status}"
    if details:
        msg += f" | Details: {details}"

    if status.upper() == "FAILED":
        logger.error(msg)
    else:
        logger.info(msg)
