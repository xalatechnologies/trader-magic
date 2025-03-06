import sys
import os
from loguru import logger

# Configure loguru logger
log_level = os.getenv("LOG_LEVEL", "INFO")
log_to_console = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
service_name = os.getenv("SERVICE_NAME", "unknown")

# Format for console output (colorized, detailed)
console_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[name]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

# Format for docker logs (structured, syslog-compatible)
syslog_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[name]} | {message}"

# Remove default logger
logger.remove()

# Add console logger if enabled
if log_to_console:
    logger.add(
        sys.stderr,
        format=console_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

# Add structured logger to stderr for Docker to capture
logger.add(
    sys.stdout,
    format=syslog_format,
    level=log_level,
    backtrace=False,
    diagnose=False,
)

def get_logger(name):
    """
    Returns a logger instance with the given name, prefixed with the service name.
    """
    prefixed_name = f"{service_name}.{name}" if service_name != "unknown" else name
    return logger.bind(name=prefixed_name)