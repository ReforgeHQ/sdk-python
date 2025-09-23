import threading
from collections import defaultdict

import requests
import responses

import prefab_pb2 as Prefab
from sdk_reforge.context import Context
from sdk_reforge.sdk import PostBodyType
from sdk_reforge.config_resolver import CriteriaEvaluator


class MockResolver:
    def __init__(self, config):
        self.config = config

    def raw(self, key):
        self.config.get(key)

    def get(self, key, context=Context({})):
        return CriteriaEvaluator(
            self.config.get(key), project_env_id=None, resolver=None, base_client=None
        ).evaluate(context)


class EmptyResolver:
    def __init__(self):
        pass

    def raw(self, key):
        return None

    def get(self, key, context=Context({})):
        return None


def sort_proto_evaluation_summaries(summaries):
    return sorted(summaries, key=lambda obj: (obj.key, obj.type))


def sort_proto_evaluation_counters(counters):
    return sorted(
        counters,
        key=lambda obj: (
            obj.config_id,
            obj.selected_index,
            obj.config_row_index,
            obj.conditional_value_index,
            obj.weighted_value_index,
            obj.selected_value.SerializeToString(),
        ),
    )


def proto_context_set_fingerprint(context_set: Prefab.ContextSet) -> str:
    fingerprint_string = ""
    for context in sorted(context_set.contexts, key=lambda obj: (obj.type)):
        key = context.values.get("key")
        if key:
            fingerprint_string += f"{context.type}:{key}::"
    return fingerprint_string


def sort_proto_context_sets(
    context_sets: [Prefab.ContextSet],
) -> [Prefab.ContextSet]:
    return sorted(
        context_sets,
        key=lambda obj: (proto_context_set_fingerprint(obj)),
    )


def sort_proto_context_shape(context_shapes: [Prefab.ContextShape]):
    return sorted(context_shapes, key=lambda obj: obj.name)


def sort_proto_loggers(loggers: [Prefab.Logger]):
    return sorted(loggers, key=lambda obj: obj.logger_name)


def get_telemetry_events_by_type(telemetry_event: Prefab.TelemetryEvents):
    values = defaultdict(list)
    for event in telemetry_event.events:
        payload_type = event.WhichOneof("payload")
        values[payload_type].append(getattr(event, payload_type))
    return values


class MockClientForPosts:
    def __init__(self):
        self.posts = []
        self.shutdown_flag = threading.Event()

    def reset(self):
        self.posts.clear()

    def post(self, path: str, body: PostBodyType) -> requests.models.Response:
        self.posts.append((path, body))
        return responses.Response(status=200, method="POST", headers=[], url="")
