# Hệ thống logging
# src/utils/logger.py
import os
import logging
from datetime import datetime
from .config import LOGS_FOLDER, LOG_LEVEL
from .artifact_paths import build_log_filename

os.makedirs(LOGS_FOLDER, exist_ok=True)

def get_log_filename():
    return build_log_filename()

def _resolve_level(level_value):
    if isinstance(level_value, int):
        return level_value
    if isinstance(level_value, str):
        return getattr(logging, level_value.upper(), logging.INFO)
    return logging.INFO

def setup_logger(name, level=None):
    logger = logging.getLogger(name)
    logger.setLevel(_resolve_level(level if level is not None else LOG_LEVEL))
    logger.propagate = False
    if not logger.handlers:
        log_file = os.path.join(LOGS_FOLDER, get_log_filename())
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(console_handler)
    return logger

default_logger = setup_logger("zalo_crawler")


def log(message, level=logging.INFO, logger=default_logger):
    logger.log(level, message)
