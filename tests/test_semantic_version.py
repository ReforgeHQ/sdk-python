from collections import namedtuple
import pytest

from sdk_reforge.semantic_version import SemanticVersion


class TestSemanticVersion:
    VersionTestCase = namedtuple(
        "VersionTestCase", ["description", "input", "expected_result"]
    )

    ComparisonTestCase = namedtuple(
        "ComparisonTestCase", ["description", "version1", "version2", "expected_result"]
    )

    @pytest.mark.parametrize(
        "case",
        [
            VersionTestCase(
                "basic version parse succeeds",
                "1.2.3",
                {
                    "major": 1,
                    "minor": 2,
                    "patch": 3,
                    "prerelease": "",
                    "build_metadata": "",
                },
            ),
            VersionTestCase(
                "version with prerelease parse succeeds",
                "1.2.3-alpha.1",
                {
                    "major": 1,
                    "minor": 2,
                    "patch": 3,
                    "prerelease": "alpha.1",
                    "build_metadata": "",
                },
            ),
            VersionTestCase(
                "version with build metadata parse succeeds",
                "1.2.3+build.123",
                {
                    "major": 1,
                    "minor": 2,
                    "patch": 3,
                    "prerelease": "",
                    "build_metadata": "build.123",
                },
            ),
            VersionTestCase(
                "version with prerelease and build metadata parse succeeds",
                "1.2.3-alpha.1+build.123",
                {
                    "major": 1,
                    "minor": 2,
                    "patch": 3,
                    "prerelease": "alpha.1",
                    "build_metadata": "build.123",
                },
            ),
            VersionTestCase(
                "version with zero values parse succeeds",
                "0.0.0",
                {
                    "major": 0,
                    "minor": 0,
                    "patch": 0,
                    "prerelease": "",
                    "build_metadata": "",
                },
            ),
        ],
        ids=lambda c: c.description,
    )
    def test_version_parsing(self, case: VersionTestCase) -> None:
        version = SemanticVersion.parse(case.input)
        assert version.major == case.expected_result["major"]
        assert version.minor == case.expected_result["minor"]
        assert version.patch == case.expected_result["patch"]
        assert version.prerelease == case.expected_result["prerelease"]
        assert version.build_metadata == case.expected_result["build_metadata"]

    @pytest.mark.parametrize(
        "case",
        [
            VersionTestCase("empty string returns None", "", None),
            VersionTestCase("invalid format returns None", "1.2", None),
            VersionTestCase("invalid numbers returns None", "1.2.a", None),
            VersionTestCase("invalid prerelease format returns None", "1.2.3-", None),
            VersionTestCase(
                "invalid build metadata format returns None", "1.2.3+", None
            ),
        ],
        ids=lambda c: c.description,
    )
    def test_parse_quietly_invalid_versions(self, case: VersionTestCase) -> None:
        result = SemanticVersion.parse_quietly(case.input)
        assert result == case.expected_result

    @pytest.mark.parametrize(
        "case",
        [
            ComparisonTestCase("equal versions compare as equal", "1.2.3", "1.2.3", 0),
            ComparisonTestCase(
                "higher major version compares greater", "2.0.0", "1.2.3", 1
            ),
            ComparisonTestCase(
                "lower major version compares less", "1.2.3", "2.0.0", -1
            ),
            ComparisonTestCase(
                "higher minor version compares greater", "1.3.0", "1.2.3", 1
            ),
            ComparisonTestCase(
                "higher patch version compares greater", "1.2.4", "1.2.3", 1
            ),
            ComparisonTestCase(
                "prerelease version compares less than release",
                "1.2.3-alpha",
                "1.2.3",
                -1,
            ),
            ComparisonTestCase(
                "build metadata doesn't affect comparison",
                "1.2.3+build.1",
                "1.2.3+build.2",
                0,
            ),
            ComparisonTestCase(
                "prerelease ordering is correct", "1.2.3-alpha.2", "1.2.3-alpha.1", 1
            ),
            ComparisonTestCase(
                "alpha.1 comes before beta.1", "1.0.0-alpha.1", "1.0.0-beta.1", -1
            ),
        ],
        ids=lambda c: c.description,
    )
    def test_version_comparison(self, case: ComparisonTestCase) -> None:
        version1 = SemanticVersion.parse(case.version1)
        version2 = SemanticVersion.parse(case.version2)
        assert version1.compare(version2) == case.expected_result

    def test_sorting(self) -> None:
        versions = [
            "2.0.0",
            "1.0.0",
            "1.1.0",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
        ]

        # Create SemanticVersion objects
        version_objects = [SemanticVersion.parse(v) for v in versions]

        # Sort them
        sorted_versions = sorted(version_objects)

        # Expected order after sorting
        expected_order = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
            "1.1.0",
            "2.0.0",
        ]

        assert [str(v) for v in sorted_versions] == expected_order

    def test_equality(self) -> None:
        version1 = SemanticVersion.parse("1.2.3-alpha+build.1")
        version2 = SemanticVersion.parse("1.2.3-alpha+build.2")
        version3 = SemanticVersion.parse("1.2.3-beta+build.1")

        # Same version with different build metadata should be equal
        assert version1 == version2
        # Different prerelease versions should not be equal
        assert version1 != version3
        # Non-SemanticVersion comparison should return NotImplemented
        assert version1.__eq__("1.2.3") is NotImplemented
