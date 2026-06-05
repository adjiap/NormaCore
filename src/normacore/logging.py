"""Application-wide logging configuration."""

import logging
import sys
from pathlib import Path


def configure_logging(log_file: str | Path = "app.log", level: str = "INFO"):
    """
    Configure application-wide logging with file and console output.

    Sets up logging to write to both a file and stdout with consistent
    formatting. Creates log directory if it doesn't exist.

    Args:
        log_file: Path to log file. Can be string or Path object.
                 Parent directories are created automatically.
                 Defaults to "app.log" in current directory.
        level: Logging level as string. Valid values: "DEBUG", "INFO",
               "WARNING", "ERROR", "CRITICAL". Case-insensitive.
               Defaults to "INFO".

    Example:
        Add the configure line, at the top of the module to be logged, or
        as part of the `__main__`
        >>> configure_logging(Path("logs/extraction.log"), "DEBUG")
        >>> configure_logging(level="WARNING")  # Use default file

    Note:
        It uses force=True to reconfigure logging if already set up.

    Note:
        Log formatting: [LEVEL YYYY-MM-DD HH:MM:SS] module.function - message
    """
    # Create log directory if log_file is a Path and parent doesn't exist
    if isinstance(log_file, Path):
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file = str(log_file)  # Convert to string for FileHandler

    logging.basicConfig(
        format="[%(levelname)s %(asctime)s] %(name)s.%(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=getattr(logging, level.upper()),
        handlers=[
            logging.FileHandler(filename=log_file, mode="a", encoding="utf-8"),
            logging.StreamHandler(stream=sys.stdout),
        ],
        force=True,
    )
