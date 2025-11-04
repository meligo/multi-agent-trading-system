"""
Centralized Logging Configuration
Routes all logs to files instead of console for production use
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

# Create logs directory
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
LOG_FILES = {
    "scalping_engine": LOGS_DIR / "scalping_engine.log",
    "news_gating": LOGS_DIR / "news_gating.log",
    "datahub": LOGS_DIR / "datahub.log",
    "websocket": LOGS_DIR / "websocket.log",
    "databento": LOGS_DIR / "databento.log",
    "ig_client": LOGS_DIR / "ig_client.log",
    "insightsentry": LOGS_DIR / "insightsentry.log",
    "dashboard": LOGS_DIR / "dashboard.log",
    "main": LOGS_DIR / "main.log",
}


def setup_file_logging(
    logger_name: str,
    log_file: str = None,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console_output: bool = False
) -> logging.Logger:
    """
    Set up file-based logging with rotation.

    Args:
        logger_name: Name of the logger
        log_file: Path to log file (default: logs/{logger_name}.log)
        level: Logging level
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        console_output: Whether to also output to console (default: False)

    Returns:
        Configured logger
    """
    # Get or create logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Determine log file path
    if log_file is None:
        log_file = LOGS_DIR / f"{logger_name}.log"
    else:
        log_file = Path(log_file)

    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    # Add file handler
    logger.addHandler(file_handler)

    # Optionally add console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def setup_all_logging(console_output: bool = False):
    """
    Set up logging for all system components.

    Args:
        console_output: Whether to also output to console
    """
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Set up individual component loggers
    for component, log_file in LOG_FILES.items():
        setup_file_logging(
            logger_name=component,
            log_file=log_file,
            level=logging.INFO,
            console_output=console_output
        )

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websocket").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("trading_ig.streamer.manager").setLevel(logging.WARNING)  # Suppress "Waiting for ticker"
    logging.getLogger("trading_ig.lightstreamer").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    print(f"✅ Logging configured - logs directory: {LOGS_DIR}")


if __name__ == "__main__":
    # Test logging setup
    setup_all_logging(console_output=True)

    logger = logging.getLogger("test")
    logger.info("Test log message")
    print(f"Log files created in: {LOGS_DIR}")
