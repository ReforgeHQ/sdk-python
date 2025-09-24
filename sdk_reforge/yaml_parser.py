from .config_parser import ConfigParser
import yaml
from ._internal_logging import InternalLogger

logger = InternalLogger(__name__)


class YamlParser:
    def __init__(self, filename: str, base_client=None) -> None:
        self.filename = filename
        self.base_client = base_client
        self.data = {}
        self.parse()

    def parse(self):
        try:
            with open(self.filename, "r") as f:
                yaml_data = yaml.safe_load(f.read())
                if not yaml_data or not isinstance(yaml_data, dict):
                    return
                config = {}
                for key in yaml_data:
                    config = ConfigParser.parse(
                        key, yaml_data[key], config, self.filename
                    )
                self.data = config
        except FileNotFoundError:
            logger.warning(f"YamlParser could not find {self.filename} to parse")
            return
