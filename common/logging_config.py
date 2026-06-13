import builtins
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ORIGINAL_PRINT = builtins.print


def setup_logging(name: str) -> logging.Logger:
    """標準出力とファイルへ同じ形式でログを出す。"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_to_file = os.getenv("LOG_TO_FILE", "true").strip().lower() in ("1", "true", "yes")
    max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "7"))

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        if log_to_file:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / f"{name}.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    _redirect_print_to_logger(logger)
    logger.info("ログ出力を初期化しました")
    return logger


def _redirect_print_to_logger(logger: logging.Logger) -> None:
    if getattr(builtins.print, "_is_logger_print", False):
        return

    def logger_print(*args: Any, sep: str = " ", end: str = "\n", file: Any = None, flush: bool = False) -> None:
        if file not in (None, sys.stdout, sys.stderr):
            _ORIGINAL_PRINT(*args, sep=sep, end=end, file=file, flush=flush)
            return

        message = sep.join(str(arg) for arg in args)
        if not message and end:
            return

        if file is sys.stderr:
            logger.error(message)
        else:
            logger.info(message)

        if flush:
            for handler in logger.handlers:
                handler.flush()

    logger_print._is_logger_print = True  # type: ignore[attr-defined]
    builtins.print = logger_print
