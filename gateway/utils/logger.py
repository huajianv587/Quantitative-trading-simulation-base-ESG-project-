import logging
import os
import sys
import tempfile
import time
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
_SHARED_HANDLERS: list[logging.Handler] | None = None


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """Keep logging usable when another local process holds the log file."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rollover_blocked_until = 0.0

    def shouldRollover(self, record: logging.LogRecord) -> bool:  # noqa: N802 - logging API
        if time.time() < self._rollover_blocked_until:
            return False
        return super().shouldRollover(record)

    def doRollover(self) -> None:  # noqa: N802 - logging API
        try:
            super().doRollover()
        except PermissionError:
            self._rollover_blocked_until = time.time() + 60
        except OSError as exc:
            if getattr(exc, "winerror", None) == 32:
                self._rollover_blocked_until = time.time() + 60
                return
            raise


def _build_shared_handlers(formatter: logging.Formatter) -> list[logging.Handler]:
    global _SHARED_HANDLERS
    if _SHARED_HANDLERS is not None:
        return _SHARED_HANDLERS

    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(CONSOLE_LOG_LEVEL)
    console.setFormatter(formatter)
    handlers.append(console)

    try:
        app_file = WindowsSafeRotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=APP_LOG_MAX_BYTES,
            backupCount=APP_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        app_file.setLevel(APP_FILE_LOG_LEVEL)
        app_file.setFormatter(formatter)
        handlers.append(app_file)

        error_file = WindowsSafeRotatingFileHandler(
            LOG_DIR / "error.log",
            maxBytes=APP_LOG_MAX_BYTES,
            backupCount=APP_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        error_file.setLevel(ERROR_FILE_LOG_LEVEL)
        error_file.setFormatter(formatter)
        handlers.append(error_file)
    except OSError:
        pass

    _SHARED_HANDLERS = handlers
    return handlers


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.setLevel(min(CONSOLE_LOG_LEVEL, APP_FILE_LOG_LEVEL, ERROR_FILE_LOG_LEVEL))
    logger.propagate = False
    for handler in _build_shared_handlers(formatter):
        if handler not in logger.handlers:
            logger.addHandler(handler)

    return logger
