from collections import namedtuple
from datetime import datetime, timezone, timedelta

import pytest
import prefab_pb2 as Prefab
from sdk_reforge.simple_criterion_evaluators import (
    NumericOperators,
    StringOperators,
    DateOperators,
    SemverOperators,
    RegexMatchOperators,
)


class TestNumericComparisons:
    NumberTestCase = namedtuple(
        "NumberTestCase",  # Kept your original name
        [
            "description",
            "contextValue",
            "operator",
            "criterionValue",
            "expectedMatchResult",
        ],
    )

    @pytest.mark.parametrize(
        "case",
        [
            NumberTestCase(
                "2 is greater than 1",
                2.1,
                Prefab.Criterion.CriterionOperator.PROP_GREATER_THAN,
                1.1,
                True,
            ),
            NumberTestCase(
                "2 is not greater than 2",
                2,
                Prefab.Criterion.CriterionOperator.PROP_GREATER_THAN,
                2,
                False,
            ),
            NumberTestCase(
                "1 is not greater than 2",
                1,
                Prefab.Criterion.CriterionOperator.PROP_GREATER_THAN,
                2,
                False,
            ),
            NumberTestCase(
                "2 is greater than or equal to 1",
                2.1,
                Prefab.Criterion.CriterionOperator.PROP_GREATER_THAN_OR_EQUAL,
                1.1,
                True,
            ),
            NumberTestCase(
                "2 is greater than or equal to 2",
                2,
                Prefab.Criterion.CriterionOperator.PROP_GREATER_THAN_OR_EQUAL,
                2,
                True,
            ),
            NumberTestCase(
                "1 is not greater than or equal to 2",
                1,
                Prefab.Criterion.CriterionOperator.PROP_GREATER_THAN_OR_EQUAL,
                2,
                False,
            ),  #
            NumberTestCase(
                "1.1 is less than 2",
                1.1,
                Prefab.Criterion.CriterionOperator.PROP_LESS_THAN,
                2,
                True,
            ),
            NumberTestCase(
                "2 is not less than 2",
                2,
                Prefab.Criterion.CriterionOperator.PROP_LESS_THAN,
                2,
                False,
            ),
            NumberTestCase(
                "2 is not less than 2",
                2,
                Prefab.Criterion.CriterionOperator.PROP_LESS_THAN,
                1,
                False,
            ),
            NumberTestCase(
                "1.1 is less than or equal to 2",
                1.1,
                Prefab.Criterion.CriterionOperator.PROP_LESS_THAN_OR_EQUAL,
                2,
                True,
            ),
            NumberTestCase(
                "2 is less than or equal to 2",
                2,
                Prefab.Criterion.CriterionOperator.PROP_LESS_THAN_OR_EQUAL,
                2,
                True,
            ),
            NumberTestCase(
                "2 is not less than or equal to 1",
                2,
                Prefab.Criterion.CriterionOperator.PROP_LESS_THAN_OR_EQUAL,
                1,
                False,
            ),
        ],
        ids=lambda c: c.description,
    )
    def test_operator(self, case: NumberTestCase) -> None:
        result = NumericOperators.evaluate(
            case.contextValue, case.operator, case.criterionValue
        )
        assert result == case.expectedMatchResult


class TestStringOperations:
    StringTestCase = namedtuple(
        "StringTestCase",  # Kept your original name
        [
            "description",
            "contextValue",
            "operator",
            "criterionValue",
            "expectedMatchResult",
        ],
    )

    @pytest.mark.parametrize(
        "case",
        [
            StringTestCase(
                "foobar starts with foo is true",
                "foobar",
                Prefab.Criterion.CriterionOperator.PROP_STARTS_WITH_ONE_OF,
                ["foo", "abc"],
                True,
            ),
            StringTestCase(
                "foobar does not start with foo is false",
                "foobar",
                Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_START_WITH_ONE_OF,
                ["foo", "abc"],
                False,
            ),
            StringTestCase(
                "foobar ends with bar is true",
                "foobar",
                Prefab.Criterion.CriterionOperator.PROP_ENDS_WITH_ONE_OF,
                ["abc", "bar"],
                True,
            ),
            StringTestCase(
                "foobar does not end with bar is false",
                "foobar",
                Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_END_WITH_ONE_OF,
                ["abc", "bar"],
                False,
            ),
            StringTestCase(
                "foobar contains oo is true",
                "foobar",
                Prefab.Criterion.CriterionOperator.PROP_CONTAINS_ONE_OF,
                ["oo", "abc"],
                True,
            ),
            StringTestCase(
                "foobar does not contain oo is false",
                "foobar",
                Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_CONTAIN_ONE_OF,
                ["oo", "abc"],
                False,
            ),
        ],
        ids=lambda c: c.description,
    )
    def test_operator(self, case: StringTestCase) -> None:
        result = StringOperators.evaluate(
            case.contextValue, case.operator, case.criterionValue
        )
        assert result == case.expectedMatchResult


