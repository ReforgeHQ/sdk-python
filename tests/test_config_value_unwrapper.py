from sdk_reforge import Options, ReforgeSDK as Client
from sdk_reforge.config_resolver import Evaluation
from sdk_reforge.config_value_unwrapper import (
    ConfigValueUnwrapper,
    EnvVarParseException,
    MissingEnvVarException,
)
from sdk_reforge.encryption import Encryption
import prefab_pb2 as Prefab
from sdk_reforge.context import Context
import os
import pytest
from contextlib import contextmanager

CONFIG = Prefab.Config(key="config_key")
EMPTY_CONTEXT = Context()
DECRYPTION_KEY_NAME = "decryption.key"
DECRYPTION_KEY_VALUE = Encryption.generate_new_hex_key()

VTV = Prefab.Config.ValueType.Value


class MockResolver:
    def __init__(self, client):
        self.base_client = client

    def get(self, key):
        if key == DECRYPTION_KEY_NAME:
            return Evaluation(
                config=Prefab.Config(key=DECRYPTION_KEY_NAME),
                value=Prefab.ConfigValue(string=DECRYPTION_KEY_VALUE),
                context=EMPTY_CONTEXT,
                value_index=0,
                config_row_index=0,
                resolver=self,
            )
        else:
            raise Exception("unexpected key")


def client():
    options = Options(
        x_datafile="tests/prefab.datafile.json",
        reforge_datasources="LOCAL_ONLY",
        collect_sync_interval=None,
    )
    return Client(options)


def config_of(value_type):
    return Prefab.Config(key="config-key", value_type=VTV(value_type))


@contextmanager
def extended_env(new_env_vars):
    old_env = os.environ.copy()
    os.environ.update(new_env_vars)
    yield
    os.environ.clear()
    os.environ.update(old_env)


