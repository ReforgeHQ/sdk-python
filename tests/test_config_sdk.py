import threading

from prefab_cloud_python import Options, Client
from prefab_cloud_python.config_client import MissingDefaultException, ConfigClient
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


class ConfigClientFactoryFixture:
    def __init__(self):
        self.client = None

    def create_config_client(self, options: Options) -> ConfigClient:
        self.client = Client(options)
        return self.client.config_client()

    def close(self):
        if self.client:
            self.client.close()


@pytest.fixture
def config_client_factory():
    factory_fixture = ConfigClientFactoryFixture()
    yield factory_fixture
    factory_fixture.close()


@pytest.fixture
def options():
    def options(
        on_no_default="RAISE",
        x_use_local_cache=True,
        prefab_envs=["unit_tests"],
        api_key=None,
        prefab_datasources="LOCAL_ONLY",
        on_ready_callback=None,
    ):
        return Options(
            api_key=api_key,
            prefab_config_classpath_dir="tests",
            prefab_envs=prefab_envs,
            prefab_datasources=prefab_datasources,
            x_use_local_cache=x_use_local_cache,
            on_no_default=on_no_default,
            collect_sync_interval=None,
            on_ready_callback=on_ready_callback,
        )

    return options


class TestConfigClient:
    def test_get(self, config_client_factory, options):
        config_client = config_client_factory.create_config_client(options())

        assert config_client.get("sample") == "test sample value"
        assert config_client.get("sample_int") == 123
        assert config_client.get("sample_double") == 12.12
        assert config_client.get("sample_bool")
        assert config_client.get("log-level.app") == Prefab.LogLevel.Value("ERROR")

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
            options(api_key="123-API-KEY-SDK", prefab_datasources="ALL")
        )
        assert (
            config_client.cache_path
            == f"{os.environ['HOME']}/.cache/prefab.cache.123.json"
        )

    def test_cache_path_local_only(self, config_client_factory, options):
        config_client = config_client_factory.create_config_client(
            options(prefab_envs=[])
        )
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
