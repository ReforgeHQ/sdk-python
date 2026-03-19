import threading

from sdk_reforge import Options, ReforgeSDK as Client
from sdk_reforge.config_sdk import MissingDefaultException, ConfigSDK
import prefab_pb2 as Prefab
import pytest
import os

from contextlib import contextmanager


@contextmanager
def extended_env(new_env_vars, deleted_env_vars=[]):
    old_env = os.environ.copy()
    os.environ.update(new_env_vars)
    for deleted_env_var in deleted_env_vars:
        os.environ.pop(deleted_env_var, None)
    yield
    os.environ.clear()
    os.environ.update(old_env)


class ConfigSDKFactoryFixture:
    def __init__(self):
        self.client = None

    def create_config_client(self, options: Options) -> ConfigSDK:
        self.client = Client(options)
        return self.client.config_sdk()

    def close(self):
        if self.client:
            self.client.close()


@pytest.fixture
def config_client_factory():
    factory_fixture = ConfigSDKFactoryFixture()
    yield factory_fixture
    factory_fixture.close()


@pytest.fixture
def options():
    def options(
        on_no_default="RAISE",
        x_use_local_cache=True,
        sdk_key=None,
        reforge_datasources="LOCAL_ONLY",
        on_ready_callback=None,
    ):
        # Only use datafile for LOCAL_ONLY mode, not for ALL mode
        datafile = (
            "tests/prefab.datafile.json"
            if reforge_datasources == "LOCAL_ONLY"
            else None
        )
        return Options(
            sdk_key=sdk_key,
            x_datafile=datafile,
            x_use_local_cache=x_use_local_cache,
            on_no_default=on_no_default,
            collect_sync_interval=None,
            on_ready_callback=on_ready_callback,
        )

    return options


class TestConfigSDK:
    def test_get(self, config_client_factory, options):
        config_client = config_client_factory.create_config_client(options())

        assert config_client.get("foo.str") == "hello!"

    def test_get_with_default(self, config_client_factory, options):
        config_client = config_client_factory.create_config_client(options())

        assert config_client.get("bad key", "default value") == "default value"

    def test_get_without_default_raises(self, config_client_factory, options):
        config_client = config_client_factory.create_config_client(options())

        with pytest.raises(MissingDefaultException) as exception:
            config_client.get("bad key")

        assert "No value found for key 'bad key' and no default was provided." in str(
            exception.value
        )

    def test_get_without_default_returns_none_if_configured(
        self, config_client_factory, options
    ):
        config_client = config_client_factory.create_config_client(
            options(on_no_default="RETURN_NONE")
        )
        assert config_client.get("bad key") is None

    def test_caching(self, config_client_factory, options):
        config_client = config_client_factory.create_config_client(options())
        cached_config = Prefab.Configs(
            configs=[
                Prefab.Config(
                    key="test",
                    id=1,
                    rows=[
                        Prefab.ConfigRow(
                            values=[
                                Prefab.ConditionalValue(
                                    value=Prefab.ConfigValue(string="test value")
                                )
                            ]
                        )
                    ],
                )
            ],
            config_service_pointer=Prefab.ConfigServicePointer(
                project_id=3, project_env_id=5
            ),
        )
        config_client.cache_configs(cached_config)

        config_client.load_cache()
        assert config_client.get("test") == "test value"

    def test_cache_path(self, config_client_factory, options):
        config_client = config_client_factory.create_config_client(
            options(sdk_key="123-API-KEY-SDK", reforge_datasources="ALL")
        )
        assert (
            config_client.cache_path
            == f"{os.environ['HOME']}/.cache/prefab.cache.123.json"
        )

    def test_cache_path_local_only(self, config_client_factory, options):
        config_client = config_client_factory.create_config_client(options())
        assert (
            config_client.cache_path
            == f"{os.environ['HOME']}/.cache/prefab.cache.local.json"
        )

    def test_cache_path_local_only_with_no_home_dir_or_xdg(
        self, config_client_factory, options
    ):
        with extended_env({}, deleted_env_vars=["HOME"]):
            config_client = config_client_factory.create_config_client(options())
            assert config_client.cache_path is None

    def test_cache_path_respects_xdg(self, config_client_factory, options):
        with extended_env({"XDG_CACHE_HOME": "/tmp"}):
            config_client = config_client_factory.create_config_client(options())
            assert config_client.cache_path == "/tmp/prefab.cache.local.json"

    def test_on_ready_callback(self, config_client_factory, options):
        on_ready_called = threading.Event()

        def my_on_ready_callback():
            on_ready_called.set()

        config_client_factory.create_config_client(
            options(on_ready_callback=my_on_ready_callback)
        )
        on_ready_called.wait(timeout=2)
        assert on_ready_called.is_set()


