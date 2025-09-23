import json


from typing import TYPE_CHECKING, ForwardRef

if TYPE_CHECKING:
    from .config_resolver import ConfigResolver
else:
    ConfigResolver = ForwardRef("ConfigResolver")

from .weighted_value_resolver import WeightedValueResolver
from .config_value_wrapper import ConfigValueWrapper
from .context import Context
from .encryption import Encryption, DecryptionException
import prefab_pb2 as Prefab
import yaml
import os
import hashlib
import isodate
from ._internal_logging import InternalLogger

VTV = Prefab.Config.ValueType.Value
VTN = Prefab.Config.ValueType.Name
CONFIDENTIAL_PREFIX = "*****"

logger = InternalLogger(__name__)


class EnvVarParseException(Exception):
    "Raised when an invalid value type is set for a `provided` config value"

    def __init__(self, env_var, config, env_var_name):
        super().__init__(
            "Evaluating %s couldn't coerce %s of %s to %s"
            % (config.key, env_var_name, env_var, VTN(config.value_type))
        )


class MissingEnvVarException(Exception):
    "Raised when an environment variable specified in a `provided` config value does not exist"

    def __init__(self, config, env_var_name):
        super().__init__(
            "Environment variable %s referenced in config %s does not exist"
            % (config.key, env_var_name)
        )


class UnknownConfigValueTypeException(Exception):
    "Raised when a config value of an unknown type is passed to the unwrapper"

    def __init__(self, type):
        super().__init__("Unknown config value type: %s" % type)


class UnknownProvidedSourceException(Exception):
    "Raised when a provided value has an unknown source"

    def __init__(self, source):
        super().__init__("Unknown provided source: %s" % source)


class ConfigValueUnwrapper:
    def __init__(self, value, resolver, weighted_value_index=None):
        self.value = value
        self.resolver = resolver
        self.weighted_value_index = weighted_value_index

    def reportable_wrapped_value(self):
        if self.value.confidential or len(self.value.decrypt_with) > 0:
            # Unique hash for differentiation
            hash = hashlib.md5()
            hash.update(str(self.unwrap()).encode())
            return ConfigValueUnwrapper(
                ConfigValueWrapper.wrap(f"{CONFIDENTIAL_PREFIX}{hash.hexdigest()[:5]}"),
                self.resolver,
                self.weighted_value_index,
            )
        else:
            return self

    def reportable_value(self):
        return self.reportable_wrapped_value().unwrap()

    @staticmethod
    def deepest_value(
        config_value: Prefab.ConfigValue,
        config: Prefab.Config,
        resolver: ConfigResolver,
        context=Context.get_current(),
    ):
        if config_value and config_value.WhichOneof("type") == "weighted_values":
            value, index = WeightedValueResolver(
                config_value.weighted_values.weighted_values,
                config.key,
                context.get(config_value.weighted_values.hash_by_property_name),
            ).resolve()
            return ConfigValueUnwrapper(
                ConfigValueUnwrapper.deepest_value(
                    value.value, config, resolver, context
                ).value,
                resolver,
                index,
            )
        elif config_value and config_value.WhichOneof("type") == "provided":
            if config_value.provided.source == Prefab.ProvidedSource.Value("ENV_VAR"):
                raw = os.getenv(config_value.provided.lookup)
                if raw is None:
                    raise MissingEnvVarException(config, config_value.provided.lookup)
                    # resolver.base_client.logger.log_internal(
                    #     "warn",
                    #     f"ENV Variable {config_value.provided.lookup} not found. Using empty string.",
                    # )
                    # return ConfigValueUnwrapper(ConfigValueWrapper.wrap(""), resolver)
                else:
                    coerced = ConfigValueUnwrapper.coerce_into_type(
                        raw, config, config_value.provided.lookup
                    )
                    return ConfigValueUnwrapper(
                        ConfigValueWrapper.wrap(coerced), resolver
                    )
            else:
                raise UnknownProvidedSourceException(config_value.provided.source)

        else:
            return ConfigValueUnwrapper(config_value, resolver)

    def unwrap(self):
        if self.value is None:
            return None

        type = self.value.WhichOneof("type")

        if type in ["int", "string", "double", "bool", "log_level"]:
            raw = getattr(self.value, type)
        elif type == "string_list":
            raw = list(self.value.string_list.values)
        elif type == "duration":
            raw = isodate.parse_duration(self.value.duration.definition)
        elif type == "json":
            raw = json.loads(self.value.json.json)
        else:
            raise UnknownConfigValueTypeException(type)

        if self.value.decrypt_with != "":
            decryption_key_evaluation = self.resolver.get(self.value.decrypt_with)
            if (
                decryption_key_evaluation is None
                or decryption_key_evaluation.raw_config_value is None
            ):
                logger.warning(
                    f"No value for decryption key {self.value.decrypt_with} found.",
                )
                return ""
            else:
                try:
                    return Encryption(
                        decryption_key_evaluation.unwrapped_value()
                    ).decrypt(raw)
                except Exception:
                    raise DecryptionException("unable to decrypt value")
        else:
            return raw

    @staticmethod
    def coerce_into_type(value_string, config, env_var_name):
        try:
            value_type = config.value_type
            if value_type == VTV("INT"):
                return int(value_string)
            if value_type == VTV("DOUBLE"):
                return float(value_string)
            elif value_type == VTV("STRING"):
                return str(value_string)
            elif value_type == VTV("STRING_LIST"):
                maybe_string_list = yaml.safe_load(value_string)
                if isinstance(maybe_string_list, list):
                    return maybe_string_list
                else:
                    raise EnvVarParseException(value_string, config, env_var_name)
            elif value_type == VTV("BOOL"):
                maybe_bool = yaml.safe_load(value_string)
                if maybe_bool is True or maybe_bool is False:
                    return maybe_bool
                else:
                    raise EnvVarParseException(value_string, config, env_var_name)
            elif value_type == VTV("NOT_SET_VALUE_TYPE"):
                return yaml.safe_load(value_string)
            else:
                raise EnvVarParseException(value_string, config, env_var_name)
        except ValueError:
            raise EnvVarParseException(value_string, config, env_var_name)
