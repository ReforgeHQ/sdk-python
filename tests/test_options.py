from sdk_reforge import Options
from sdk_reforge.options import (
    MissingSdkKeyException,
    InvalidSdkKeyException,
    InvalidApiUrlException,
    InvalidStreamUrlException,
)

import os
import pytest

from contextlib import contextmanager


@contextmanager
def extended_env(new_env_vars):
    old_env = os.environ.copy()
    os.environ.update(new_env_vars)
    yield
    os.environ.clear()
    os.environ.update(old_env)


class TestOptionsApiKey:
    def test_valid_api_key_from_input(self):
        options = Options(sdk_key="1-dev-api-key")
        assert options.api_key == "1-dev-api-key"
        assert options.api_key_id == "1"

    def test_valid_api_key_from_env(self):
        with extended_env({"PREFAB_API_KEY": "2-test-api-key"}):
            options = Options()

            assert options.api_key == "2-test-api-key"
            assert options.api_key_id == "2"

    def test_api_key_from_input_overrides_env(self):
        with extended_env({"PREFAB_API_KEY": "2-test-api-key"}):
            options = Options(sdk_key="3-dev-api-key")

            assert options.api_key == "3-dev-api-key"
            assert options.api_key_id == "3"

    def test_missing_sdk_key_error(self):
        with pytest.raises(MissingSdkKeyException) as context:
            Options()

        assert "No SDK key found" in str(context)

    def test_invalid_sdk_key_error(self):
        with pytest.raises(InvalidSdkKeyException) as context:
            Options(sdk_key="bad_sdk_key")
            assert "Invalid SDK key: bad_sdk_key" in str(context)

    def test_api_key_doesnt_matter_local_only_set_in_env(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options(sdk_key="bad_api_key")
            assert options.api_key is None
            assert options.api_key_id == "local"

    def test_api_key_doesnt_matter_local_only(self):
        options = Options(sdk_key="bad_api_key", reforge_datasources="LOCAL_ONLY")
        assert options.api_key is None

    def test_api_key_strips_whitespace(self):
        options = Options(sdk_key="2-test-api-key\n")
        assert options.api_key == "2-test-api-key"

    def test_api_key_strips_whitespace_sourced_from_env(self):
        with extended_env({"PREFAB_API_KEY": " 2-test-api-key\n"}):
            options = Options()
            assert options.api_key == "2-test-api-key"


class TestOptionsApiUrl:
    def test_prefab_api_url_from_env(self):
        with extended_env(
            {
                "PREFAB_API_KEY": "1-api",
                "REFORGE_API_URL": "https://api.dev-prefab.cloud",
            }
        ):
            options = Options()
            assert options.reforge_api_urls == ["https://api.dev-prefab.cloud"]

    def test_api_url_from_input(self):
        with extended_env({"PREFAB_API_KEY": "1-api"}):
            options = Options(reforge_api_urls=["https://api.test-prefab.cloud"])
            assert options.reforge_api_urls == ["https://api.test-prefab.cloud"]

    def test_prefab_api_url_default_fallback(self):
        with extended_env({"PREFAB_API_KEY": "1-api"}):
            options = Options()
            assert options.reforge_api_urls == [
                "https://primary.reforge.com",
                "https://secondary.reforge.com",
            ]

    def test_prefab_api_url_errors_on_invalid_format(self):
        with extended_env({"PREFAB_API_KEY": "1-api"}):
            with pytest.raises(InvalidApiUrlException) as context:
                Options(reforge_api_urls=["httttp://api.prefab.cloud"])

            assert "Invalid API URL found: httttp://api.prefab.cloud" in str(context)

    def test_prefab_api_url_doesnt_matter_local_only_set_in_env(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options(reforge_api_urls=["http://api.prefab.cloud"])
            assert options.reforge_api_urls is None

    def test_prefab_api_url_doesnt_matter_local_only(self):
        options = Options(
            reforge_api_urls=["http://api.prefab.cloud"],
            reforge_datasources="LOCAL_ONLY",
        )
        assert options.reforge_api_urls is None


class TestOptionsStreamUrl:
    def test_prefab_stream_url_from_env(self):
        with extended_env(
            {
                "PREFAB_API_KEY": "1-api",
                "REFORGE_API_URL": "https://api.dev-prefab.cloud",
                "REFORGE_STREAM_URL": "https://s.api.dev-prefab.cloud",
            }
        ):
            options = Options()
            assert options.reforge_stream_urls == ["https://s.api.dev-prefab.cloud"]

    def test_api_url_from_input(self):
        with extended_env({"PREFAB_API_KEY": "1-api"}):
            options = Options(
                reforge_api_urls=["https://api.test-prefab.cloud"],
                reforge_stream_urls=["https://foo.test-prefab.cloud"],
            )
            assert options.reforge_stream_urls == ["https://foo.test-prefab.cloud"]

    def test_prefab_api_url_default_fallback(self):
        with extended_env({"PREFAB_API_KEY": "1-api"}):
            options = Options()
            assert options.reforge_stream_urls == ["https://stream.reforge.com"]

    def test_prefab_api_url_errors_on_invalid_format(self):
        with extended_env({"PREFAB_API_KEY": "1-api"}):
            with pytest.raises(InvalidStreamUrlException) as context:
                Options(reforge_stream_urls=["httttp://stream.prefab.cloud"])

            assert "Invalid Stream URL found: httttp://stream.prefab.cloud" in str(
                context
            )

    def test_prefab_api_url_doesnt_matter_local_only_set_in_env(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options(reforge_stream_urls=["http://stream.prefab.cloud"])
            assert options.reforge_stream_urls is None

    def test_prefab_api_url_doesnt_matter_local_only(self):
        options = Options(
            reforge_stream_urls=["http://stream.prefab.cloud"],
            reforge_datasources="LOCAL_ONLY",
        )
        assert options.reforge_stream_urls is None


class TestOptionsOnNoDefault:
    def test_defaults_to_raise(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options()
            assert options.on_no_default == "RAISE"

    def test_returns_return_none_if_given(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options(on_no_default="RETURN_NONE")
            assert options.on_no_default == "RETURN_NONE"

    def test_returns_raise_for_any_other_input(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options(on_no_default="WHATEVER")
            assert options.on_no_default == "RAISE"


class TestOptionsOnConnectionFailure:
    def test_defaults_to_return(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options()
            assert options.on_connection_failure == "RETURN"

    def test_returns_raise_if_given(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options(on_connection_failure="RAISE")
            assert options.on_connection_failure == "RAISE"

    def test_returns_return_for_any_other_input(self):
        with extended_env({"REFORGE_DATASOURCES": "LOCAL_ONLY"}):
            options = Options(on_connection_failure="WHATEVER")
            assert options.on_connection_failure == "RETURN"
