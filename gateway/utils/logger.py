import logging
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
configured_log_dir = os.getenv("APP_LOG_DIR", "").strip()
LOG_DIR = Path(configured_log_dir) if configured_log_dir else PROJECT_ROOT / "storage" / "logs"
if not LOG_DIR.is_absolute():
    LOG_DIR = PROJECT_ROOT / LOG_DIR
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    LOG_DIR = Path(tempfile.gettempdir()) / "quant-esg-logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        app_file = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
        app_file.setLevel(logging.DEBUG)
        app_file.setFormatter(formatter)
        logger.addHandler(app_file)

        error_file = logging.FileHandler(LOG_DIR / "error.log", encoding="utf-8")
        error_file.setLevel(logging.WARNING)
        error_file.setFormatter(formatter)
        logger.addHandler(error_file)
    except OSError:
        # Keep the application usable even when file logging is not writable.
        pass

    return logger
