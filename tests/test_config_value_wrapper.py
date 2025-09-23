from sdk_reforge.config_value_wrapper import ConfigValueWrapper
import prefab_pb2 as Prefab


class TestConfigValueWrapper:
    def test_wrap_int(self):
        result = ConfigValueWrapper.wrap(42)
        assert type(result) == Prefab.ConfigValue
        assert result.int == 42

    def test_wrap_float(self):
        result = ConfigValueWrapper.wrap(3.14)
        assert type(result) == Prefab.ConfigValue
        assert result.double == 3.14

    def test_wrap_boolean_true(self):
        result = ConfigValueWrapper.wrap(True)
        assert type(result) == Prefab.ConfigValue
        assert result.bool is True

    def test_wrap_boolean_false(self):
        result = ConfigValueWrapper.wrap(False)
        assert type(result) == Prefab.ConfigValue
        assert result.bool is False

    def test_wrap_string_array(self):
        result = ConfigValueWrapper.wrap(["one", "two", "three"])
        assert type(result) == Prefab.ConfigValue
        assert result.string_list.values == ["one", "two", "three"]

    def test_wrap_other_array(self):
        result = ConfigValueWrapper.wrap([1, 3.4])
        assert type(result) == Prefab.ConfigValue
        assert result.string_list.values == ["1", "3.4"]

    def test_wrap_string(self):
        result = ConfigValueWrapper.wrap("hello")
        assert type(result) == Prefab.ConfigValue
        assert result.string == "hello"
