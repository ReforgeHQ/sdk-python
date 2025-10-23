"""Log level enum for Reforge SDK"""

from enum import Enum
import logging


class LogLevel(Enum):
    """Log levels supported by Reforge SDK"""

    TRACE = logging.DEBUG  # Python doesn't have TRACE, map to DEBUG
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARN = logging.WARNING
    ERROR = logging.ERROR
    FATAL = logging.CRITICAL

    @property
    def python_level(self) -> int:
        """Get the Python logging level for this log level"""
        return self.value

    def __int__(self) -> int:
        """Convert to integer (Python logging level)"""
        return self.value
