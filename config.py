# -*- coding: utf-8 -*-
APP_NAME = "STEGOSIGHT"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "Stego & Anti-Stego Intelligent Guard"

# GUI theming + sizing
GUI_SETTINGS = {
    "window": {
        "title": f"{APP_NAME}: Stego & Anti-Stego Intelligent Guard",
        "width": 1000,
        "height": 720,
        "min_width": 900,
        "min_height": 640,
    },
    "theme": {
        "primary_color": "#1E88E5",
        "background_color": "#FAFAFA",
    }
}

SUPPORTED_IMAGE_FORMATS = [".png", ".bmp", ".jpg", ".jpeg"]

# Logging
LOGGING_SETTINGS = {
    "level": "INFO",           # DEBUG/INFO/WARNING/ERROR
    "log_dir": "logs",
    "log_file": "stegosight.log",
    "max_bytes": 2 * 1024 * 1024,
    "backup_count": 3,
}

# Crypto defaults
CRYPTO_SETTINGS = {
    "salt_bytes": 16,
    "argon2id": {              # OWASP / RFC 9106 guidance (ปรับตามเครื่องได้)
        "time_cost": 3,
        "memory_cost": 64 * 1024,  # KiB
        "parallelism": 2,
        "key_len": 32
    },
    "pbkdf2": {                # fallback ถ้าไม่มี argon2-cffi
        "iterations": 300_000,
        "key_len": 32
    }
}

# Steganalysis
ANALYSIS_SETTINGS = {
    "weights": {"chi_square": 0.4, "ela": 0.3, "histogram": 0.3},
    "risk_thresholds": {"low": 25, "medium": 50, "high": 75}
}
