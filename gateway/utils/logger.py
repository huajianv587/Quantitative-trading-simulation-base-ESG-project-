import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler
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


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_level(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip().upper()
    if not raw:
        return default
    return getattr(logging, raw, default)


CONSOLE_LOG_LEVEL = _env_level("LOG_LEVEL", logging.INFO)
APP_FILE_LOG_LEVEL = _env_level("APP_FILE_LOG_LEVEL", logging.DEBUG)
ERROR_FILE_LOG_LEVEL = _env_level("ERROR_FILE_LOG_LEVEL", logging.WARNING)
APP_LOG_MAX_BYTES = _env_int("APP_LOG_MAX_BYTES", 5 * 1024 * 1024)
APP_LOG_BACKUP_COUNT = _env_int("APP_LOG_BACKUP_COUNT", 5)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(min(CONSOLE_LOG_LEVEL, APP_FILE_LOG_LEVEL, ERROR_FILE_LOG_LEVEL))
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(CONSOLE_LOG_LEVEL)
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        app_file = RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=APP_LOG_MAX_BYTES,
            backupCount=APP_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        app_file.setLevel(APP_FILE_LOG_LEVEL)
        app_file.setFormatter(formatter)
        logger.addHandler(app_file)

        error_file = RotatingFileHandler(
            LOG_DIR / "error.log",
            maxBytes=APP_LOG_MAX_BYTES,
            backupCount=APP_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        error_file.setLevel(ERROR_FILE_LOG_LEVEL)
        error_file.setFormatter(formatter)
        logger.addHandler(error_file)
    except OSError:
        # Keep the application usable even when file logging is not writable.
        pass

    return logger
