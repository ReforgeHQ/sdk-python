"""
Example demonstrating dynamic log level control with structlog.

This example shows how to use the LoggerProcessor to dynamically control log levels
based on Reforge configuration. The log level can be changed in real-time through
the Reforge dashboard without restarting the application.
"""

import time
import os
import structlog
from sdk_reforge import ReforgeSDK, Options, LoggerProcessor


class CustomLoggerNameProcessor(LoggerProcessor):
    """
    Custom processor that extracts the logger name from the module field.

    This demonstrates how to customize the logger name lookup for more
    sophisticated log level rules based on module names.
    """

    def logger_name(self, logger, event_dict: dict) -> str:
        # Use the module name as the logger name for Reforge evaluation
        return event_dict.get("module") or "unknown"


def main():
    """
    Configure structlog with Reforge dynamic log level control.
    """
    # Configure structlog with our processor
    # Note: The LoggerProcessor must come after add_log_level
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,  # Must come before LoggerProcessor
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.THREAD_NAME,
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.PROCESS,
                    structlog.processors.CallsiteParameter.MODULE,
                }
            ),
            CustomLoggerNameProcessor().processor,  # Add Reforge log level control
            structlog.dev.ConsoleRenderer(pad_event=25),
        ]
    )

    logger = structlog.getLogger()

    # Configure SDK to run in local-only mode for this example
    # In production, you would set your REFORGE_SDK_KEY instead
    os.environ["REFORGE_DATASOURCES"] = "LOCAL_ONLY"

    def on_ready():
        """Called when SDK is ready"""
        logger.info("✓ SDK ready - log levels now controlled by Reforge")

    # Create SDK
    options = Options(
        x_datafile="test.datafile.json",  # In production, omit this for remote config
        on_ready_callback=on_ready,
        logger_key="log-levels.default",  # Config key that controls log levels
    )

    sdk = ReforgeSDK(options)

    logger.info("Starting structlog example")
    logger.info(
        "Try changing the 'log-levels.default' config in Reforge dashboard "
        "to see log output change dynamically!"
    )

    # Log messages at different levels in a loop
    try:
        for i in range(60):  # Run for 60 seconds
            # Get a config value to show SDK is working
            config_value = sdk.get("example-config", default="default-value")

            logger.debug(
                f"[{i}] Debug message",
                config_value=config_value,
                level_hint="Only visible when level is DEBUG",
            )
            logger.info(
                f"[{i}] Info message",
                config_value=config_value,
                level_hint="Visible when level is INFO or below",
            )
            logger.warning(
                f"[{i}] Warning message",
                config_value=config_value,
                level_hint="Visible when level is WARN or below",
            )
            logger.error(
                f"[{i}] Error message",
                config_value=config_value,
                level_hint="Visible when level is ERROR or below",
            )
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")

    sdk.close()


if __name__ == "__main__":
    main()
