import logging

from prefab_cloud_python import Options, Client
from prefab_cloud_python.config_client import MissingDefaultException
import pytest


@pytest.fixture
def client():
    options = Options(
        prefab_config_classpath_dir="tests",
        prefab_envs=["unit_tests"],
        prefab_datasources="LOCAL_ONLY",
        collect_sync_interval=None,
    )
    client_instance = Client(options)
    yield client_instance
    client_instance.close()


class TestClient:
    def test_get(self, client):
        assert client.get("sample") == "test sample value"
        assert client.get("sample_int") == 123

    def test_get_with_default(self, client):
        assert not client.get("false_value", default="red")
        assert client.get("zero_value", default="red") == 0
        assert client.get("missing_value", default="buckets") == "buckets"

    def test_get_with_missing_default(self, client):
        with pytest.raises(MissingDefaultException) as exception:
            assert client.get("missing_value") is None

        assert "No value found for key 'missing_value'" in str(exception)
        assert "on_no_default" in str(exception)

    def test_can_be_configured_to_return_none_when_missing_default(self, client):
        options = client.options
        options.on_no_default = "RETURN_NONE"
        client = Client(options)

        assert client.get("missing_value") is None

    def test_loading_from_datafile(self):
        options = Options(
            x_datafile="tests/prefab.datafile.json", collect_sync_interval=None
        )
        client = Client(options)
        assert client.get("foo.str") == "hello!"

    def test_enabled(self, client):
        assert not client.enabled("does_not_exist")
        assert client.enabled("enabled_flag")
        assert not client.enabled("disabled_flag")
        assert not client.enabled("flag_with_a_value")

    def test_enabled_with_user_key_match(self, client):
        assert not client.enabled("user_key_match", context={"user": {"key": "jimmy"}})
        assert client.enabled("user_key_match", context={"user": {"key": "abc123"}})
        assert client.enabled("user_key_match", context={"user": {"key": "xyz987"}})

    def test_enabled_with_scoped_context(self, client):
        with Client.scoped_context({"user": {"key": "jimmy"}}):
            assert not client.enabled("user_key_match")

        with Client.scoped_context({"user": {"key": "abc123"}}):
            assert client.enabled("user_key_match")

        with Client.scoped_context({"user": {"key": "xyz987"}}):
            assert client.enabled("user_key_match")

    def test_ff_enabled_with_context(self, client):
        assert not client.enabled(
            "just_my_domain", context={"user": {"domain": "gmail.com"}}
        )
        assert not client.enabled(
            "just_my_domain", context={"user": {"domain": "prefab.cloud"}}
        )
        assert not client.enabled(
            "just_my_domain", context={"user": {"domain": "example.com"}}
        )

    def test_ff_get_with_attributes(self, client):
        assert (
            client.get(
                "just_my_domain",
                default=None,
                context={"user": {"domain": "gmail.com"}},
            )
            is None
        )
        assert (
            client.get(
                "just_my_domain",
                context={"user": {"domain": "gmail.com"}},
                default="DEFAULT",
            )
            == "DEFAULT"
        )
        assert (
            client.get(
                "just_my_domain",
                context={"user": {"domain": "prefab.cloud"}},
            )
            == "new-version"
        )
        assert (
            client.get("just_my_domain", context={"user": {"domain": "example.com"}})
            == "new-version"
        )

    def test_ff_get_with_scoped_context(self, client):
        with Client.scoped_context({"user": {"domain": "gmail.com"}}):
            assert client.get("just_my_domain", default=None) is None

        with Client.scoped_context({"user": {"domain": "gmail.com"}}):
            assert client.get("just_my_domain", default="DEFAULT") == "DEFAULT"

        with Client.scoped_context({"user": {"domain": "prefab.cloud"}}):
            assert client.get("just_my_domain") == "new-version"

    def test_getting_feature_flag_value(self, client):
        assert not client.enabled("flag_with_a_value")
        assert client.get("flag_with_a_value") == "all-features"

    def test_loglevel(self, client):
        assert client.get_loglevel("") == logging.WARNING
        assert client.get_loglevel("app") == logging.ERROR
        assert client.get_loglevel("app.controller") == logging.ERROR
        assert client.get_loglevel("app.controller.hello") == logging.WARNING
        assert client.get_loglevel("app.controller.hello.index") == logging.INFO
        assert client.get_loglevel("app.controller.hello.index.store") == logging.INFO
        assert client.get_loglevel("app.controller.hello.edit") == logging.WARN
