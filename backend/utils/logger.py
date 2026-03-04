import logging
import sys
from config.settings import settings
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors and a newline before the message."""
    
    _DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    def format(self, record):
        level_color = Colors.RESET
        if record.levelno == logging.INFO:
            level_color = Colors.GREEN
        elif record.levelno == logging.WARNING:
            level_color = Colors.YELLOW
        elif record.levelno >= logging.ERROR:
            level_color = Colors.RED
        elif record.levelno == logging.DEBUG:
            level_color = Colors.BLUE

        timestamp = self.formatTime(record, self._DATE_FORMAT)
        level_name = record.levelname
        if level_name == "INFO": level_name = "SUCCESS" 
        
        header = f"{timestamp} | {level_color}{Colors.BOLD}{level_name:<8}{Colors.RESET} | {record.name}"
        message = f"| {record.getMessage()}"
        
        return f"{header} {message}"

def _build_handler() -> logging.StreamHandler:
    """Create a stdout handler with our custom colored format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter())
    return handler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_build_handler())
    numeric_level = getattr(logging, settings.log_level.upper(), logging.DEBUG)
    logger.setLevel(numeric_level)
    logger.propagate = False
    return logger

logger = get_logger("app")
