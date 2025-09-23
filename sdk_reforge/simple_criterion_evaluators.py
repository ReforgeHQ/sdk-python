import re
from datetime import datetime, date, timezone
from typing import Callable, Mapping, FrozenSet, Union, Optional
import prefab_pb2 as Prefab
from types import MappingProxyType
from numbers import Real  # includes both int and float

from sdk_reforge.semantic_version import SemanticVersion


def negate(should_negate: bool, value: bool) -> bool:
    return not value if should_negate else value


class NumericOperators:
    """Handles numeric comparisons for criterion evaluation."""

    _COMPARE_TO_EVAL: Mapping[
        Prefab.Criterion.CriterionOperator.ValueType, Callable[[int], bool]
    ] = MappingProxyType(
        {
            Prefab.Criterion.CriterionOperator.PROP_GREATER_THAN: lambda v: v > 0,
            Prefab.Criterion.CriterionOperator.PROP_GREATER_THAN_OR_EQUAL: lambda v: v
            >= 0,
            Prefab.Criterion.CriterionOperator.PROP_LESS_THAN: lambda v: v < 0,
            Prefab.Criterion.CriterionOperator.PROP_LESS_THAN_OR_EQUAL: lambda v: v
            <= 0,
        }
    )

    SUPPORTED_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(_COMPARE_TO_EVAL.keys())

    @staticmethod
    def evaluate(
        context_value: Real,
        operator: Prefab.Criterion.CriterionOperator.ValueType,
        criterion_value: Real,
    ) -> bool:
        """
        Evaluates a numeric comparison between two values.

        Args:
            context_value: The value from context
            operator: The comparison operator to apply
            criterion_value: The value from the criterion

        Returns:
            True if the comparison succeeds, False otherwise
        """
        if not (isinstance(criterion_value, Real) and isinstance(context_value, Real)):
            return False

        comparison_result = NumericOperators._compare(context_value, criterion_value)
        return NumericOperators._COMPARE_TO_EVAL[operator](comparison_result)

    @staticmethod
    def _compare(a: Real, b: Real) -> int:
        """Compare two numbers, returning -1, 0, or 1."""
        if a < b:
            return -1
        elif a > b:
            return 1
        return 0


class StringOperators:
    """Handles string comparisons for criterion evaluation."""

    # Group operators by their base operation
    _CONTAINS_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(
        {
            Prefab.Criterion.CriterionOperator.PROP_CONTAINS_ONE_OF,
            Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_CONTAIN_ONE_OF,
        }
    )

    _STARTS_WITH_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(
        {
            Prefab.Criterion.CriterionOperator.PROP_STARTS_WITH_ONE_OF,
            Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_START_WITH_ONE_OF,
        }
    )

    _ENDS_WITH_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(
        {
            Prefab.Criterion.CriterionOperator.PROP_ENDS_WITH_ONE_OF,
            Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_END_WITH_ONE_OF,
        }
    )

    SUPPORTED_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(_CONTAINS_OPERATORS | _STARTS_WITH_OPERATORS | _ENDS_WITH_OPERATORS)

    _NEGATIVE_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(
        {
            Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_CONTAIN_ONE_OF,
            Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_START_WITH_ONE_OF,
            Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_END_WITH_ONE_OF,
        }
    )

    _STRING_OPERATIONS: MappingProxyType[
        Prefab.Criterion.CriterionOperator.ValueType, Callable[[str, str], bool]
    ] = MappingProxyType(
        {op: lambda s, x: x in s for op in _CONTAINS_OPERATORS}
        | {op: str.startswith for op in _STARTS_WITH_OPERATORS}
        | {op: str.endswith for op in _ENDS_WITH_OPERATORS}
    )

    @staticmethod
    def evaluate(
        context_value: str,
        operator: Prefab.Criterion.CriterionOperator.ValueType,
        criterion_value: list[str],
    ) -> bool:
        if not (isinstance(context_value, str) and isinstance(criterion_value, list)):
            return False

        operation = StringOperators._STRING_OPERATIONS[operator]
        negative = operator in StringOperators._NEGATIVE_OPERATORS

        return negate(
            negative,
            any(
                operation(str(context_value), test_value)
                for test_value in criterion_value
            ),
        )


