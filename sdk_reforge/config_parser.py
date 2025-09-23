import prefab_pb2 as Prefab

from prefab_cloud_python._internal_constants import LOG_LEVEL_BASE_KEY


class MissingFeatureFlagValueException(Exception):
    "Raised when a feature flag is missing a value"

    def __init__(self, key, source):
        super().__init__(
            "Feature flag config `%s` in %s must have a `value`" % (key, source)
        )


class ConfigParser:
    def parse(key, value, config, source):
        if isinstance(value, dict):
            return ConfigParser.parse_dict(key, value, config, source)
        else:
            parsed = ConfigParser.parse_scalar(key, value, config, source)
            config[key] = parsed
            return config

    def parse_dict(key, value, config, source):
        if value.get("feature_flag") is not None:
            config[key] = ConfigParser.feature_flag_config(key, value, source)
        elif value.get("type") == "provided":
            config[key] = ConfigParser.provided_config(key, value, source)
        else:
            for nest_key in value:
                nest_value = value[nest_key]
                if nest_key == "_":
                    nested_key = key
                else:
                    nested_key = "%s.%s" % (key, nest_key)
                config = ConfigParser.parse(nested_key, nest_value, config, source)
        return config

    def parse_scalar(key, value, config, source):
        return {
            "source": source,
            "match": "default",
            "config": Prefab.Config(
                config_type="CONFIG",
                key=key,
                rows=[
                    Prefab.ConfigRow(
                        values=[
                            Prefab.ConditionalValue(
                                value=ConfigParser.value_from(key, value)
                            )
                        ]
                    )
                ],
            ),
        }

    def provided_config(key, value, source):
        value = Prefab.ConfigValue(
            provided=Prefab.Provided(source="ENV_VAR", lookup=value["lookup"]),
            confidential=value.get("confidential"),
        )

        row = Prefab.ConfigRow(values=[Prefab.ConditionalValue(value=value)])

        return {
            "source": source,
            "match": value.provided.lookup,
            "config": Prefab.Config(config_type="CONFIG", key=key, rows=[row]),
        }

    def feature_flag_config(key, value, source):
        if "value" not in value.keys():
            raise MissingFeatureFlagValueException(key, source)

        if value.get("criterion"):
            criteria = [ConfigParser.parse_criterion(value["criterion"])]
        else:
            criteria = []

        variant = ConfigParser.feature_flag_variant_from(key, value["value"])

        row = Prefab.ConfigRow(
            values=[
                Prefab.ConditionalValue(
                    criteria=criteria,
                    value=Prefab.ConfigValue(
                        weighted_values=Prefab.WeightedValues(
                            weighted_values=[
                                Prefab.WeightedValue(weight=1000, value=variant)
                            ]
                        )
                    ),
                )
            ]
        )

        return {
            "source": source,
            "match": key,
            "config": Prefab.Config(
                config_type="FEATURE_FLAG",
                key=key,
                rows=[row],
                allowable_values=[variant],
            ),
        }

    def parse_criterion(criterion):
        return Prefab.Criterion(
            operator=criterion.get("operator"),
            property_name=ConfigParser.parse_property(criterion),
            value_to_match=ConfigParser.parse_value_to_match(criterion.get("values")),
        )

    def parse_property(criterion):
        if criterion.get("operator") == "LOOKUP_KEY_IN":
            return "LOOKUP"
        else:
            return criterion.get("property")

    def parse_value_to_match(values):
        if isinstance(values, list):
            return Prefab.ConfigValue(string_list=Prefab.StringList(values=values))
        else:
            raise "can't handle %s" % values

    def value_from(key, value):
        if isinstance(value, str):
            if key.startswith(LOG_LEVEL_BASE_KEY):
                log_level = ConfigParser.parse_log_level(value)
                return {"log_level": log_level}
            else:
                return {"string": value}
        elif isinstance(value, bool):
            return {"bool": value}
        elif isinstance(value, int):
            return {"int": value}
        elif isinstance(value, float):
            return {"double": value}
        else:
            pass

    def feature_flag_variant_from(key, value):
        if isinstance(value, str):
            if key.startswith(LOG_LEVEL_BASE_KEY):
                log_level = ConfigParser.parse_log_level(value)
                return Prefab.ConfigValue(log_level=log_level)
            else:
                return Prefab.ConfigValue(string=value)
        elif isinstance(value, bool):
            return Prefab.ConfigValue(bool=value)
        elif isinstance(value, int):
            return Prefab.ConfigValue(int=value)
        elif isinstance(value, float):
            return Prefab.ConfigValue(double=value)
        else:
            pass

    def parse_log_level(log_level):
        if log_level.upper() in Prefab.LogLevel.keys():
            return log_level.upper()
        else:
            return "NOT_SET_LOG_LEVEL"
