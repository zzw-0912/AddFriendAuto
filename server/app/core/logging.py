import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_LOGGER_NAME = "friendauto"


def configure_logging() -> None:
    logger = logging.getLogger(APP_LOGGER_NAME)
    if logger.handlers:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    log_dir = Path(os.getenv("FRIENDAUTO_LOG_DIR", "logs"))
    try:
      log_dir.mkdir(parents=True, exist_ok=True)
      file_handler = RotatingFileHandler(
          log_dir / "server.log",
          maxBytes=5 * 1024 * 1024,
          backupCount=5,
          encoding="utf-8",
      )
      file_handler.setFormatter(formatter)
      file_handler.setLevel(level)
      logger.addHandler(file_handler)
    except OSError:
        logger.exception("failed_to_initialize_file_logging log_dir=%s", log_dir.resolve())
