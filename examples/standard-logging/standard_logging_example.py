"""
Example demonstrating dynamic log level control with standard Python logging.

This example shows how to use the LoggerFilter to dynamically control log levels
based on Reforge configuration. The log level can be changed in real-time through
the Reforge dashboard without restarting the application.
"""

import logging
import sys
import time
import os

from sdk_reforge import ReforgeSDK, Options, LoggerFilter


def main():
    # Set up the root logger with a stdout handler
    root_logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    # Configure SDK to run in local-only mode for this example
    # In production, you would set your REFORGE_SDK_KEY instead
    os.environ["REFORGE_DATASOURCES"] = "LOCAL_ONLY"

    def configure_logger():
        """Add the Reforge LoggerFilter after SDK is ready"""
        handler.addFilter(LoggerFilter())
        print("✓ Logger filter configured - log levels now controlled by Reforge\n")

    # Create SDK with on_ready_callback to add the filter when ready
    options = Options(
        x_datafile="test.datafile.json",  # In production, omit this for remote config
        on_ready_callback=configure_logger,
        logger_key="log-levels.default",  # Config key that controls log levels
    )

    sdk = ReforgeSDK(options)

    # Create a test logger
    logger = logging.getLogger("reforge.python.example")

    print("Logging at all levels every second...")
    print("Try changing the 'log-levels.default' config in Reforge dashboard")
    print("to see log output change dynamically!\n")

    # Log messages at different levels in a loop
    try:
        for i in range(60):  # Run for 60 seconds
            logger.debug(f"[{i}] Debug message - only visible when level is DEBUG")
            logger.info(f"[{i}] Info message - visible when level is INFO or below")
            logger.warning(
                f"[{i}] Warning message - visible when level is WARN or below"
            )
            logger.error(f"[{i}] Error message - visible when level is ERROR or below")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")

    sdk.close()


if __name__ == "__main__":
    main()
