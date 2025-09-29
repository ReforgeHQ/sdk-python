from __future__ import annotations


from ._internal_logging import InternalLogger
import threading
import time
from typing import Optional

import prefab_pb2 as Prefab
import os
from ._count_down_latch import CountDownLatch
from ._requests import ApiClient, UnauthorizedException
from ._sse_connection_manager import SSEConnectionManager
from .config_sdk_interface import ConfigSDKInterface
from .config_loader import ConfigLoader
from .config_resolver import ConfigResolver
from .config_value_unwrapper import ConfigValueUnwrapper
from .context import Context
from .config_resolver import Evaluation
from .constants import NoDefaultProvided, ConfigValueType

from google.protobuf.json_format import MessageToJson, Parse


STALE_CACHE_WARN_HOURS = 5

logger = InternalLogger(__name__)


class InitializationTimeoutException(Exception):
    def __init__(self, timeout_seconds, key):
        super().__init__(
            f"Reforge couldn't initialize in {timeout_seconds} second timeout. Trying to fetch key `{key}`."
        )


class MissingDefaultException(Exception):
    def __init__(self, key):
        super().__init__(
            f"""No value found for key '{key}' and no default was provided.
If you'd prefer returning `None` rather than raising when this occurs, modify the `on_no_default` value you provide in your Options."""
        )


