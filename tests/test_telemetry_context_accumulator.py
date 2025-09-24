import prefab_pb2 as Prefab

from sdk_reforge.context import Context
from sdk_reforge._telemetry import ContextExampleAccumulator


def test_fingerprint():
    assert (
        ContextExampleAccumulator.context_fingerprint(
            Context({"one": {"key": "hello1"}, "": {"b": "world"}})
        )
        == "one:hello1::"
    )
    assert (
        ContextExampleAccumulator.context_fingerprint(
            Context({"one": {"key": "hello1"}, "": {"b": "world", "key": 123}})
        )
        == ":123::one:hello1::"
    )
    assert (
        ContextExampleAccumulator.context_fingerprint(
            Context({"one": {"name": "hello1"}, "": {"b": "world"}})
        )
        == ""
    )


def test_accumulator_ignores_contexts_without_key():
    accumulator = ContextExampleAccumulator()
    assert len(accumulator.get_and_reset_contexts()) == 0
    accumulator.add(Context({"one": {"name": "hello1"}, "": {"b": "world"}}))
    assert accumulator.size() == 0
    assert len(accumulator.get_and_reset_contexts()) == 0


def test_accumulator_keeps_first_context_with_duplicate_fingerprint():
    accumulator = ContextExampleAccumulator()
    assert len(accumulator.get_and_reset_contexts()) == 0
    accumulator.add(Context({"one": {"key": "hello1", "age": 29}, "": {"b": "world"}}))
    assert accumulator.size() == 1
    accumulator.add(Context({"one": {"key": "hello1", "age": 30}, "": {"b": "world"}}))
    assert accumulator.size() == 1
    contexts = accumulator.get_and_reset_contexts()
    assert next(
        (
            context
            for context in contexts[0].contextSet.contexts
            if context.type == "one"
        )
    ).values.get("age") == Prefab.ConfigValue(int=29)
    assert len(contexts) == 1


def test_accumulator_accumulates():
    accumulator = ContextExampleAccumulator()
    assert len(accumulator.get_and_reset_contexts()) == 0
    accumulator.add(Context({"one": {"key": "hello1"}, "": {"b": "world"}}))
    assert accumulator.size() == 1
    accumulator.add(Context({"one": {"key": "hello2"}, "": {"b": "world"}}))
    assert accumulator.size() == 2
    contexts = accumulator.get_and_reset_contexts()
    assert len(contexts) == 2
    assert accumulator.size() == 0
