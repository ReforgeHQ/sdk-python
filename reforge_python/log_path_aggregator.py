import logging
import time
from ._internal_logging import InternalLogger
from collections import defaultdict
import prefab_pb2 as Prefab

logger = InternalLogger(__name__)


class LogPathAggregator:
    def __init__(self, max_paths):
        self.max_paths = max_paths
        self.start_at = time.time()
        self.paths = defaultdict(int)

    def push(self, path, severity):
        if len(self.paths) >= self.max_paths:
            return

        self.paths[(path, severity)] += 1

    def flush(self):
        to_ship = self.paths.copy()
        self.paths = defaultdict(int)

        start_at_was = self.start_at
        self.start_at = time.time()

        logger.debug("flushing stats for %s paths" % len(to_ship))

        aggregate = defaultdict(lambda: Prefab.Logger())

        for (path, severity), count in to_ship.items():
            if (
                severity == logging.DEBUG
                or severity == Prefab.LogLevel.DEBUG
                or severity == "DEBUG"
            ):
                aggregate[path].debugs = count
            elif (
                severity == logging.INFO
                or severity == Prefab.LogLevel.INFO
                or severity == "INFO"
            ):
                aggregate[path].infos = count
            elif (
                severity == logging.WARNING
                or severity == Prefab.LogLevel.WARN
                or severity == "WARN"
            ):
                aggregate[path].warns = count
            elif (
                severity == logging.ERROR
                or severity == Prefab.LogLevel.ERROR
                or severity == "ERROR"
            ):
                aggregate[path].errors = count
            elif (
                severity == logging.CRITICAL
                or severity == Prefab.LogLevel.FATAL
                or severity == "FATAL"
            ):
                aggregate[path].fatals = count
            aggregate[path].logger_name = path
        loggers = Prefab.LoggersTelemetryEvent(
            loggers=aggregate.values(),
            start_at=round(start_at_was * 1000),
            end_at=round(time.time() * 1000),
        )
        return loggers
