import threading
from queue import Queue, Full
import time
from enum import Enum
from abc import ABC

from cachetools import TTLCache

from prefab_pb2 import (
    ConfigEvaluationSummary,
    ConfigEvaluationSummaries,
    ConfigEvaluationCounter,
    TelemetryEvent,
    TelemetryEvents,
    ExampleContext as ProtoExampleContext,
    ExampleContexts,
)
from .context import Context
from .options import Options
from .config_resolver import Evaluation
from collections import defaultdict

from .context_shape_aggregator import ContextShapeAggregator
from ._internal_logging import InternalLogger

logger = InternalLogger(__name__)


def current_time_millis() -> int:
    return int(time.time() * 1000)


class BaseTelemetryEvent(ABC):
    class Type(Enum):
        EVAL = 1
        FLUSH = 2
        LOG = 3

    def __init__(self, event_type=Type.FLUSH, timestamp=None):
        self.event_type = event_type
        self.timestamp = timestamp if timestamp is not None else current_time_millis()


class FlushTelemetryEvent(BaseTelemetryEvent):
    def __init__(self):
        super().__init__(event_type=BaseTelemetryEvent.Type.FLUSH)
        self.processed_event = threading.Event()

    def block_until_consumed(self):
        self.processed_event.wait()

    def mark_finished(self):
        self.processed_event.set()


class EvaluationTelemetryEvent(BaseTelemetryEvent):
    def __init__(self, evaluation: Evaluation):
        super().__init__(event_type=BaseTelemetryEvent.Type.EVAL)
        self.evaluation = evaluation


class LogEvent(BaseTelemetryEvent):
    def __init__(self, path: str, level):
        super().__init__(event_type=BaseTelemetryEvent.Type.LOG)
        self.path = path
        self.level = level


class TelemetryManager(object):
    def __init__(self, client, options: Options) -> None:
        self.client = client
        self.report_interval = options.collect_sync_interval
        self.report_summaries = options.collect_evaluation_summaries
        self.collect_example_contexts = (
            options.context_upload_mode == Options.ContextUploadMode.PERIODIC_EXAMPLE
        )
        self.collect_context_shapes = (
            options.context_upload_mode != Options.ContextUploadMode.NONE
        )
        self.collect_logs = False  # Logging removed
        self.sync_started = False
        self.event_processor = TelemetryEventProcessor(
            base_client=self.client,
            evaluation_event_handler=self._handle_evaluation,
            flush_event_handler=self._handle_flush,
            log_event_handler=self._handle_log,
        )
        self.event_processor.start()
        self.timer = None
        self.evaluation_rollup = EvaluationRollup()
        self.example_contexts = ContextExampleAccumulator()
        self.context_shape_aggregator = ContextShapeAggregator(
            max_shapes=options.collect_max_shapes
        )
        self.listeners = []

    def start_periodic_sync(self) -> None:
        if self.report_interval:
            self.sync_started = True
            self.timer = threading.Timer(self.report_interval, self.run_sync)
            self.timer.daemon = True
            self.timer.start()

    def stop(self):
        self.sync_started = False

    def run_sync(self) -> None:
        try:
            self.flush()
        finally:
            if self.sync_started and not self.client.shutdown_flag.is_set():
                self.timer = threading.Timer(self.report_interval, self.run_sync)
                self.timer.daemon = True
                self.timer.start()

    def record_evaluation(self, evaluation: Evaluation) -> None:
        self.event_processor.enqueue(EvaluationTelemetryEvent(evaluation))

    def record_log(self, logger_name: str, severity) -> None:
        if self.collect_logs:
            self.event_processor.enqueue(LogEvent(logger_name, level=severity))

    def flush(self) -> FlushTelemetryEvent:
        flush_event = FlushTelemetryEvent()
        self.event_processor.enqueue(flush_event)
        return flush_event

    def flush_and_block(self):
        self.flush().block_until_consumed()

    def _handle_evaluation(self, evaluationEvent: EvaluationTelemetryEvent) -> None:
        if self.report_summaries:
            self.evaluation_rollup.record_evaluation(evaluationEvent.evaluation)
        if self.collect_example_contexts:
            self.example_contexts.add(evaluationEvent.evaluation.context)
        if self.collect_context_shapes:
            context = evaluationEvent.evaluation.context
            if isinstance(context, Context):
                self.context_shape_aggregator.push(context)
            elif not isinstance(context, str):
                self.context_shape_aggregator.push(Context(context))

    def _handle_flush(self, flush_event: FlushTelemetryEvent) -> None:
        try:
            telemetry_events = []
            if self.report_summaries:
                current_eval_rollup = self.evaluation_rollup
                eval_summaries = current_eval_rollup.build_telemetry()
                self.evaluation_rollup = EvaluationRollup()
                if len(eval_summaries.summaries) > 0:
                    telemetry_events.append(TelemetryEvent(summaries=eval_summaries))
            if self.collect_example_contexts:
                current_example_contexts = (
                    self.example_contexts.get_and_reset_contexts()
                )
                if current_example_contexts:
                    telemetry_events.append(
                        TelemetryEvent(
                            example_contexts=ExampleContexts(
                                examples=current_example_contexts
                            )
                        )
                    )
            if self.collect_context_shapes:
                shapes = self.context_shape_aggregator.flush()
                if shapes and len(shapes.shapes) > 0:
                    telemetry_events.append(TelemetryEvent(context_shapes=shapes))

            if self.collect_logs:
                loggers = self.log_path_aggregator.flush()
                if len(loggers.loggers) > 0:
                    telemetry_events.append(TelemetryEvent(loggers=loggers))
            if telemetry_events:
                # TODO retry/log
                self.client.post(
                    "/api/v1/telemetry/",
                    TelemetryEvents(events=telemetry_events),
                )
        finally:
            flush_event.mark_finished()

    def _handle_log(self, log_event: LogEvent) -> None:
        self.log_path_aggregator.push(log_event.path, log_event.level)


