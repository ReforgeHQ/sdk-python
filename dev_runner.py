#!/usr/bin/env python3
"""
Development runner to observe SDK behavior including SSE streaming and watchdog.

Usage:
    REFORGE_SDK_KEY=your-key python dev_runner.py

Or set a specific config key to watch:
    REFORGE_SDK_KEY=your-key python dev_runner.py my.config.key
"""

import logging
import sys
import time
import os

from sdk_reforge import ReforgeSDK, Options


def setup_logging() -> None:
    """Configure logging to show SDK internals."""
    root_logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root_logger.addHandler(handler)

    # Set root to DEBUG to see everything
    root_logger.setLevel(logging.DEBUG)

    # Quiet down noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def main() -> None:
    setup_logging()

    sdk_key = os.environ.get("REFORGE_SDK_KEY")
    if not sdk_key:
        print("Error: REFORGE_SDK_KEY environment variable not set")
        print("Usage: REFORGE_SDK_KEY=your-key python dev_runner.py [config.key]")
        sys.exit(1)

    # Optional: config key to watch
    watch_key = sys.argv[1] if len(sys.argv) > 1 else None

    print(f"Starting SDK with key: {sdk_key[:10]}...")
    print(f"Watching config key: {watch_key or '(none)'}")
    print("Press Ctrl+C to stop\n")
    print("=" * 60)

    options = Options(
        sdk_key=sdk_key,
        connection_timeout_seconds=10,
    )

    sdk = ReforgeSDK(options)
    config_sdk = sdk.config_sdk()

    print("=" * 60)
    print("SDK initialized, entering main loop...")
    print("=" * 60 + "\n")

    try:
        iteration = 0
        while True:
            iteration += 1

            status_parts = [
                f"[{iteration}]",
                f"initialized={config_sdk.is_ready()}",
                f"hwm={config_sdk.highwater_mark()}",
            ]

            if watch_key:
                try:
                    value = config_sdk.get(watch_key, default="<not found>")
                    status_parts.append(f"{watch_key}={value!r}")
                except Exception as e:
                    status_parts.append(f"{watch_key}=<error: {e}>")

            print(" | ".join(status_parts))
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\nShutting down...")

    sdk.close()
    print("Done.")


if __name__ == "__main__":
    main()
