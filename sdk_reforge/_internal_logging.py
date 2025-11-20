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

        # Register this logger with the logging manager so it can participate
        # in the logger hierarchy and inherit handlers from parent loggers
        logging.Logger.manager.loggerDict[name] = self

        # Set up the parent logger in the hierarchy
        # This is adapted from logging.Logger.manager._fixupParents
        i = name.rfind(".")
        rv = None
        while (i > 0) and not rv:
            substr = name[:i]
            if substr not in logging.Logger.manager.loggerDict:
                logging.Logger.manager.loggerDict[substr] = logging.PlaceHolder(self)
            else:
                obj = logging.Logger.manager.loggerDict[substr]
                if isinstance(obj, logging.Logger):
                    rv = obj
                else:
                    # It's a PlaceHolder
                    obj.append(self)
            i = name.rfind(".", 0, i - 1)
        if not rv:
            rv = logging.root
        self.parent = rv

    def _log(
        self,
        level: int,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
    ) -> None:
        """
        Override _log to add prefab_internal to extra.
        This is called by info(), debug(), warning(), error(), etc.
        """
        if not ReentrancyCheck.is_set():
            if extra is None:
                extra = {}
            else:
                # Make a copy to avoid modifying the caller's dict
                extra = extra.copy()
            extra["prefab_internal"] = True

            super()._log(
                level,
                msg,
                args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
                stacklevel=stacklevel,
            )
