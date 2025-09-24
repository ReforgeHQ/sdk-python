import prefab_pb2 as Prefab
from sdk_reforge._telemetry import EvaluationRollup
from sdk_reforge.config_resolver import Evaluation
from unittest.mock import patch
from sdk_reforge.context import Context
import pytest

from tests.helpers import (
    EmptyResolver,
    sort_proto_evaluation_summaries,
    sort_proto_evaluation_counters,
)

TIMEVAL = 1234567890.0
TIMEVAL2 = 1234567899.0
EMPTY_CONTEXT = Context()
EMPTY_RESOLVER = EmptyResolver()

CONFIG1 = Prefab.Config(key="key1", config_type="CONFIG", id=1001, rows=[])

CONFIG2 = Prefab.Config(key="key2", config_type="CONFIG", id=1002, rows=[])

VALUE1 = Prefab.ConfigValue(int=100)
VALUE2 = Prefab.ConfigValue(int=200)

WVAL = Prefab.ConfigValue(
    weighted_values=Prefab.WeightedValues(
        weighted_values=[Prefab.WeightedValue(weight=1000, value=VALUE1)]
    )
)

CONFIDENTIAL_VALUE = Prefab.ConfigValue(string="don't pass it on", confidential=True)


@pytest.fixture
def mock_time():
    with patch("time.time") as mock_time:
        # Set the mock to return a specific value
        mock_time.return_value = TIMEVAL
        yield mock_time


def test_empty_rollup(mock_time):
    evaluation_rollup = EvaluationRollup()
    mock_time.return_value = TIMEVAL2
    telemetry = evaluation_rollup.build_telemetry()
    assert len(telemetry.summaries) == 0
    assert telemetry.start == int(TIMEVAL * 1000)
    assert telemetry.end == int(TIMEVAL2 * 1000)


def test_rollup_counts_properly(mock_time):
    evaluation_rollup = EvaluationRollup()
    evaluation_rollup.record_evaluation(
        Evaluation(
            config=CONFIG1,
            value=VALUE1,
            value_index=31,
            config_row_index=0,
            resolver=EMPTY_RESOLVER,
            context=EMPTY_CONTEXT,
        )
    )
    evaluation_rollup.record_evaluation(
        Evaluation(
            config=CONFIG1,
            value=VALUE2,
            value_index=32,
            config_row_index=0,
            resolver=EMPTY_RESOLVER,
            context=EMPTY_CONTEXT,
        )
    )
    evaluation_rollup.record_evaluation(
        Evaluation(
            config=CONFIG2,
            value=VALUE1,
            value_index=31,
            config_row_index=1,
            resolver=EMPTY_RESOLVER,
            context=EMPTY_CONTEXT,
        )
    )
    # do this one twice
    evaluation_rollup.record_evaluation(
        Evaluation(
            config=CONFIG2,
            value=VALUE2,
            value_index=32,
            config_row_index=1,
            resolver=EMPTY_RESOLVER,
            context=EMPTY_CONTEXT,
        )
    )
    evaluation_rollup.record_evaluation(
        Evaluation(
            config=CONFIG2,
            value=VALUE2,
            value_index=32,
            config_row_index=1,
            resolver=EMPTY_RESOLVER,
            context=EMPTY_CONTEXT,
        )
    )
    mock_time.return_value = TIMEVAL2
    telemetry = evaluation_rollup.build_telemetry()

    sorted_summaries = sort_proto_evaluation_summaries(telemetry.summaries)
    assert len(telemetry.summaries) == 2
    assert telemetry.start == int(TIMEVAL * 1000)
    assert telemetry.end == int(TIMEVAL2 * 1000)
    first_summary = sorted_summaries[0]
    assert len(first_summary.counters) == 2
    assert first_summary.key == CONFIG1.key
    assert first_summary.type == CONFIG1.config_type
    assert sort_proto_evaluation_counters(
        first_summary.counters
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

    second_summary = sorted_summaries[1]
    assert len(second_summary.counters) == 2
    assert second_summary.key == CONFIG2.key
    assert second_summary.type == CONFIG2.config_type
    assert sort_proto_evaluation_counters(
        second_summary.counters
    ) == sort_proto_evaluation_counters(
        [
            Prefab.ConfigEvaluationCounter(
                count=1,
                config_id=CONFIG2.id,
                config_row_index=1,
                conditional_value_index=31,
                selected_value=VALUE1,
            ),
            Prefab.ConfigEvaluationCounter(
                count=2,
                config_id=CONFIG2.id,
                config_row_index=1,
                conditional_value_index=32,
                selected_value=VALUE2,
            ),
        ]
    )


def test_rollup_works_for_weighted_value(mock_time):
    evaluation_rollup = EvaluationRollup()
    EMPTY_CONTEXT.get("foo")
    evaluation_rollup.record_evaluation(
        Evaluation(
            config=CONFIG1,
            value=WVAL,
            value_index=31,
            config_row_index=0,
            resolver=EMPTY_RESOLVER,
            context=EMPTY_CONTEXT,
        )
    )
    mock_time.return_value = TIMEVAL2
    telemetry = evaluation_rollup.build_telemetry()
    assert len(telemetry.summaries) == 1
    assert telemetry.summaries[0].counters == [
        Prefab.ConfigEvaluationCounter(
            count=1,
            config_id=CONFIG1.id,
            config_row_index=0,
            conditional_value_index=31,
            selected_value=VALUE1,
            weighted_value_index=0,
        )
    ]


def test_rollup_works_for_confidential(mock_time):
    evaluation_rollup = EvaluationRollup()
    evaluation_rollup.record_evaluation(
        Evaluation(
            config=CONFIG1,
            value=CONFIDENTIAL_VALUE,
            value_index=31,
            config_row_index=0,
            resolver=EMPTY_RESOLVER,
            context=EMPTY_CONTEXT,
        )
    )
    mock_time.return_value = TIMEVAL2
    telemetry = evaluation_rollup.build_telemetry()
    assert len(telemetry.summaries) == 1
    assert telemetry.summaries[0].counters == [
        Prefab.ConfigEvaluationCounter(
            count=1,
            config_id=CONFIG1.id,
            config_row_index=0,
            conditional_value_index=31,
            selected_value=Prefab.ConfigValue(string="*****e31d9"),
        )
    ]


def test_rollup_handles_none_value(mock_time):
    evaluation_rollup = EvaluationRollup()
    evaluation_rollup.record_evaluation(
        Evaluation(
            config=CONFIG1,
            value=None,
            value_index=31,
            config_row_index=0,
            resolver=EMPTY_RESOLVER,
            context=EMPTY_CONTEXT,
        )
    )
    mock_time.return_value = TIMEVAL2
    telemetry = evaluation_rollup.build_telemetry()
    assert len(telemetry.summaries) == 1
    assert telemetry.summaries[0].counters == [
        Prefab.ConfigEvaluationCounter(
            count=1,
            config_id=CONFIG1.id,
            config_row_index=0,
            conditional_value_index=31,
            selected_value=None,
        )
    ]