class TestDateOperations:
    DateTestCase = namedtuple(
        "DateTestCase",
        [
            "description",
            "contextValue",
            "operator",
            "criterionValue",
            "expectedMatchResult",
        ],
    )

    # Reference timestamps for testing
    REFERENCE_TIME = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    REFERENCE_MILLIS = int(REFERENCE_TIME.timestamp() * 1000)

    ONE_HOUR_MILLIS = 3600 * 1000
    ONE_DAY_MILLIS = 24 * ONE_HOUR_MILLIS

    @pytest.mark.parametrize(
        "case",
        [
            # Tests with RFC3339 strings
            DateTestCase(
                "RFC3339 date before reference time returns true",
                "2023-12-31T12:00:00Z",
                Prefab.Criterion.CriterionOperator.PROP_BEFORE,
                REFERENCE_MILLIS,
                True,
            ),
            DateTestCase(
                "RFC3339 date after reference time returns false",
                "2023-12-31T12:00:00Z",
                Prefab.Criterion.CriterionOperator.PROP_AFTER,
                REFERENCE_MILLIS,
                False,
            ),
            DateTestCase(
                "RFC3339 date with timezone offset before reference returns true",
                "2023-12-31T14:00:00+02:00",  # Same as 12:00 UTC
                Prefab.Criterion.CriterionOperator.PROP_BEFORE,
                REFERENCE_MILLIS,
                True,
            ),
            DateTestCase(
                "RFC3339 exact match with before returns false",
                "2024-01-01T12:00:00Z",
                Prefab.Criterion.CriterionOperator.PROP_BEFORE,
                REFERENCE_MILLIS,
                False,
            ),
            # Tests with millisecond timestamps
            DateTestCase(
                "Millisecond timestamp before reference returns true",
                REFERENCE_MILLIS - ONE_DAY_MILLIS,
                Prefab.Criterion.CriterionOperator.PROP_BEFORE,
                REFERENCE_MILLIS,
                True,
            ),
            DateTestCase(
                "Millisecond timestamp after reference returns true",
                REFERENCE_MILLIS + ONE_HOUR_MILLIS,
                Prefab.Criterion.CriterionOperator.PROP_AFTER,
                REFERENCE_MILLIS,
                True,
            ),
            # Tests with Datetime instances
            DateTestCase(
                "datetime before reference returns true",
                REFERENCE_TIME - timedelta(days=1),
                Prefab.Criterion.CriterionOperator.PROP_BEFORE,
                REFERENCE_MILLIS,
                True,
            ),
            # Tests with Date instances (will assume midnight)
            DateTestCase(
                "datetime before reference returns true",
                (REFERENCE_TIME - timedelta(days=1)).date(),
                Prefab.Criterion.CriterionOperator.PROP_BEFORE,
                REFERENCE_MILLIS,
                True,
            ),
            # Edge cases and invalid inputs
            DateTestCase(
                "Invalid RFC3339 format returns false",
                "2024-13-01T12:00:00Z",  # Invalid month
                Prefab.Criterion.CriterionOperator.PROP_BEFORE,
                REFERENCE_MILLIS,
                False,
            ),
            DateTestCase(
                "Non-supported operator returns false",
                "2024-01-01T12:00:00Z",
                "UNSUPPORTED_OPERATOR",
                REFERENCE_MILLIS,
                False,
            ),
            DateTestCase(
                "Invalid millisecond timestamp format returns false",
                "not_a_number",
                Prefab.Criterion.CriterionOperator.PROP_BEFORE,
                REFERENCE_MILLIS,
                False,
            ),
        ],
        ids=lambda c: c.description,
    )
    def test_operator(self, case: DateTestCase) -> None:
        result = DateOperators.evaluate(
            case.contextValue, case.operator, case.criterionValue
        )
        assert result == case.expectedMatchResult


