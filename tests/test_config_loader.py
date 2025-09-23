from sdk_reforge import Options, ReforgeSDK as Client
import prefab_pb2 as Prefab


class TestConfigLoader:
    def test_calc_config(self):
        options = Options(
            x_datafile="tests/prefab.datafile.json",
            reforge_datasources="LOCAL_ONLY",
            collect_sync_interval=None,
        )
        client = Client(options)
        loader = client.config_sdk().config_loader


    def test_highwater(self):
        client = self.client()
        loader = client.config_sdk().config_loader

        assert loader.highwater_mark == 0
        loader.set(
            Prefab.Config(
                id=1,
                key="sample_int",
                rows=[
                    Prefab.ConfigRow(
                        values=[
                            Prefab.ConditionalValue(value=Prefab.ConfigValue(int=456))
                        ]
                    )
                ],
            ),
            "test",
        )
        assert loader.highwater_mark == 1
        loader.set(
            Prefab.Config(
                id=5,
                key="sample_int",
                rows=[
                    Prefab.ConfigRow(
                        values=[
                            Prefab.ConditionalValue(value=Prefab.ConfigValue(int=456))
                        ]
                    )
                ],
            ),
            "test",
        )
        assert loader.highwater_mark == 5
        loader.set(
            Prefab.Config(
                id=2,
                key="sample_int",
                rows=[
                    Prefab.ConfigRow(
                        values=[
                            Prefab.ConditionalValue(value=Prefab.ConfigValue(int=456))
                        ]
                    )
                ],
            ),
            "test",
        )
        assert loader.highwater_mark == 5

    def test_api_deltas(self):
        client = self.client()
        loader = client.config_sdk().config_loader

        val = Prefab.ConfigValue(int=456)
        config = Prefab.Config(
            id=2,
            key="sample_int",
            rows=[Prefab.ConfigRow(values=[Prefab.ConditionalValue(value=val)])],
        )
        loader.set(config, "test")

        configs = Prefab.Configs()
        configs.configs.append(config)

        assert loader.get_api_deltas() == configs

    def test_loading_tombstone_removes_entries(self):
        client = self.client()
        loader = client.config_sdk().config_loader

        val = Prefab.ConfigValue(int=456)
        config = Prefab.Config(
            id=2,
            key="sample_int",
            rows=[Prefab.ConfigRow(values=[Prefab.ConditionalValue(value=val)])],
        )
        loader.set(config, "test")
        self.assert_correct_config(loader, "sample_int", "int", 456)

        config = Prefab.Config(id=3, key="sample_int", rows=[])
        loader.set(config, "test")

        assert loader.get_api_deltas() == Prefab.Configs()

    @staticmethod
    def assert_correct_config(loader, key, type, value):
        value_from_config = loader.calc_config()[key]["config"].rows[0].values[0].value
        assert value_from_config.WhichOneof("type") == type
        assert getattr(value_from_config, type) == value

    @staticmethod
    def client():
        options = Options(
            x_datafile="tests/prefab.datafile.json",
            reforge_datasources="LOCAL_ONLY",
            collect_sync_interval=None,
        )
        return Client(options)
