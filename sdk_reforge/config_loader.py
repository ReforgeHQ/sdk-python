import prefab_pb2 as Prefab
from ._internal_logging import InternalLogger

logger = InternalLogger(__name__)


class ConfigLoader:
    def __init__(self, base_client):
        self.base_client = base_client
        self.options = base_client.options
        self.highwater_mark = 0
        self.classpath_config = {}
        self.local_overrides = {}
        self.api_config = {}

    def calc_config(self):
        return self.classpath_config | self.api_config | self.local_overrides

    def set(self, config, source):
        existing_config = self.api_config.get(config.key)
        if existing_config and existing_config["config"].id >= config.id:
            return

        if len(config.rows) == 0 and config.key in self.api_config:
            self.api_config.pop(config.key)
        else:
            if existing_config:
                logger.debug(
                    "Replace %s with value from %s %s -> %s"
                    % (config.key, source, existing_config["config"].id, config.id),
                )
            self.api_config[config.key] = {"source": source, "config": config}
        self.highwater_mark = max([config.id, self.highwater_mark])

    def get_api_deltas(self):
        configs = Prefab.Configs()
        for config_value in self.api_config.values():
            configs.configs.append(config_value["config"])
        return configs
