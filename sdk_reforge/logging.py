"""
Logging integrations for Reforge SDK.

Provides filters and processors for standard logging and structlog that dynamically
adjust log levels based on Reforge configuration.
"""

import logging
from typing import Optional, Any

try:
    from structlog import DropEvent

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    DropEvent = None

import sdk_reforge
from sdk_reforge import ReforgeSDK


class BaseLoggerFilterProcessor:
    """Base class for logger filters/processors"""

    def __init__(self, sdk: Optional[ReforgeSDK] = None) -> None:
        self.sdk = sdk

    def _get_sdk(self) -> Optional[ReforgeSDK]:
        """Get SDK instance, either from constructor or singleton"""
        if self.sdk:
            return self.sdk
        try:
            return sdk_reforge.get_sdk()
        except Exception:
            return None

    def _should_log_message(
        self, sdk: ReforgeSDK, logger_name: str, called_method_level: int
    ) -> bool:
        """Check if message should be logged based on configured level"""
        log_level = sdk.get_log_level(logger_name)
        return called_method_level >= log_level.python_level


class LoggerFilter(BaseLoggerFilterProcessor, logging.Filter):
    """
    Filter for use with standard Python logging.

    This filter dynamically adjusts log levels based on Reforge configuration.
    Will get its SDK reference from sdk_reforge.get_sdk() unless overridden.

    Example usage:
        import logging
        from sdk_reforge.logging import LoggerFilter

        logger = logging.getLogger("my.app")
        logger.addFilter(LoggerFilter())
    """

    def __init__(self, sdk: Optional[ReforgeSDK] = None) -> None:
        super().__init__(sdk)

    def logger_name(self, record: logging.LogRecord) -> str:
        """
        Override this method to derive a different logger name from the record.

        Args:
            record: The log record

        Returns:
            str: The logger name to use for level lookup
        """
        return record.name

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Determine if the log record should be logged.

        Args:
            record: The log record to filter

        Returns:
            bool: True if the record should be logged, False otherwise
        """
        sdk = self._get_sdk()
        if sdk:
            logger_name = self.logger_name(record)
            if logger_name:
                return self._should_log_message(sdk, logger_name, record.levelno)
        return True


if STRUCTLOG_AVAILABLE:

    class LoggerProcessor(BaseLoggerFilterProcessor):
        """
        Processor for use with structlog.

        This processor dynamically adjusts log levels based on Reforge configuration.
        Will get its SDK reference from sdk_reforge.get_sdk() unless overridden.

        Example usage:
            import structlog
            from sdk_reforge.logging import LoggerProcessor

            structlog.configure(
                processors=[
                    structlog.stdlib.add_log_level,
                    LoggerProcessor().processor,
                    # ... other processors
                ]
            )
        """

        def __init__(self, sdk: Optional[ReforgeSDK] = None) -> None:
            super().__init__(sdk)

        def logger_name(self, logger: Any, event_dict: dict) -> Optional[str]:
            """
            Override this method to derive a different logger name.

            Args:
                logger: The structlog logger instance
                event_dict: The event dictionary

            Returns:
                Optional[str]: The logger name to use for level lookup
            """
            return getattr(logger, "name", None) or event_dict.get("logger")

        def processor(self, logger: Any, method_name: str, event_dict: dict) -> dict:
            """
            Process a structlog event, filtering based on configured log level.

            This method depends on structlog.stdlib.add_log_level being in the
            structlog pipeline first.

            Args:
                logger: The structlog logger instance
                method_name: The name of the method called (e.g., "info", "error")
                event_dict: The event dictionary

            Returns:
                dict: The event dictionary (if not filtered)

            Raises:
                DropEvent: If the log should be filtered
            """
            logger_name = self.logger_name(logger, event_dict)
            called_method_level = self._derive_structlog_numeric_level(
                method_name, event_dict
            )
            if not called_method_level:
                return event_dict
            if not logger_name:
                return event_dict

            sdk = self._get_sdk()
            if sdk:
                if not self._should_log_message(sdk, logger_name, called_method_level):
                    raise DropEvent
            return event_dict

        @staticmethod
        def _derive_structlog_numeric_level(
            method_name: str, event_dict: dict
        ) -> Optional[int]:
            """
            Derive the numeric log level from structlog event.

            Args:
                method_name: The method name called
                event_dict: The event dictionary

            Returns:
                Optional[int]: The numeric log level, or None if not determinable
            """
            # Check for numeric level added by level_to_number processor
            numeric_level_from_dict = event_dict.get("level_number")
            if type(numeric_level_from_dict) == int:
                return numeric_level_from_dict

            # Try to derive from level string or method name
            string_level = event_dict.get("level") or method_name

            # Remap levels per structlog conventions
            if string_level == "warn":
                string_level = "warning"
            elif string_level == "exception":
                string_level = "error"

            if string_level:
                maybe_numeric_level = logging.getLevelName(string_level.upper())
                if type(maybe_numeric_level) == int:
                    return maybe_numeric_level
            return None

else:
    # Structlog not available, create stub class
    class LoggerProcessor(BaseLoggerFilterProcessor):  # type: ignore
        """Stub class when structlog is not available"""

        def __init__(self, sdk: Optional[ReforgeSDK] = None) -> None:
            raise ImportError(
                "structlog is not installed. Install it with: pip install structlog"
            )
