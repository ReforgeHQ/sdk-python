from abc import ABC, abstractmethod
import reforge_pb2 as Reforge
from reforge_python import Options


class ConfigSDKInterface(ABC):
    @abstractmethod
    def continue_connection_processing(self) -> bool:
        pass

    @abstractmethod
    def highwater_mark(self) -> int:
        pass

    @abstractmethod
    def handle_unauthorized_response(self) -> None:
        pass

    @abstractmethod
    def is_shutting_down(self) -> bool:
        pass

    @abstractmethod
    def load_configs(self, configs: Reforge.Configs, src: str) -> None:
        pass

    @property
    @abstractmethod
    def options(self) -> Options:
        pass