class TestSemverOperators:
    OperatorTestCase = namedtuple(
        "OperatorTestCase",
        [
            "description",
            "context_value",
            "operator",
            "criterion_value",
            "expected_result",
        ],
    )

    @pytest.mark.parametrize(
        "case",
        [
            # Valid semver comparisons
            OperatorTestCase(
                "equal versions return true",
                "1.2.3",
                Prefab.Criterion.CriterionOperator.PROP_SEMVER_EQUAL,
                "1.2.3",
                True,
            ),
            OperatorTestCase(
                "equal versions with prerelease return true",
                "1.2.3-alpha",
                Prefab.Criterion.CriterionOperator.PROP_SEMVER_EQUAL,
                "1.2.3-alpha",
                True,
            ),
            OperatorTestCase(
                "greater than comparison returns true",
                "2.0.0",
                Prefab.Criterion.CriterionOperator.PROP_SEMVER_GREATER_THAN,
                "1.9.9",
                True,
            ),
            OperatorTestCase(
                "less than comparison returns true",
                "1.9.9",
                Prefab.Criterion.CriterionOperator.PROP_SEMVER_LESS_THAN,
                "2.0.0",
                True,
            ),
            # Invalid versions
            OperatorTestCase(
                "invalid context value returns false",
                "not.a.version",
                Prefab.Criterion.CriterionOperator.PROP_SEMVER_EQUAL,
                "1.0.0",
                False,
            ),
            OperatorTestCase(
                "invalid criterion value returns false",
                "1.0.0",
                Prefab.Criterion.CriterionOperator.PROP_SEMVER_EQUAL,
                "not.a.version",
                False,
            ),
            OperatorTestCase(
                "both invalid versions return false",
                "invalid1",
                Prefab.Criterion.CriterionOperator.PROP_SEMVER_EQUAL,
                "invalid2",
                False,
            ),
            # Unsupported operator
            OperatorTestCase(
                "unsupported operator returns false",
                "1.0.0",
                "UNSUPPORTED_OPERATOR",
                "1.0.0",
                False,
            ),
        ],
        ids=lambda c: c.description,
    )
    def test_operator(self, case: OperatorTestCase) -> None:
        result = SemverOperators.evaluate(
            case.context_value, case.operator, case.criterion_value
        )
        assert result == case.expected_result


class TestRegexMatchOperators:
    RegexTestCase = namedtuple(
        "RegexTestCase",
        [
            "description",
            "context_value",
            "operator",
            "criterion_value",
            "expected_result",
        ],
    )

    @pytest.mark.parametrize(
        "case",
        [
            # Basic matching
            RegexTestCase(
                "simple regex match returns true",
                "hello world",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                "world",
                True,
            ),
            RegexTestCase(
                "simple regex non-match returns false",
                "hello world",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                "universe",
                False,
            ),
            RegexTestCase(
                "does not match returns true for non-matching regex",
                "hello world",
                Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_MATCH,
                "universe",
                True,
            ),
            # Pattern features
            RegexTestCase(
                "match with wildcard returns true",
                "hello world",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                "hel+o",
                True,
            ),
            RegexTestCase(
                "match with character class returns true",
                "hello123",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                r"\d+",
                True,
            ),
            RegexTestCase(
                "match with start anchor returns false if not at start",
                "hello world",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                "^world",
                False,
            ),
            # Invalid patterns
            RegexTestCase(
                "invalid regex pattern returns false",
                "hello world",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                "[unclosed",
                False,
            ),
            RegexTestCase(
                "invalid regex with does_not_match returns false",
                "hello world",
                Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_MATCH,
                "[unclosed",
                False,
            ),
            # Non-string inputs
            RegexTestCase(
                "numeric context value returns false",
                123,
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                r"\d+",
                False,
            ),
            RegexTestCase(
                "numeric pattern returns false",
                "123",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                123,
                False,
            ),
            # Empty strings
            RegexTestCase(
                "empty context value can still match",
                "",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                "^$",
                True,
            ),
            RegexTestCase(
                "empty pattern is valid regex",
                "hello",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                "",
                True,
            ),
            # Special cases
            RegexTestCase(
                "None context value returns false",
                None,
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                ".*",
                False,
            ),
            RegexTestCase(
                "None pattern returns false",
                "hello",
                Prefab.Criterion.CriterionOperator.PROP_MATCHES,
                None,
                False,
            ),
        ],
        ids=lambda c: c.description,
    )
    def test_operator(self, case: RegexTestCase) -> None:
        result = RegexMatchOperators.evaluate(
            case.context_value, case.operator, case.criterion_value
        )
        assert result == case.expected_result
