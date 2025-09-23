import prefab_pb2 as Prefab
from sdk_reforge import Options
from sdk_reforge._telemetry import TelemetryManager
from sdk_reforge.config_resolver import Evaluation
from sdk_reforge.context import Context
import pytest

from tests.helpers import (
    EmptyResolver,
    sort_proto_evaluation_counters,
    MockClientForPosts,
    sort_proto_context_sets,
    sort_proto_context_shape,
    get_telemetry_events_by_type,
)

TIMEVAL = 1234567890.0
TIMEVAL2 = 1234567899.0
EMPTY_CONTEXT = Context()
EXAMPLE_CONTEXT1 = Context({"one": {"key": "hello1"}, "": {"b": "world"}})
EXAMPLE_CONTEXT2 = Context({"one": {"key": "hello2"}, "": {"b": "world"}})

EMPTY_RESOLVER = EmptyResolver()

CONFIG1 = Prefab.Config(key="key1", config_type="CONFIG", id=1001, rows=[])

CONFIG2 = Prefab.Config(key="key2", config_type="CONFIG", id=1002, rows=[])

VALUE1 = Prefab.ConfigValue(int=100)
VALUE2 = Prefab.ConfigValue(int=200)

mock_client = MockClientForPosts()


@pytest.fixture
def options() -> Options:
    options = Options(
        collect_evaluation_summaries=True,
        context_upload_mode=Options.ContextUploadMode.PERIODIC_EXAMPLE,
        collect_sync_interval=10,
        reforge_datasources="LOCAL_ONLY",
    )
    # Telemetry test with local only config
    return options


@pytest.fixture
def client(options):
    mock_client.reset()
    return mock_client


@pytest.fixture
def telemetry_manager(client, options: Options) -> TelemetryManager:
    telemetry_manager = TelemetryManager(client, options)
    yield telemetry_manager
    telemetry_manager.stop()


def test_telemetry(options: Options, telemetry_manager: TelemetryManager):
    telemetry_manager.record_evaluation(
        Evaluation(
            config=CONFIG1,
            value=VALUE1,
            value_index=31,
            config_row_index=0,
            resolver=EMPTY_RESOLVER,
            context=EXAMPLE_CONTEXT1,
        )
    )
    telemetry_manager.record_evaluation(
        Evaluation(
            config=CONFIG1,
            value=VALUE2,
            value_index=32,
            config_row_index=0,
            resolver=EMPTY_RESOLVER,
            context=EXAMPLE_CONTEXT2,
        )
    )
    telemetry_manager.flush_and_block()
    assert len(mock_client.posts) == 1

    post_url, uploaded_telemetry_proto = mock_client.posts[0]

    assert len(uploaded_telemetry_proto.events) == 3

    telemetry_events_by_type = get_telemetry_events_by_type(uploaded_telemetry_proto)

    assert {key: len(value) for key, value in telemetry_events_by_type.items()} == {
        "summaries": 1,
        "example_contexts": 1,
        "context_shapes": 1,
    }

    config_evaluation_summary = telemetry_events_by_type["summaries"][0]
    assert len(config_evaluation_summary.summaries) == 1
    assert config_evaluation_summary.summaries[0].key == CONFIG1.key

    assert sort_proto_evaluation_counters(
        config_evaluation_summary.summaries[0].counters
    ) == sort_proto_evaluation_counters(
        [
            Prefab.ConfigEvaluationCounter(
                count=1,
                config_id=CONFIG1.id,
                config_row_index=0,
                conditional_value_index=31,
                selected_value=VALUE1,
            ),
            Prefab.ConfigEvaluationCounter(
                count=1,
                config_id=CONFIG1.id,
                config_row_index=0,
                conditional_value_index=32,
                selected_value=VALUE2,
            ),
        ]
    )

    example_contexts = telemetry_events_by_type["example_contexts"][0]
    assert len(example_contexts.examples) == 2
    expected = sort_proto_context_sets(
        [
            Prefab.ContextSet(
                contexts=[
                    Prefab.Context(
                        type="one", values={"key": Prefab.ConfigValue(string="hello1")}
                    ),
                    Prefab.Context(
                        type="", values={"b": Prefab.ConfigValue(string="world")}
                    ),
                ]
            ),
            Prefab.ContextSet(
                contexts=[
                    Prefab.Context(
                        type="one", values={"key": Prefab.ConfigValue(string="hello2")}
                    ),
                    Prefab.Context(
                        type="", values={"b": Prefab.ConfigValue(string="world")}
                    ),
                ]
            ),
        ]
    )
    assert (
        sort_proto_context_sets([item.contextSet for item in example_contexts.examples])
        == expected
    )

    context_shapes_event = telemetry_events_by_type["context_shapes"][0]
    context_shapes = context_shapes_event.shapes
    assert len(context_shapes) == 2
    assert sort_proto_context_shape(context_shapes) == sort_proto_context_shape(
        [
            Prefab.ContextShape(name="one", field_types={"key": 2}),
            Prefab.ContextShape(name="", field_types={"b": 2}),
        ]
    )
