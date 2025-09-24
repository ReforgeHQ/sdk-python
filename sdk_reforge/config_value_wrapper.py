from datetime import date, datetime, timezone

import prefab_pb2 as Prefab


class ConfigValueWrapper:
    @staticmethod
    def wrap(value, confidential=None):
        value_type = type(value)
        if value_type == Prefab.ConfigValue:
            return value
        elif value_type == int:
            return Prefab.ConfigValue(int=value, confidential=confidential)
        elif value_type == float:
            return Prefab.ConfigValue(double=value, confidential=confidential)
        elif value_type == bool:
            return Prefab.ConfigValue(bool=value, confidential=confidential)
        elif value_type == list:
            return Prefab.ConfigValue(
                string_list=Prefab.StringList(values=[str(x) for x in value]),
                confidential=confidential,
            )
        elif value_type == datetime:
            return Prefab.ConfigValue(
                string=ConfigValueWrapper._format_date_time(value),
                confidential=confidential,
            )
        elif value_type == date:
            return Prefab.ConfigValue(
                string=ConfigValueWrapper._format_date_time(
                    datetime.combine(value, datetime.min.time(), timezone.utc)
                ),
                confidential=confidential,
            )
        else:
            return Prefab.ConfigValue(string=value, confidential=confidential)

    @staticmethod
    def _format_date_time(value: datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
