"""
STEGOSIGHT Logger
ระบบจัดการ logging สำหรับแอปพลิเคชัน
"""

import logging
import sys
from functools import wraps
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Callable

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
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # ผูก handler เข้ากับ logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger  # ✅ สำคัญมาก! ต้องคืน logger กลับไป


def log_operation(arg, operation=None, status="SUCCESS", details=None):
    """Decorator/utility สำหรับบันทึกสถานะการทำงาน.

    สามารถใช้ได้ 2 รูปแบบ:

    * เป็น decorator: ``@log_operation("My Task")``
    * เรียกตรงเพื่อ log: ``log_operation(logger, "My Task", status="FAILED")``
    """

    # Decorator usage (argument เป็นชื่อ operation)
    if operation is None and isinstance(arg, str):
        operation_name = arg

        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                logger = logging.getLogger(func.__module__)
                logger.info(f"[{operation_name}] Started")
                try:
                    result = func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.error(f"[{operation_name}] FAILED: {exc}", exc_info=True)
                    raise
                logger.info(f"[{operation_name}] Completed")
                return result

            return wrapper

        return decorator

    # Direct usage (argument แรกเป็น logger object)
    if operation is not None:
        logger = arg
        msg = f"[{operation}] Status: {status}"
        if details:
            msg += f" | Details: {details}"

        if status and status.upper() == "FAILED":
            logger.error(msg)
        else:
            logger.info(msg)
        return None

    raise TypeError(
        "log_operation ต้องใช้เป็น decorator พร้อมชื่อ operation หรือเรียกกับ logger และชื่อ operation"
    )