class ConfigSDK(ConfigSDKInterface):
    def __init__(self, base_client):
        self.is_initialized = threading.Event()
        self.checkpointing_thread = None
        self.streaming_thread = None
        self.sse_client = None
        logger.info("Initializing ConfigClient")
        self.base_client = base_client
        self._options = base_client.options
        self.init_latch = CountDownLatch()
        self.unauthorized_event = threading.Event()
        self.finish_init_mutex = threading.Lock()
        self.checkpoint_freq_secs = 60
        self.config_loader = ConfigLoader(base_client)
        self.config_resolver = ConfigResolver(base_client, self.config_loader)
        self._cache_path = None
        self.set_cache_path()
        self.api_client = ApiClient(self.options)
        self.sse_connection_manager = SSEConnectionManager(
            self.api_client, self, self.options.reforge_stream_urls
        )

        if self.options.is_local_only():
            self.finish_init("local only")
        elif self.options.has_datafile():
            self.load_json_file(self.options.datafile)
        else:
            # don't load checkpoint here, that'll block the caller. let the thread do it
            self.start_checkpointing_thread()

    def get(
        self,
        key,
        default=NoDefaultProvided,
        context: Optional[dict | Context] = None,
    ) -> ConfigValueType:
        evaluation_result = self.__get(key, None, {}, context=context)
        if evaluation_result is not None:
            self.base_client.telemetry_manager.record_evaluation(evaluation_result)
            if evaluation_result.config:
                return evaluation_result.unwrapped_value()
        return self.handle_default(key, default)

    def __get(
        self,
        key,
        lookup_key,
        properties,
        context: Optional[dict | Context] = None,
    ) -> None | Evaluation:
        ok_to_proceed = self.init_latch.wait(
            timeout=self.options.connection_timeout_seconds
        )
        if self.unauthorized_event.is_set():
            raise UnauthorizedException(self.options.api_key)
        if not ok_to_proceed:
            if self.options.on_connection_failure == "RAISE":
                raise InitializationTimeoutException(
                    self.options.connection_timeout_seconds, key
                )
            logger.warning(
                f"Couldn't initialize in {self.options.connection_timeout_seconds}. Key {key}. Returning what we have.",
            )
        return self.config_resolver.get(key, context=context)

    @property
    def options(self):
        return self._options

    def handle_default(self, key, default):
        if default != NoDefaultProvided:
            return default
        if self.options.on_no_default == "RAISE":
            raise MissingDefaultException(key)
        return None

    def load_checkpoint(self):
        try:
            if self.load_checkpoint_from_api_cdn():
                return
            if self.load_cache():
                return
            logger.warning("No success loading checkpoints")
        except UnauthorizedException:
            self.handle_unauthorized_response()

    def start_checkpointing_thread(self):
        self.checkpointing_thread = threading.Thread(
            target=self.load_checkpoint, daemon=True
        )
        self.checkpointing_thread.start()

    def start_streaming(self):
        self.streaming_thread = threading.Thread(
            target=self.sse_connection_manager.streaming_loop, daemon=True
        )
        self.streaming_thread.start()

    def is_shutting_down(self):
        return self.base_client.shutdown_flag.is_set()

    def continue_connection_processing(self):
        return not self.is_shutting_down() and not self.unauthorized_event.is_set()

    def highwater_mark(self) -> int:
        return self.config_loader.highwater_mark

    def load_initial_data(self):
        try:
            self.load_checkpoint()
        except UnauthorizedException:
            self.handle_unauthorized_response()

    def load_checkpoint_from_api_cdn(self):
        try:
            hwm = self.config_loader.highwater_mark
            response = self.api_client.resilient_request(
                "/api/v2/configs/" + str(hwm),
                auth=("authuser", self.options.api_key),
                timeout=4,
                allow_cache=True,
            )
            if response.ok:
                if not response.content or len(response.content) == 0:
                    logger.warning(
                        "Received zero-byte config payload from remote_cdn_api, treating as connection error"
                    )
                    return False
                configs = Prefab.Configs.FromString(response.content)
                self.load_configs(configs, "remote_api_cdn")
                return True
            else:
                logger.info(
                    "Checkpoint remote_cdn_api failed to load",
                )
                return False
        except UnauthorizedException:
            self.handle_unauthorized_response()

    def load_configs(self, configs: Prefab.Configs, source: str) -> None:
        project_id = configs.config_service_pointer.project_id
        project_env_id = configs.config_service_pointer.project_env_id
        self.config_resolver.project_env_id = project_env_id
        starting_highwater_mark = self.config_loader.highwater_mark

        default_contexts = {}
        if configs.default_context and configs.default_context.contexts is not None:
            for context in configs.default_context.contexts:
                values = {}
                for k, v in context.values.items():
                    values[k] = ConfigValueUnwrapper(v, self.config_resolver).unwrap()
                default_contexts[context.type] = values

        self.config_resolver.default_context = default_contexts

        for config in configs.configs:
            self.config_loader.set(config, source)
        if self.config_loader.highwater_mark > starting_highwater_mark:
            logger.info(
                f"Found new checkpoint with highwater id {self.config_loader.highwater_mark} from {source} in project {project_id} environment: {project_env_id}",
            )
        else:
            logger.debug(
                f"Checkpoint with highwater id {self.config_loader.highwater_mark} from {source}. No changes.",
            )
        self.config_resolver.update()
        self.finish_init(source)

    def cache_configs(self, configs):
        if not self.options.use_local_cache:
            return
        if not self.cache_path:
            return
        with open(self.cache_path, "w") as f:
            f.write(MessageToJson(configs))
            logger.debug(f"Cached configs to {self.cache_path}")

    def load_cache(self):
        if not self.options.use_local_cache:
            return False
        if not self.cache_path:
            return False
        try:
            with open(self.cache_path, "r") as f:
                configs = Parse(f.read(), Prefab.Configs())
                self.load_configs(configs, "cache")

                hours_old = round(
                    (time.mktime(time.localtime()) - os.path.getmtime(self.cache_path))
                    / 3600,
                    2,
                )
                if hours_old > STALE_CACHE_WARN_HOURS:
                    logger.info(f"Stale Cache Load: {hours_old} hours old")
                return True
        except OSError as e:
            logger.info("error loading from cache", e)
            return False

    def load_json_file(self, datafile):
        with open(datafile) as f:
            configs = Parse(f.read(), Prefab.Configs())
            self.load_configs(configs, "datafile")

    def finish_init(self, source):
        with self.finish_init_mutex:
            was_initialized = self.is_initialized.is_set()
            self.is_initialized.set()
            self.init_latch.count_down()
            if not was_initialized:
                logger.warning(f"Unlocked config via {source}")
                if self.options.is_loading_from_api():
                    self.start_streaming()
                if self.options.on_ready_callback:
                    threading.Thread(
                        target=self.options.on_ready_callback, daemon=True
                    ).start()

    def set_cache_path(self):
        home_dir_cache_path = None
        home_dir = os.environ.get("HOME")
        if home_dir:
            home_dir_cache_path = os.path.join(home_dir, ".cache")
        cache_path = os.environ.get("XDG_CACHE_HOME", home_dir_cache_path)
        if cache_path:
            file_name = f"prefab.cache.{self.base_client.options.api_key_id}.json"
            self.cache_path = os.path.join(cache_path, file_name)

    @property
    def cache_path(self):
        if self._cache_path:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
        return self._cache_path

    @cache_path.setter
    def cache_path(self, path):
        self._cache_path = path

    def record_log(self, path, severity):
        self.base_client.record_log(path, severity)

    def is_ready(self) -> bool:
        return self.is_initialized.is_set()

    def handle_unauthorized_response(self):
        logger.error("Received unauthorized response")
        self.unauthorized_event.set()
        self.init_latch.count_down()

    def close(self) -> None:
        if self.sse_client:
            self.sse_client.close()
