import sys
import logging
from typing import Optional

def setup_logger(name: str, level: int = logging.INFO, log_format: Optional[str] = None, log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up and configure a logger.

    Args:
        name: Name of the logger
        level: Logging level (default: INFO)
        log_format: Custom log format string (optional)
        log_file: Path to log file (optional, logs to console if not provided)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Default format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Name of the logger

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Default logger for the module
logger = setup_logger(__name__)