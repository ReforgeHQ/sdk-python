from sdk_reforge.context_shape import ContextShape, MAPPING
import prefab_pb2 as Prefab


class Dummy(object):
    pass


class TestContextShape:
    def test_field_type_number(self):
        data = [
            [1, 1],
            [9999999999999999999, 1],
            [-9999999999999999999, 1],
            ["a", 2],
            ["michael", 2],
            [1.0, 4],
            [999999999999999999999.0, 4],
            [-999999999999999999999.0, 4],
            [True, 5],
            [False, 5],
            [[], 10],
            [[1, 2, 3], 10],
            [["a", "b", "c"], 10],
            [Dummy(), 2],
        ]

        for [v, t] in data:
            assert ContextShape.field_type_number(v) == t

    # If this test fails, it means that we've added a new type to the ConfigValue
    def test_mapping_is_exhaustive(self):
        unsupported = [
            "bytes",
            "limit_definition",
            "log_level",
            "weighted_values",
            "int_range",
            "provided",
            "confidential",
            "decrypt_with",
            "duration",
            "schema",
            "name",
            "description",
        ]

        supported = list(
            map(
                lambda x: x.number,
                filter(
                    lambda x: x.name not in unsupported,
                    list(Prefab.ConfigValue.DESCRIPTOR.fields),
                ),
            )
        )

        mapped = list(set(MAPPING.values()))

        assert (
            mapped == supported
        ), f"ContextShape MAPPING needs update: {mapped} != {supported}"
