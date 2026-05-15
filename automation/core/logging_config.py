"""Centralized logging setup."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from automation.core.config import AutomationConfig


def configure_logging(config: AutomationConfig | None = None) -> logging.Logger:
    cfg = config or AutomationConfig()
    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("automation")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler = RotatingFileHandler(cfg.log_file, maxBytes=5_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
