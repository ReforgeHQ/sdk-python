import logging
import os
import sys
import re
from contextlib import contextmanager
from typing import Any, Generator, Optional, Tuple

import pytest
import prefab_pb2 as Prefab

from sdk_reforge import ReforgeSDK, Options
from sdk_reforge.logging import LoggerFilter, LoggerProcessor


@contextmanager
def extended_env(new_env_vars: dict[str, str]) -> Generator[None, None, None]:
    old_env = os.environ.copy()
    os.environ.update(new_env_vars)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def assert_logged(
    cap: Any, level: str, msg: str, logger_name: str, should_log: bool = True
) -> None:
    """Check if a message was logged to stdout"""
    pattern = re.compile(f".*{logger_name or 'root'}.*{level}.*{msg}.*")
    stdout, stderr = cap.readouterr()
    if should_log:
        assert pattern.match(
            stdout
        ), f"Expected to find '{msg}' at level '{level}' in stdout"
    else:
        assert not pattern.match(
            stdout
        ), f"Did not expect to find '{msg}' at level '{level}' in stdout"


def configure_logger(
    logger_name: Optional[str] = None,
) -> Tuple[logging.Logger, logging.StreamHandler[Any]]:
    """Configure a logger with stdout handler"""
    logger = logging.getLogger(name=logger_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # Clear any existing handlers

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(ch)

    return (logger, ch)


@pytest.fixture
def sdk_with_log_config():  # type: ignore[no-untyped-def]
    """Create SDK with a log level config"""
    with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
        sdk = ReforgeSDK(
            Options(
                x_datafile="tests/test.datafile.json",
                logger_key="test.log.level",
                collect_sync_interval=None,
            )
        )

        # Create a log level config: INFO by default
        config = Prefab.Config(
            key="test.log.level",
            config_type=Prefab.ConfigType.Value("LOG_LEVEL_V2"),
            rows=[
                Prefab.ConfigRow(
                    values=[
                        Prefab.ConditionalValue(
                            value=Prefab.ConfigValue(
                                log_level=Prefab.LogLevel.Value("INFO")
                            )
                        )
                    ]
                )
            ],
        )

        sdk.config_sdk().config_resolver.local_store[config.key] = {"config": config}

        yield sdk
        sdk.close()


class TestLoggerFilter:
    def test_filter_allows_logs_at_or_above_configured_level(
        self, sdk_with_log_config: Any, capsys: Any
    ) -> None:
        """Test that LoggerFilter allows logs at or above the configured level"""
        (logger, ch) = configure_logger("test.logger")
        log_filter = LoggerFilter(sdk=sdk_with_log_config)
        ch.addFilter(log_filter)

        # DEBUG should be filtered (below INFO)
        logger.debug("Debug message")
        assert_logged(capsys, "DEBUG", "Debug message", "test.logger", should_log=False)

        # INFO should pass
        logger.info("Info message")
        assert_logged(capsys, "INFO", "Info message", "test.logger", should_log=True)

        # WARNING should pass
        logger.warning("Warning message")
        assert_logged(
            capsys, "WARNING", "Warning message", "test.logger", should_log=True
        )

        # ERROR should pass
        logger.error("Error message")
        assert_logged(capsys, "ERROR", "Error message", "test.logger", should_log=True)

    def test_filter_returns_true_when_sdk_not_available(self, capsys: Any) -> None:
        """Test that filter allows all logs when SDK is not available"""
        (logger, ch) = configure_logger("test.logger")
        log_filter = LoggerFilter(sdk=None)  # No SDK
        ch.addFilter(log_filter)

        # All levels should pass when SDK not available
        logger.debug("Debug message")
        assert_logged(capsys, "DEBUG", "Debug message", "test.logger", should_log=True)

        logger.info("Info message")
        assert_logged(capsys, "INFO", "Info message", "test.logger", should_log=True)

    def test_filter_uses_default_debug_when_config_not_found(self, capsys: Any) -> None:
        """Test that filter uses DEBUG level when config not found"""
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            sdk = ReforgeSDK(
                Options(
                    x_datafile="tests/test.datafile.json",
                    logger_key="nonexistent.key",
                    collect_sync_interval=None,
                )
            )

            (logger, ch) = configure_logger("test.logger")
            log_filter = LoggerFilter(sdk=sdk)
            ch.addFilter(log_filter)

            # With default DEBUG, all levels should pass
            logger.debug("Debug message")
            assert_logged(
                capsys, "DEBUG", "Debug message", "test.logger", should_log=True
            )

            logger.info("Info message")
            assert_logged(
                capsys, "INFO", "Info message", "test.logger", should_log=True
            )

            sdk.close()


class TestLoggerProcessor:
    def test_derive_structlog_numeric_level(self) -> None:
        """Test the _derive_structlog_numeric_level helper method"""
        # Test with level_number in dict (highest priority)
        assert (
            LoggerProcessor._derive_structlog_numeric_level(
                "warn", {"level_number": 30}
            )
            == 30
        )

        # Test with level string in dict
        assert (
            LoggerProcessor._derive_structlog_numeric_level(
                "warn", {"level": "warning"}
            )
            == 30
        )

        # Test with method_name
        assert LoggerProcessor._derive_structlog_numeric_level("warning", {}) == 30

        # Test warn alias
        assert LoggerProcessor._derive_structlog_numeric_level("warn", {}) == 30

        # Test debug
        assert LoggerProcessor._derive_structlog_numeric_level("debug", {}) == 10

        # Test info
        assert LoggerProcessor._derive_structlog_numeric_level("info", {}) == 20

        # Test error
        assert LoggerProcessor._derive_structlog_numeric_level("error", {}) == 40

        # Test exception alias (maps to error)
        assert LoggerProcessor._derive_structlog_numeric_level("exception", {}) == 40
