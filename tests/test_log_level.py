import logging
import os
from contextlib import contextmanager
from sdk_reforge import ReforgeSDK, Options, LogLevel


@contextmanager
def extended_env(new_env_vars):  # type: ignore[no-untyped-def]
    old_env = os.environ.copy()
    os.environ.update(new_env_vars)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)


class TestLogLevel:
    def test_log_level_enum_values(self) -> None:
        """Test that LogLevel enum has correct Python logging values"""
        assert LogLevel.TRACE.python_level == logging.DEBUG
        assert LogLevel.DEBUG.python_level == logging.DEBUG
        assert LogLevel.INFO.python_level == logging.INFO
        assert LogLevel.WARN.python_level == logging.WARNING
        assert LogLevel.ERROR.python_level == logging.ERROR
        assert LogLevel.FATAL.python_level == logging.CRITICAL

    def test_get_log_level_returns_debug_when_not_found(self) -> None:
        """Test that get_log_level returns DEBUG when config not found"""
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            sdk = ReforgeSDK(
                Options(
                    x_datafile="tests/test.datafile.json",
                    logger_key="nonexistent.key",
                    collect_sync_interval=None,
                )
            )

            level = sdk.get_log_level("any.logger")
            assert level == LogLevel.DEBUG

    def test_logger_key_default_value(self) -> None:
        """Test that logger_key has the correct default value"""
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options()
            assert options.logger_key == "log-levels.default"