class DateOperators:
    """Handles date comparisons for criterion evaluation."""

    SUPPORTED_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(
        {
            Prefab.Criterion.CriterionOperator.PROP_BEFORE,
            Prefab.Criterion.CriterionOperator.PROP_AFTER,
        }
    )

    @staticmethod
    def evaluate(
        context_value: Union[str, Real, datetime, date],
        operator: Prefab.Criterion.CriterionOperator.ValueType,
        criterion_value: int,
    ) -> bool:
        if not (
            isinstance(context_value, (str, Real, datetime, date))
            and isinstance(criterion_value, int)
        ):
            return False

        try:
            # Convert context_value to milliseconds since epoch
            if isinstance(context_value, str):
                # Handle RFC3339 string
                # Replace 'Z' with '+00:00' for compatibility with fromisoformat
                if context_value.endswith("Z"):
                    context_value = context_value[:-1] + "+00:00"
                dt = datetime.fromisoformat(context_value)
                context_millis = int(dt.timestamp() * 1000)
            elif isinstance(context_value, datetime):
                context_millis = int(context_value.timestamp() * 1000)
            elif isinstance(context_value, date):
                context_millis = (
                    int(
                        datetime.combine(
                            context_value, datetime.min.time(), timezone.utc
                        ).timestamp()
                    )
                    * 1000
                )
            else:
                context_millis = int(float(context_value))

            # Perform comparison based on operator
            if operator == Prefab.Criterion.CriterionOperator.PROP_BEFORE:
                return context_millis < criterion_value
            elif operator == Prefab.Criterion.CriterionOperator.PROP_AFTER:
                return context_millis > criterion_value
            else:
                return False

        except (ValueError, TypeError):
            return False


class SemverOperators:
    """Handles semver comparisons for criterion evaluation."""

    SUPPORTED_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(
        {
            Prefab.Criterion.CriterionOperator.PROP_SEMVER_EQUAL,
            Prefab.Criterion.CriterionOperator.PROP_SEMVER_GREATER_THAN,
            Prefab.Criterion.CriterionOperator.PROP_SEMVER_LESS_THAN,
        }
    )

    @staticmethod
    def evaluate(
        context_value: str,
        operator: Prefab.Criterion.CriterionOperator.ValueType,
        criterion_value: str,
    ) -> bool:
        # Parse both versions, return False if either parse fails
        context_semver = SemanticVersion.parse_quietly(context_value)
        criterion_semver = SemanticVersion.parse_quietly(criterion_value)

        if context_semver is None or criterion_semver is None:
            return False

        if operator == Prefab.Criterion.CriterionOperator.PROP_SEMVER_EQUAL:
            return context_semver == criterion_semver

        if operator == Prefab.Criterion.CriterionOperator.PROP_SEMVER_GREATER_THAN:
            return context_semver > criterion_semver

        if operator == Prefab.Criterion.CriterionOperator.PROP_SEMVER_LESS_THAN:
            return context_semver < criterion_semver

        return False  # Unsupported operator


class RegexMatchOperators:
    """Handles regex matching comparisons for criterion evaluation."""

    SUPPORTED_OPERATORS: FrozenSet[
        Prefab.Criterion.CriterionOperator.ValueType
    ] = frozenset(
        {
            Prefab.Criterion.CriterionOperator.PROP_MATCHES,
            Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_MATCH,
        }
    )

    @staticmethod
    def _compile_pattern(pattern: str) -> Optional[re.Pattern]:
        """
        Attempts to compile a regex pattern, returning None if compilation fails.
        """
        try:
            return re.compile(pattern)
        except (re.error, TypeError):
            return None

    @staticmethod
    def evaluate(
        context_value: str,
        operator: Prefab.Criterion.CriterionOperator.ValueType,
        criterion_value: str,
    ) -> bool:
        # Handle non-string inputs
        if not isinstance(context_value, str) or not isinstance(criterion_value, str):
            return False

        # Try to compile the pattern
        pattern = RegexMatchOperators._compile_pattern(criterion_value)
        if pattern is None:
            return False

        # Perform the match
        try:
            matches = bool(pattern.search(context_value))
            return negate(
                operator == Prefab.Criterion.CriterionOperator.PROP_DOES_NOT_MATCH,
                matches,
            )
        except (re.error, TypeError):
            return False