class HashableProtobufWrapper:
    def __init__(self, msg):
        self.msg = msg

    def __hash__(self):
        return hash(self.msg.SerializeToString())

    def __eq__(self, other):
        return self.msg.SerializeToString() == other.msg.SerializeToString()


class ContextExampleAccumulator(object):
    def __init__(self):
        self.recently_seen_contexts = set()
        self.fingerprint_cache = TTLCache(maxsize=1000, ttl=60 * 5)

    def size(self):
        return len(self.recently_seen_contexts)

    def add(self, context: Context) -> None:
        fingerprint = ContextExampleAccumulator.context_fingerprint(context)
        if fingerprint and fingerprint not in self.fingerprint_cache:
            self.fingerprint_cache[fingerprint] = fingerprint
            self.recently_seen_contexts.add(
                HashableProtobufWrapper(
                    ProtoExampleContext(
                        timestamp=current_time_millis(), contextSet=context.to_proto()
                    )
                )
            )

    def get_and_reset_contexts(self) -> [ProtoExampleContext]:
        contexts_to_return = [item.msg for item in self.recently_seen_contexts]
        self.recently_seen_contexts.clear()
        return contexts_to_return

    @staticmethod
    def context_fingerprint(context: Context) -> str:
        fingerprint_string = ""
        for name, named_context in sorted(context.contexts.items()):
            key = named_context.get("key")
            if key:
                fingerprint_string += f"{name}:{key}::"
        return fingerprint_string


class EvaluationRollup(object):
    def __init__(self):
        self.counts = defaultdict(lambda: 0)
        self.recorded_since = current_time_millis()

    def record_evaluation(self, evaluation: Evaluation) -> None:
        if evaluation.config:
            reportable_value = None
            try:
                reportable_value = HashableProtobufWrapper(
                    evaluation.deepest_value().reportable_wrapped_value().value
                )
            except Exception:
                pass
            self.counts[
                (
                    evaluation.config.key,
                    evaluation.config.config_type,
                    evaluation.config.id,
                    evaluation.config_row_index,
                    evaluation.value_index,
                    evaluation.deepest_value().weighted_value_index,
                    reportable_value,
                )
            ] += 1

    def build_telemetry(self):
        all_summaries = []
        key_groups = self._get_keys_grouped_by_key_and_type()
        for key_and_type, all_keys in key_groups.items():
            current_counters = []
            for current_key_tuple in all_keys:
                selected_value = None
                if current_key_tuple[6]:
                    selected_value = current_key_tuple[6].msg
                current_counters.append(
                    ConfigEvaluationCounter(
                        count=self.counts[current_key_tuple],
                        config_id=current_key_tuple[2],
                        config_row_index=current_key_tuple[3],
                        conditional_value_index=current_key_tuple[4],
                        weighted_value_index=current_key_tuple[5],
                        selected_value=selected_value,
                    )
                )
            all_summaries.append(
                ConfigEvaluationSummary(
                    key=key_and_type[0], type=key_and_type[1], counters=current_counters
                )
            )
        return ConfigEvaluationSummaries(
            start=self.recorded_since,
            end=current_time_millis(),
            summaries=all_summaries,
        )

    def _get_keys_grouped_by_key_and_type(self):
        grouped_keys = defaultdict(list)
        for key in self.counts.keys():
            grouped_keys[(key[0], key[1])].append(key)
        return grouped_keys


class TelemetryEventProcessor(object):
    class TelemetryThread(threading.Thread):
        def __init__(self, *args, **kwargs):
            self.base_client = kwargs.pop("base_client", None)
            super().__init__(*args, **kwargs)

        def run(self):
            try:
                super().run()
            except Exception as e:
                # Log just the exception name and message without the full traceback
                logger.warning(
                    f"Exception in thread {self.name}: {e.__class__.__name__}: {e}"
                )
                # Using warning level instead of error+traceback to keep logs cleaner

    def __init__(
        self,
        base_client=None,
        evaluation_event_handler=None,
        flush_event_handler=None,
        log_event_handler=None,
    ) -> None:
        self.base_client = base_client
        self.thread = None
        self.queue = Queue(10000)
        self.evaluation_event_handler = evaluation_event_handler
        self.flush_event_handler = flush_event_handler
        self.log_event_handler = log_event_handler

    def start(self) -> None:
        self.thread = TelemetryEventProcessor.TelemetryThread(
            target=self.process_queue,
            daemon=True,
            name="TelemetryEventProcessor",
            base_client=self.base_client,
        )
        self.thread.start()

    def enqueue(self, event: BaseTelemetryEvent):
        try:
            self.queue.put_nowait(event)
        except Full:
            pass

    def process_queue(self):
        while not self.base_client.shutdown_flag.is_set():
            event = self.queue.get()
            try:
                if (
                    event.event_type == BaseTelemetryEvent.Type.EVAL
                    and self.evaluation_event_handler
                ):
                    self.evaluation_event_handler(event)
                elif (
                    event.event_type == BaseTelemetryEvent.Type.FLUSH
                    and self.flush_event_handler
                ):
                    self.flush_event_handler(event)
                elif (
                    event.event_type == BaseTelemetryEvent.Type.LOG
                    and self.log_event_handler
                ):
                    self.log_event_handler(event)
                else:
                    raise ValueError(f"Unknown event type: {event.event_type}")

            finally:
                self.queue.task_done()
