from sdk_reforge.yaml_parser import YamlParser
from sdk_reforge.config_parser import ConfigParser
import os

TEST_FILENAME = "yaml_parser_test.yml"

VALID_CONTENTS = """
---
name: "michael"
"""

INVALID_CONTENTS = """
hello
"""


class TestYamlParser:
    def test_valid_file(self):
        with open(TEST_FILENAME, "w") as f:
            f.write(VALID_CONTENTS)

        parser = YamlParser(TEST_FILENAME)
        expected_data = ConfigParser.parse("name", "michael", {}, TEST_FILENAME)
        assert parser.data == expected_data
        os.remove(TEST_FILENAME)

    def test_invalid_file(self):
        with open(TEST_FILENAME, "w") as f:
            f.write(INVALID_CONTENTS)

        parser = YamlParser(TEST_FILENAME)
        assert parser.data == {}
        os.remove(TEST_FILENAME)

    def test_non_existent_file(self):
        parser = YamlParser(TEST_FILENAME)
        assert parser.data == {}