class TestLoadCheckpointErrorHandling:
    """Test that load_checkpoint handles errors gracefully and starts streaming.

    The design is that streaming should start as a fallback even if checkpoint
    loading fails, but finish_init() should NOT be called - let SSE load configs
    (which will call finish_init), or let the timeout in get() kick in as designed.
    """

    def test_starts_streaming_when_no_checkpoint_found(self):
        """When both CDN and cache fail to load, streaming should still start."""
        from unittest.mock import Mock, patch

        mock_base_client = Mock()
        mock_base_client.options = Options(
            sdk_key="123-test-key",
            x_use_local_cache=False,
        )
        mock_base_client.shutdown_flag = threading.Event()

        with patch.object(ConfigSDK, "__init__", lambda self, x: None):
            config_sdk = ConfigSDK(None)
            config_sdk.base_client = mock_base_client
            config_sdk._options = mock_base_client.options
            config_sdk.config_loader = Mock()
            config_sdk.config_loader.highwater_mark = 0
            config_sdk.api_client = Mock()
            config_sdk.is_initialized = threading.Event()
            config_sdk.init_latch = Mock()
            config_sdk.finish_init_mutex = threading.Lock()
            config_sdk.watchdog = None
            config_sdk.streaming_thread = None
            config_sdk.sse_connection_manager = Mock()

            # Mock load methods to return False (no data found)
            config_sdk.load_checkpoint_from_api_cdn = Mock(return_value=False)
            config_sdk.load_cache = Mock(return_value=False)
            config_sdk.start_streaming = Mock()

            config_sdk.load_checkpoint()

            # finish_init should NOT have been called - let SSE or timeout handle it
            assert not config_sdk.is_initialized.is_set()
            config_sdk.init_latch.count_down.assert_not_called()
            # But streaming should start as fallback
            config_sdk.start_streaming.assert_called_once()

    def test_starts_streaming_on_unexpected_exception(self):
        """When an unexpected exception occurs, streaming should still start."""
        from unittest.mock import Mock, patch

        mock_base_client = Mock()
        mock_base_client.options = Options(
            sdk_key="123-test-key",
            x_use_local_cache=False,
        )
        mock_base_client.shutdown_flag = threading.Event()

        with patch.object(ConfigSDK, "__init__", lambda self, x: None):
            config_sdk = ConfigSDK(None)
            config_sdk.base_client = mock_base_client
            config_sdk._options = mock_base_client.options
            config_sdk.config_loader = Mock()
            config_sdk.config_loader.highwater_mark = 0
            config_sdk.api_client = Mock()
            config_sdk.is_initialized = threading.Event()
            config_sdk.init_latch = Mock()
            config_sdk.finish_init_mutex = threading.Lock()
            config_sdk.watchdog = None
            config_sdk.streaming_thread = None
            config_sdk.sse_connection_manager = Mock()

            # Mock load_checkpoint_from_api_cdn to raise an unexpected exception
            config_sdk.load_checkpoint_from_api_cdn = Mock(
                side_effect=RuntimeError("Unexpected network error")
            )
            config_sdk.start_streaming = Mock()

            config_sdk.load_checkpoint()

            # finish_init should NOT have been called - let SSE or timeout handle it
            assert not config_sdk.is_initialized.is_set()
            config_sdk.init_latch.count_down.assert_not_called()
            # But streaming should start as fallback
            config_sdk.start_streaming.assert_called_once()

    def test_does_not_start_streaming_on_unauthorized(self):
        """When UnauthorizedException occurs, streaming should NOT start."""
        from unittest.mock import Mock, patch
        from sdk_reforge._requests import UnauthorizedException

        mock_base_client = Mock()
        mock_base_client.options = Options(
            sdk_key="123-test-key",
            x_use_local_cache=False,
        )
        mock_base_client.shutdown_flag = threading.Event()

        with patch.object(ConfigSDK, "__init__", lambda self, x: None):
            config_sdk = ConfigSDK(None)
            config_sdk.base_client = mock_base_client
            config_sdk._options = mock_base_client.options
            config_sdk.config_loader = Mock()
            config_sdk.config_loader.highwater_mark = 0
            config_sdk.api_client = Mock()
            config_sdk.is_initialized = threading.Event()
            config_sdk.init_latch = Mock()
            config_sdk.finish_init_mutex = threading.Lock()
            config_sdk.unauthorized_event = threading.Event()
            config_sdk.watchdog = None
            config_sdk.streaming_thread = None
            config_sdk.sse_connection_manager = Mock()

            # Mock load_checkpoint_from_api_cdn to raise UnauthorizedException
            config_sdk.load_checkpoint_from_api_cdn = Mock(
                side_effect=UnauthorizedException("bad-key")
            )
            config_sdk.start_streaming = Mock()

            config_sdk.load_checkpoint()

            # Unauthorized should be handled, streaming should NOT start
            assert config_sdk.unauthorized_event.is_set()
            config_sdk.init_latch.count_down.assert_called_once()
            config_sdk.start_streaming.assert_not_called()
