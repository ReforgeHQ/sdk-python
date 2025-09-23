import threading
import logging
from typing import Iterator

import prefab_pb2 as Prefab


LLV = Prefab.LogLevel.Value


python_log_level_name_to_prefab_log_levels = {
    "debug": LLV("DEBUG"),
    "info": LLV("INFO"),
    "warn": LLV("WARN"),
    "warning": LLV("WARN"),
    "error": LLV("ERROR"),
    "critical": LLV("FATAL"),
}

python_to_prefab_log_levels = {
    logging.NOTSET: LLV("DEBUG"),
    logging.DEBUG: LLV("DEBUG"),
    logging.INFO: LLV("INFO"),
    logging.WARN: LLV("WARN"),
    logging.ERROR: LLV("ERROR"),
    logging.CRITICAL: LLV("FATAL"),
}

prefab_to_python_log_levels = {
    LLV("TRACE"): logging.DEBUG,
    LLV("DEBUG"): logging.DEBUG,
    LLV("INFO"): logging.INFO,
    LLV("WARN"): logging.WARN,
    LLV("ERROR"): logging.ERROR,
    LLV("FATAL"): logging.CRITICAL,
}


def iterate_dotted_string(s: str) -> Iterator[str]:
    parts = s.split(".")
    for i in range(len(parts), 0, -1):
        yield ".".join(parts[:i])


class ReentrancyCheck:
    thread_local = threading.local()

    @staticmethod
    def set() -> None:
        ReentrancyCheck.thread_local.prefab_log_reentrant = True

    @staticmethod
    def is_set() -> bool:
        # Safely check if the thread-local variable is set and return True/False
        return getattr(ReentrancyCheck.thread_local, "prefab_log_reentrant", False)

    @staticmethod
    def clear() -> None:
        try:
            # Attempt to delete the variable
            delattr(ReentrancyCheck.thread_local, "prefab_log_reentrant")
        except AttributeError:
            # Variable was not set for this thread
            pass


class InternalLogger(logging.Logger):
    def __init__(self, name: str, level: int = logging.NOTSET) -> None:
        super().__init__(name, level)
        self.thread_local = threading.local()

    def log(self, level: int, msg, *args, **kwargs) -> None:
        if not ReentrancyCheck.is_set():
            extras = kwargs.pop("extra", {})
            extras["prefab_internal"] = True
            # Pass the possibly-modified 'extra' dictionary to the underlying logger
            super().log(level, msg, *args, extra=extras, **kwargs)
