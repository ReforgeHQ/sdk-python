from __future__ import annotations
import re
from typing import Optional


class SemanticVersion:
    _SEMVER_PATTERN = re.compile(
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        prerelease: str = "",
        build_metadata: str = "",
    ):
        self._major = major
        self._minor = minor
        self._patch = patch
        self._prerelease = prerelease
        self._build_metadata = build_metadata

    @staticmethod
    def parse_quietly(version: str) -> Optional[SemanticVersion]:
        """Attempts to parse a version string, returning None if parsing fails."""
        try:
            return SemanticVersion.parse(version)
        except ValueError:
            return None

    @staticmethod
    def parse(version: str) -> SemanticVersion:
        """Creates a new SemanticVersion from a version string."""
        if not version:
            raise ValueError("version string cannot be empty")

        match = SemanticVersion._SEMVER_PATTERN.match(version)
        if not match:
            raise ValueError(f"invalid semantic version format: {version}")

        matches = match.groupdict()
        try:
            major = int(matches["major"])
            minor = int(matches["minor"])
            patch = int(matches["patch"])
        except ValueError as e:
            raise ValueError(f"invalid version number format: {str(e)}")

        return SemanticVersion(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=matches["prerelease"] or "",
            build_metadata=matches["buildmetadata"] or "",
        )

    @property
    def major(self) -> int:
        return self._major

    @property
    def minor(self) -> int:
        return self._minor

    @property
    def patch(self) -> int:
        return self._patch

    @property
    def prerelease(self) -> str:
        return self._prerelease

    @property
    def build_metadata(self) -> str:
        return self._build_metadata

    def _compare_prerelease_identifiers(self, id1: str, id2: str) -> int:
        """Compare two prerelease identifiers according to semver rules."""
        # If both are numeric
        if id1.isdigit() and id2.isdigit():
            num1, num2 = int(id1), int(id2)
            return 1 if num1 > num2 else (-1 if num1 < num2 else 0)

        # If one is numeric
        if id1.isdigit():
            return -1  # Numeric identifiers have lower precedence
        if id2.isdigit():
            return 1

        # Neither is numeric, compare as strings
        return 1 if id1 > id2 else (-1 if id1 < id2 else 0)

    def _compare_prerelease(self, other: SemanticVersion) -> int:
        """Compare prerelease strings according to semver rules."""
        if not self.prerelease and not other.prerelease:
            return 0
        if not self.prerelease:
            return 1
        if not other.prerelease:
            return -1

        self_ids = self.prerelease.split(".")
        other_ids = other.prerelease.split(".")

        for id1, id2 in zip(self_ids, other_ids):
            result = self._compare_prerelease_identifiers(id1, id2)
            if result != 0:
                return result

        # If all identifiers match up to the length of the shorter one,
        # the longer one is greater
        return len(self_ids) - len(other_ids)

    def compare(self, other: SemanticVersion) -> int:
        """
        Implements comparison between two semantic versions
        Returns -1 if self < other, 0 if self == other, and 1 if self > other
        """
        if self.major != other.major:
            return 1 if self.major > other.major else -1

        if self.minor != other.minor:
            return 1 if self.minor > other.minor else -1

        if self.patch != other.patch:
            return 1 if self.patch > other.patch else -1

        return self._compare_prerelease(other)

    def __str__(self) -> str:
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            result += f"-{self.prerelease}"
        if self.build_metadata:
            result += f"+{self.build_metadata}"
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
            # Build metadata is ignored in equality checks
        )

    def __lt__(self, other: SemanticVersion) -> bool:
        return self.compare(other) < 0

    def __le__(self, other: SemanticVersion) -> bool:
        return self.compare(other) <= 0

    def __gt__(self, other: SemanticVersion) -> bool:
        return self.compare(other) > 0

    def __ge__(self, other: SemanticVersion) -> bool:
        return self.compare(other) >= 0
