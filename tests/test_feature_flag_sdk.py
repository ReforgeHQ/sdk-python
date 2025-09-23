from prefab_cloud_python import Options, Client

default = "default"


class TestFeatureFlagClient:
    def test_feature_is_on(self):
        ff_client = self.build_client()

        assert not ff_client.feature_is_on("something-that-doesnt-exist")
        assert not ff_client.feature_is_on("disabled_flag")
        assert ff_client.feature_is_on("enabled_flag")
        assert not ff_client.feature_is_on("flag_with_a_value")

    def test_feature_is_on_for(self):
        ff_client = self.build_client()

        assert not ff_client.feature_is_on_for(
            "something-that-doesnt-exist", context={"user": {"key": "not-included"}}
        )
        assert not ff_client.feature_is_on_for(
            "user_key_match", context={"user": {"key": "not-included"}}
        )
        assert ff_client.feature_is_on_for(
            "user_key_match", context={"user": {"key": "abc123"}}
        )
        assert ff_client.feature_is_on_for(
            "user_key_match", context={"user": {"key": "xyz987"}}
        )

    def test_get(self):
        ff_client = self.build_client()

        assert ff_client.get("something-that-doesnt-exist", default=None) is None
        assert not ff_client.get("disabled_flag")
        assert ff_client.get("enabled_flag")
        assert ff_client.get("flag_with_a_value") == "all-features"

        assert ff_client.get("something-that-doesnt-exist", default=default) == default
        assert not ff_client.get("disabled_flag", default=default)
        assert ff_client.get("enabled_flag", default=default)
        assert ff_client.get("flag_with_a_value", default=default) == "all-features"

    @staticmethod
    def build_client():
        options = Options(
            prefab_config_classpath_dir="tests",
            prefab_envs="unit_tests",
            prefab_datasources="LOCAL_ONLY",
        )
        client = Client(options)
        return client.feature_flag_client()