class TestConfigValueUnwrapper:
    def test_unwrapping_int(self):
        config_value = Prefab.ConfigValue(int=123)
        assert (
            TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT) == 123
        )
        assert (
            TestConfigValueUnwrapper.reportable_value(
                config_value, CONFIG, EMPTY_CONTEXT
            )
            == 123
        )

    def test_unwrapping_string(self):
        config_value = Prefab.ConfigValue(string="abc")
        assert (
            TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT)
            == "abc"
        )
        assert (
            TestConfigValueUnwrapper.reportable_value(
                config_value, CONFIG, EMPTY_CONTEXT
            )
            == "abc"
        )

    def test_unwrapping_double(self):
        config_value = Prefab.ConfigValue(double=5.22)
        assert (
            TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT) == 5.22
        )
        assert (
            TestConfigValueUnwrapper.reportable_value(
                config_value, CONFIG, EMPTY_CONTEXT
            )
            == 5.22
        )

    def test_unwrapping_bool(self):
        config_value = Prefab.ConfigValue(bool=True)
        assert TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT)
        assert TestConfigValueUnwrapper.reportable_value(
            config_value, CONFIG, EMPTY_CONTEXT
        )

        config_value = Prefab.ConfigValue(bool=False)
        assert not TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT)
        assert not TestConfigValueUnwrapper.reportable_value(
            config_value, CONFIG, EMPTY_CONTEXT
        )

    def test_unwrapping_log_level(self):
        config_value = Prefab.ConfigValue(log_level="INFO")
        assert TestConfigValueUnwrapper.unwrap(
            config_value, CONFIG, EMPTY_CONTEXT
        ), Prefab.LogLevel.keys().index("INFO")

    def test_unwrapping_string_list(self):
        string_list = ["a", "b", "c"]
        config_value = Prefab.ConfigValue(
            string_list=Prefab.StringList(values=string_list)
        )
        unwrapped_value = TestConfigValueUnwrapper.unwrap(
            config_value, CONFIG, EMPTY_CONTEXT
        )

        # Check if unwrapped_value is a list
        assert isinstance(unwrapped_value, list), "unwrapped_value should be a list"

        # Check if unwrapped_value matches the original string_list
        assert (
            unwrapped_value == string_list
        ), "unwrapped_value should match the original string_list"

        reportable_value = TestConfigValueUnwrapper.reportable_value(
            config_value, CONFIG, EMPTY_CONTEXT
        )

        # Check if reportable_value is a list
        assert isinstance(reportable_value, list), "reportable_value should be a list"

        # Check if reportable_value matches the original string_list
        assert (
            reportable_value == string_list
        ), "reportable_value should match the original string_list"

    def test_unwrapping_weighted_values(self):
        weighted_values = self.build_weighted_values({"abc": 1})
        config_value = Prefab.ConfigValue(weighted_values=weighted_values)
        assert (
            TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT)
            == "abc"
        )
        assert (
            TestConfigValueUnwrapper.reportable_value(
                config_value, CONFIG, EMPTY_CONTEXT
            )
            == "abc"
        )

        weighted_values = self.build_weighted_values({"abc": 1, "def": 1, "ghi": 1})
        config_value = Prefab.ConfigValue(weighted_values=weighted_values)
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:123")
            )
            == "ghi"
        )
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:456")
            )
            == "ghi"
        )
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:789")
            )
            == "abc"
        )
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:012")
            )
            == "def"
        )

        weighted_values = self.build_weighted_values({"abc": 1, "def": 99, "ghi": 1})
        config_value = Prefab.ConfigValue(weighted_values=weighted_values)
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:123")
            )
            == "def"
        )
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:456")
            )
            == "def"
        )
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:789")
            )
            == "def"
        )
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:012")
            )
            == "def"
        )
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:103")
            )
            == "ghi"
        )
        assert (
            TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, self.context_with_key("user:119")
            )
            == "abc"
        )

    def test_unwrapping_provided_values(self):
        with extended_env({"ENV_VAR_NAME": "unit test value"}):
            value = Prefab.Provided(source="ENV_VAR", lookup="ENV_VAR_NAME")
            config_value = Prefab.ConfigValue(provided=value)
            assert (
                TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT)
                == "unit test value"
            )
            assert (
                TestConfigValueUnwrapper.reportable_value(
                    config_value, CONFIG, EMPTY_CONTEXT
                )
                == "unit test value"
            )

    def test_unwrapping_provided_values_coerces_to_int(self):
        with extended_env({"ENV_VAR_NAME": "42"}):
            value = Prefab.Provided(source="ENV_VAR", lookup="ENV_VAR_NAME")
            config_value = Prefab.ConfigValue(provided=value)
            assert (
                TestConfigValueUnwrapper.unwrap(
                    config_value, config_of("INT"), EMPTY_CONTEXT
                )
                == 42
            )

    def test_unwrapping_provided_values_of_type_string_list(self):
        with extended_env({"ENV_VAR_NAME": '["bob","cary"]'}):
            value = Prefab.Provided(source="ENV_VAR", lookup="ENV_VAR_NAME")
            config_value = Prefab.ConfigValue(provided=value)
            assert TestConfigValueUnwrapper.unwrap(
                config_value, CONFIG, EMPTY_CONTEXT
            ) == ["bob", "cary"]

    def test_unwrapping_provided_values_when_value_type_mismatch(self):
        with extended_env({"ENV_VAR_NAME": "not an int"}):
            value = Prefab.Provided(source="ENV_VAR", lookup="ENV_VAR_NAME")
            config_value = Prefab.ConfigValue(provided=value)
            with pytest.raises(EnvVarParseException):
                assert (
                    TestConfigValueUnwrapper.unwrap(
                        config_value, config_of("INT"), EMPTY_CONTEXT
                    )
                    == 42
                )

    def test_unwrapping_provided_values_with_missing_env_var(self):
        value = Prefab.Provided(source="ENV_VAR", lookup="NON_EXISTENT_ENV_VAR_NAME")
        config_value = Prefab.ConfigValue(provided=value)
        with pytest.raises(MissingEnvVarException):
            TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT)

    def test_unwrapping_encrypted_values_decrypts(self):
        clear_text = "very secret stuff"
        encrypted = Encryption(DECRYPTION_KEY_VALUE).encrypt(clear_text)
        config_value = Prefab.ConfigValue(
            string=encrypted, decrypt_with=DECRYPTION_KEY_NAME
        )
        assert (
            TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT)
            == clear_text
        )
        assert (
            TestConfigValueUnwrapper.reportable_value(
                config_value, CONFIG, EMPTY_CONTEXT
            )
            == "*****27151"
        )

    def test_unwrapping_json(self):
        config_value = Prefab.ConfigValue(json=Prefab.Json(json='{"hello": "world"}'))
        assert TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT) == {
            "hello": "world"
        }
        assert TestConfigValueUnwrapper.reportable_value(
            config_value, CONFIG, EMPTY_CONTEXT
        ) == {"hello": "world"}

    def test_reportable_value_for_confidential(self):
        clear_text = "kind of secret stuff"
        config_value = Prefab.ConfigValue(string=clear_text, confidential=True)
        assert (
            TestConfigValueUnwrapper.unwrap(config_value, CONFIG, EMPTY_CONTEXT)
            == clear_text
        )
        assert (
            TestConfigValueUnwrapper.reportable_value(
                config_value, CONFIG, EMPTY_CONTEXT
            )
            == "*****a0e4d"
        )

    def test_coerce(self):
        assert (
            ConfigValueUnwrapper.coerce_into_type("string", CONFIG, "ENV") == "string"
        )
        assert ConfigValueUnwrapper.coerce_into_type("42", CONFIG, "ENV") == 42
        assert ConfigValueUnwrapper.coerce_into_type("false", CONFIG, "ENV") is False
        assert ConfigValueUnwrapper.coerce_into_type("False", CONFIG, "ENV") is False
        assert ConfigValueUnwrapper.coerce_into_type("true", CONFIG, "ENV") is True
        assert ConfigValueUnwrapper.coerce_into_type("True", CONFIG, "ENV") is True
        assert ConfigValueUnwrapper.coerce_into_type("42.42", CONFIG, "ENV") == 42.42
        assert ConfigValueUnwrapper.coerce_into_type("['a','b']", CONFIG, "ENV") == [
            "a",
            "b",
        ]

        assert (
            ConfigValueUnwrapper.coerce_into_type("string", config_of("STRING"), "ENV")
            == "string"
        )
        assert (
            ConfigValueUnwrapper.coerce_into_type("42", config_of("STRING"), "ENV")
            == "42"
        )
        assert (
            ConfigValueUnwrapper.coerce_into_type("42.42", config_of("STRING"), "ENV")
            == "42.42"
        )

        assert (
            ConfigValueUnwrapper.coerce_into_type("42", config_of("INT"), "ENV") == 42
        )

        assert (
            ConfigValueUnwrapper.coerce_into_type("false", config_of("BOOL"), "ENV")
            is False
        )

        assert (
            ConfigValueUnwrapper.coerce_into_type("42.42", config_of("DOUBLE"), "ENV")
            == 42.42
        )

        assert ConfigValueUnwrapper.coerce_into_type(
            "['a','b']", config_of("STRING_LIST"), "ENV"
        ) == ["a", "b"]

        with pytest.raises(EnvVarParseException):
            ConfigValueUnwrapper.coerce_into_type("not an int", config_of("INT"), "ENV")

        with pytest.raises(EnvVarParseException):
            ConfigValueUnwrapper.coerce_into_type(
                "not a bool", config_of("BOOL"), "ENV"
            )

        with pytest.raises(EnvVarParseException):
            ConfigValueUnwrapper.coerce_into_type(
                "not a double", config_of("DOUBLE"), "ENV"
            )

        with pytest.raises(EnvVarParseException):
            ConfigValueUnwrapper.coerce_into_type(
                "not a list", config_of("STRING_LIST"), "ENV"
            )

    @staticmethod
    def unwrap(config_value, config, context):
        return ConfigValueUnwrapper.deepest_value(
            config_value, config, MockResolver(client()), context
        ).unwrap()

    @staticmethod
    def reportable_value(config_value, config, context):
        return ConfigValueUnwrapper.deepest_value(
            config_value, config, MockResolver(client()), context
        ).reportable_value()

    @staticmethod
    def context_with_key(key):
        return Context({"user": {"key": key}})

    @staticmethod
    def build_weighted_values(values_and_weights):
        weighted_values = []
        for value in values_and_weights:
            weighted_value = Prefab.WeightedValue(
                value=Prefab.ConfigValue(string=value), weight=values_and_weights[value]
            )
            weighted_values.append(weighted_value)

        return Prefab.WeightedValues(
            weighted_values=weighted_values, hash_by_property_name="user.key"
        )
