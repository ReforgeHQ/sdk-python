from __future__ import annotations

import os
from enum import Enum
from urllib.parse import urlparse
from typing import Optional, Callable, Type

from .context import Context
from .constants import ContextDictType


class MissingSdkKeyException(Exception):
    """
    Raised when no SDK key is found
    """

    def __init__(self) -> None:
        super().__init__("No SDK key found - set REFORGE_BACKEND_SDK_KEY")


class InvalidSdkKeyException(Exception):
    """
    Raised when an invalid SDK key is provided
    """

    def __init__(self, api_key: str) -> None:
        super().__init__(f"Invalid SDK key: {api_key}")


class InvalidApiUrlException(Exception):
    """
    Raised when an invalid API URL is given
    """

    def __init__(self, url: str) -> None:
        super().__init__(f"Invalid API URL found: {url}")


class InvalidStreamUrlException(Exception):
    """
    Raised when an invalid API URL is given
    """

    def __init__(self, url: str) -> None:
        super().__init__(f"Invalid Stream URL found: {url}")


VALID_DATASOURCES = ("LOCAL_ONLY", "ALL")
VALID_ON_NO_DEFAULT = ("RAISE", "RETURN_NONE")
VALID_ON_CONNECTION_FAILURE = ("RETURN", "RAISE")


class Options:
    class ContextUploadMode(Enum):
        NONE = 1
        SHAPE_ONLY = 2
        PERIODIC_EXAMPLE = 3

    def __init__(
        self,
        sdk_key: Optional[str] = None,
        reforge_api_urls: Optional[list[str]] = None,
        reforge_stream_urls: Optional[list[str]] = None,
        reforge_telemetry_url: Optional[str] = None,
        reforge_datasources: Optional[str] = None,
        connection_timeout_seconds: int = 10,
        http_secure: Optional[bool] = None,
        on_no_default: str = "RAISE",
        on_connection_failure: str = "RETURN",
        x_use_local_cache: bool = False,
        x_datafile: Optional[str] = None,
        collect_max_shapes: int = 10_000,
        collect_sync_interval: Optional[int] = 30,
        collect_evaluation_summaries: bool = True,
        context_upload_mode: ContextUploadMode = ContextUploadMode.PERIODIC_EXAMPLE,
        global_context: Optional[ContextDictType | Context] = None,
        on_ready_callback: Optional[Callable[[], None]] = None,
        logger_key: str = "log-levels.default",
    ) -> None:
        self.reforge_datasources = Options.__validate_datasource(reforge_datasources)
        self.datafile = x_datafile
        self.__set_api_key(
            sdk_key
            or os.environ.get("REFORGE_BACKEND_SDK_KEY")
            or os.environ.get("PREFAB_API_KEY")
        )
        self.__set_api_url(
            reforge_api_urls
            or self.api_urls_from_env()
            or ["https://primary.reforge.com", "https://secondary.reforge.com"]
        )
        self.__set_stream_url(
            reforge_stream_urls
            or self.stream_urls_from_env()
            or ["https://stream.reforge.com"]
        )
        self.telemetry_url = self.validate_url(
            reforge_telemetry_url or "https://telemetry.reforge.com"
        )
        self.connection_timeout_seconds = connection_timeout_seconds
        self.http_secure = http_secure or os.environ.get("REFORGE_HTTP") != "true"
        self.stats = None
        self.shared_cache = None
        self.use_local_cache = x_use_local_cache
        self.__set_on_no_default(on_no_default)
        self.__set_on_connection_failure(on_connection_failure)
        self.collect_sync_interval = collect_sync_interval
        self.collect_max_shapes = collect_max_shapes
        self.context_upload_mode = context_upload_mode
        self.collect_evaluation_summaries = collect_evaluation_summaries
        self.global_context = Context.normalize_context_arg(global_context)
        self.on_ready_callback = on_ready_callback
        self.logger_key = logger_key

    def is_local_only(self) -> bool:
        return self.reforge_datasources == "LOCAL_ONLY"

    def has_datafile(self) -> bool:
        return self.datafile is not None

    def is_loading_from_api(self) -> bool:
        return not (self.is_local_only() or self.has_datafile())

    @staticmethod
    def __validate_datasource(datasource: Optional[str]) -> str:
        if os.getenv("REFORGE_DATASOURCES") == "LOCAL_ONLY":
            default = "LOCAL_ONLY"
        else:
            default = "ALL"

        if datasource in VALID_DATASOURCES:
            return datasource
        else:
            return default

    def __set_api_key(self, api_key: Optional[str]) -> None:
        if self.is_local_only() or self.has_datafile():
            self.api_key = None
            self.api_key_id = "local"
            return

        if api_key is None:
            raise MissingSdkKeyException()
        api_key = str(api_key).strip()
        if "-" not in api_key:
            raise InvalidSdkKeyException(api_key)
        self.api_key = api_key
        self.api_key_id = api_key.split("-")[0]

    def __set_api_url(self, api_url_list: list[str]) -> None:
        if self.reforge_datasources == "LOCAL_ONLY":
            self.reforge_api_urls = None
            return
        self.reforge_api_urls = self.validate_and_process_urls(
            api_url_list, InvalidApiUrlException
        )

    def __set_stream_url(self, stream_url_list: list[str]) -> None:
        if self.reforge_datasources == "LOCAL_ONLY":
            self.reforge_stream_urls = None
            return
        self.reforge_stream_urls = self.validate_and_process_urls(
            stream_url_list, InvalidStreamUrlException
        )

    @staticmethod
    def validate_url(
        api_url: str, exception_type: Type[Exception] = InvalidApiUrlException
    ) -> str:
        parsed_url = urlparse(str(api_url))
        if parsed_url.scheme in ["http", "https"]:
            return api_url.rstrip("/")
        else:
            raise exception_type(api_url)

    @staticmethod
    def urls_from_env_var(env_var_name: str) -> Optional[list[str]]:
        envvar = os.environ.get(env_var_name)
        if envvar:
            return envvar.split(",")
        return None

    @staticmethod
    def api_urls_from_env() -> Optional[list[str]]:
        return Options.urls_from_env_var("REFORGE_API_URL")

    @staticmethod
    def stream_urls_from_env() -> Optional[list[str]]:
        return Options.urls_from_env_var("REFORGE_STREAM_URL")

    def validate_and_process_urls(
        self,
        api_url_list: list[str],
        exception_type: Type[Exception] = InvalidApiUrlException,
    ) -> list[str]:
        valid_urls = []
        for api_url in api_url_list:
            try:
                valid_urls.append(self.validate_url(api_url, exception_type))
            except InvalidApiUrlException as e:
                raise e
        return valid_urls

    def __set_on_no_default(self, value: str) -> None:
        if value in VALID_ON_NO_DEFAULT:
            self.on_no_default = value
        else:
            self.on_no_default = "RAISE"

    def __set_on_connection_failure(self, value: str) -> None:
        if value in VALID_ON_CONNECTION_FAILURE:
            self.on_connection_failure = value
        else:
            self.on_connection_failure = "RETURN"
