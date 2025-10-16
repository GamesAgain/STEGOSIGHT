"""
STEGOSIGHT Logger
ระบบจัดการ logging สำหรับแอปพลิเคชัน
"""

import logging
import sys
from functools import wraps
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
    log_file = log_dir / LOGGING_SETTINGS.get("log_file", "app.log")

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


def log_operation(logger_or_operation, operation=None, status="SUCCESS", details=None):
    """Utility to log operations or decorate functions.

    The helper can be used in two ways:

    1. Direct call mode::

        log_operation(logger, "Encrypt", status="SUCCESS")

    2. Decorator mode::

        @log_operation("Encrypt")
        def encrypt(...):
            ...

    Args:
        logger_or_operation: Logger instance or operation name when used as a decorator.
        operation: Operation name when called directly with a logger.
        status: Status string when called directly.
        details: Optional detail string when called directly.
    """

    # Decorator usage
    if operation is None and isinstance(logger_or_operation, str):
        op_name = logger_or_operation

        def decorator(func):
            module_logger = setup_logger(func.__module__)

            @wraps(func)
            def wrapper(*args, **kwargs):
                module_logger.info(f"[{op_name}] Status: STARTED")
                try:
                    result = func(*args, **kwargs)
                    module_logger.info(f"[{op_name}] Status: SUCCESS")
                    return result
                except Exception as exc:  # pragma: no cover - defensive logging path
                    module_logger.error(f"[{op_name}] Status: FAILED | Details: {exc}")
                    raise

            return wrapper

        return decorator

    # Direct call usage for backwards compatibility
    logger = logger_or_operation
    msg = f"[{operation}] Status: {status}"
    if details:
        msg += f" | Details: {details}"

    if status.upper() == "FAILED":
        logger.error(msg)
    else:
        logger.info(msg)
