from __future__ import annotations
import functools
import threading
import logging
from urllib3 import Retry


from ._telemetry import TelemetryManager
from ._internal_logging import (
    InternalLogger,
    iterate_dotted_string,
    prefab_to_python_log_levels,
    ReentrancyCheck,
)
from .context import Context, ScopedContext
from .config_client import ConfigClient
from .feature_flag_client import FeatureFlagClient
from .options import Options
from ._requests import TimeoutHTTPAdapter, VersionHeader, Version
from typing import Optional, Union
import prefab_pb2 as Prefab
import uuid
import requests
from urllib.parse import urljoin
from .constants import (
    NoDefaultProvided,
    ConfigValueType,
    ContextDictOrContext,
)
from ._internal_constants import LOG_LEVEL_BASE_KEY

PostBodyType = Union[Prefab.Loggers, Prefab.ContextShapes, Prefab.TelemetryEvents]
logger = InternalLogger(__name__)
LLV = Prefab.LogLevel.Value


class Client:
    max_sleep_sec = 10
    base_sleep_sec = 0.5

    def __init__(self, options: Options) -> None:
        self.shutdown_flag = threading.Event()
        self.options = options
        self.global_context = options.global_context
        self.instance_hash = str(uuid.uuid4())
        self.telemetry_manager = TelemetryManager(self, options)
        if not options.is_local_only():
            self.telemetry_manager.start_periodic_sync()
        self.api_urls = options.prefab_api_urls
        # Define the retry strategy
        retry_strategy = Retry(
            total=2,  # Maximum number of retries
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
            allowed_methods=["POST", "GET"],
        )
        # Create an TimeoutHTTPAdapter adapter with the retry strategy and a standard timeout and mount it to session
        adapter = TimeoutHTTPAdapter(max_retries=retry_strategy, timeout=5)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.headers.update({VersionHeader: f"prefab-cloud-python-{Version}"})
        if options.is_local_only():
            logger.info(f"Prefab {Version} running in local-only mode")
        else:
            logger.info(
                f"Prefab {Version} connecting to %s, secure %s"
                % (
                    options.prefab_api_urls,
                    options.http_secure,
                ),
            )

        self.context().clear()
        self.config_client()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get(
        self,
        key: str,
        default: ConfigValueType = NoDefaultProvided,
        context: Optional[ContextDictOrContext] = None,
    ) -> ConfigValueType:
        if self.is_ff(key):
            return self.feature_flag_client().get(key, default=default, context=context)
        else:
            return self.config_client().get(key, default=default, context=context)

    def enabled(
        self, feature_name: str, context: Optional[ContextDictOrContext] = None
    ) -> bool:
        return self.feature_flag_client().feature_is_on_for(
            feature_name, context=context
        )

    def is_ff(self, key: str) -> bool:
        raw = self.config_client().config_resolver.raw(key)
        if raw is not None and raw.config_type == Prefab.ConfigType.Value(
            "FEATURE_FLAG"
        ):
            return True
        return False

    def get_loglevel(self, logger_name: str) -> Optional[int]:
        """determine the loglevel for the given logger_name. The return value is one of the logging.WARNING, logging.INFO numeric constants"""
        try:
            ReentrancyCheck.set()  # set thread local so any internal-to-client-logging doesn't cause lockup
            if not self.config_client().is_ready():
                return self.options.bootstrap_loglevel
            default = logging.WARNING
            if logger_name:
                full_lookup_key = ".".join([LOG_LEVEL_BASE_KEY, logger_name])
            else:
                full_lookup_key = LOG_LEVEL_BASE_KEY

            for lookup_key in iterate_dotted_string(full_lookup_key):
                log_level = self.get(lookup_key, default=None)
                if (
                    log_level is not None
                    and prefab_to_python_log_levels.get(log_level) is not None
                ):
                    return prefab_to_python_log_levels.get(log_level)
            return default
        finally:
            ReentrancyCheck.clear()

    def context(self) -> Context:
        return Context.get_current()

    @staticmethod
    def scoped_context(context: dict | Context) -> ScopedContext:
        return Context.scope(context)

    @functools.cache
    def config_client(self) -> ConfigClient:
        client = ConfigClient(self)
        return client

    @functools.cache
    def feature_flag_client(self) -> FeatureFlagClient:
        return FeatureFlagClient(self)

    def post(self, path: str, body: PostBodyType) -> requests.models.Response:
        headers = {
            "Content-Type": "application/x-protobuf",
            "Accept": "application/x-protobuf",
        }

        endpoint = urljoin(self.options.telemetry_url or "", path)

        return self.session.post(
            endpoint,
            headers=headers,
            data=body.SerializeToString(),
            auth=("authuser", self.options.api_key or ""),
        )

    def record_log(self, logger_name, severity):
        """severity is the python numeric loglevel, eg logging.WARNING"""
        if self.telemetry_manager:
            self.telemetry_manager.record_log(logger_name, severity)

    def is_ready(self) -> bool:
        return self.config_client().is_ready()

    def set_global_context(
        self, global_context: Optional[ContextDictOrContext] = None
    ) -> Client:
        self.global_context = Context.normalize_context_arg(global_context)
        return self

    def close(self) -> None:
        if not self.shutdown_flag.is_set():
            logger.info("Shutting down prefab client instance")
            self.shutdown_flag.set()
            self.config_client().close()
        else:
            logger.warning("Close already called")
