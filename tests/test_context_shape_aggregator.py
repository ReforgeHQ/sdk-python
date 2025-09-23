from __future__ import annotations


from sdk_reforge.context import Context
import prefab_pb2 as Prefab
from datetime import date

from sdk_reforge.context_shape_aggregator import ContextShapeAggregator
from tests.helpers import sort_proto_context_shape

DOB = date.today()

CONTEXT_1 = Context(
    {
        "user": {"name": "user-name", "email": "user.email", "age": 42.5},
        "subscription": {"plan": "advanced", "free": False},
    }
)

CONTEXT_2 = Context(
    {
        "user": {"name": "other-user-name", "dob": DOB},
        "device": {"name": "device-name", "os": "os-name", "version": 3},
    }
)

CONTEXT_3 = Context({"subscription": {"plan": "pro", "trial": True}})


class TestContextShapeAggregator:
    def test_push_with_limit(self):
        aggregator = ContextShapeAggregator(max_shapes=9)
        aggregator.push(CONTEXT_1)
        assert aggregator.field_tuples == {
            ("user", "name", 2),
            ("user", "email", 2),
            ("user", "age", 4),
            ("subscription", "plan", 2),
            ("subscription", "free", 5),
        }

        aggregator.push(CONTEXT_2)

        assert aggregator.field_tuples == {
            ("user", "name", 2),
            ("user", "email", 2),
            ("user", "age", 4),
            ("subscription", "plan", 2),
            ("subscription", "free", 5),
            ("user", "dob", 2),
            ("device", "name", 2),
            ("device", "os", 2),
            ("device", "version", 1),
        }

        # we've reached the field limit so this will not change
        aggregator.push(CONTEXT_3)

        assert aggregator.field_tuples == {
            ("user", "name", 2),
            ("user", "email", 2),
            ("user", "age", 4),
            ("subscription", "plan", 2),
            ("subscription", "free", 5),
            ("user", "dob", 2),
            ("device", "name", 2),
            ("device", "os", 2),
            ("device", "version", 1),
        }

    def test_push(self):
        aggregator = ContextShapeAggregator()
        aggregator.push(CONTEXT_1)
        aggregator.push(CONTEXT_2)
        aggregator.push(CONTEXT_3)

        assert aggregator.field_tuples == {
            ("user", "name", 2),
            ("user", "email", 2),
            ("user", "age", 4),
            ("subscription", "plan", 2),
            ("subscription", "free", 5),
            ("user", "dob", 2),
            ("device", "name", 2),
            ("device", "os", 2),
            ("device", "version", 1),
            ("subscription", "trial", 5),
        }

    def test_prepare_data(self):
        aggregator = ContextShapeAggregator()
        assert aggregator.dirty is False
        aggregator.push(CONTEXT_1)
        assert aggregator.dirty is True

        aggregator.push(CONTEXT_2)
        aggregator.push(CONTEXT_3)

        assert sort_proto_context_shape(
            aggregator.flush().shapes
        ) == sort_proto_context_shape(
            [
                Prefab.ContextShape(
                    name="device",
                    field_types={"version": 1, "os": 2, "name": 2},
                ),
                Prefab.ContextShape(
                    name="subscription",
                    field_types={"plan": 2, "free": 5, "trial": 5},
                ),
                Prefab.ContextShape(
                    name="user",
                    field_types={"age": 4, "dob": 2, "email": 2, "name": 2},
                ),
            ],
        )
