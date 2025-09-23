from __future__ import annotations
import functools
import time
from collections.abc import Sequence

from .read_write_lock import ReadWriteLock
from .config_value_unwrapper import ConfigValueUnwrapper
from .context import Context
from ._internal_logging import InternalLogger
from .simple_criterion_evaluators import (
    NumericOperators,
    StringOperators,
    DateOperators,
    SemverOperators,
    RegexMatchOperators,
)
import prefab_pb2 as Prefab

logger = InternalLogger(__name__)


class ConfigResolver:
    def __init__(self, base_client, config_loader):
        self.local_store = None
        self.lock = ReadWriteLock()
        self.base_client = base_client
        self.config_loader = config_loader
        self.project_env_id = 0
        self.default_context = {}
        self.make_local()

    def get(self, key, context=None) -> "Evaluation | None":
        with self.lock.read_locked():
            raw_config = self.raw(key)

        if raw_config is None:
            merged_context = self.evaluation_context(context)
            return Evaluation(
                config=None,
                value=None,
                config_row_index=0,
                value_index=0,
                context=merged_context,
                resolver=self,
            )
        else:
            return self.evaluate(raw_config, context=context)

    def raw(self, key) -> Prefab.ConfigValue | None:
        via_key = self.local_store.get(key)
        if via_key is not None:
            return via_key["config"]
        return None

    def evaluate(self, config, context=None) -> "Evaluation | None":
        return CriteriaEvaluator(
            config,
            project_env_id=self.project_env_id,
            resolver=self,
            base_client=self.base_client,
        ).evaluate(self.evaluation_context(context))

    def evaluation_context(self, context):
        merged_context = Context()
        merged_context.merge_context_dict(self.base_client.global_context.to_dict())
        merged_context.merge_context_dict(self.default_context)
        if Context.get_current():
            merged_context.merge_context_dict(Context.get_current().to_dict())
        if context:
            merged_context.merge_context_dict(
                Context.normalize_context_arg(context).to_dict()
            )
        return merged_context

    def update(self):
        self.make_local()

    def make_local(self):
        with self.lock.write_locked():
            self.local_store = self.config_loader.calc_config()

    @property
    def default_context(self):
        return self._default_context

    @default_context.setter
    def default_context(self, value):
        self._default_context = Context.normalize_context_arg(value).to_dict()


OPS = Prefab.Criterion.CriterionOperator


class CriteriaEvaluator:
    def __init__(self, config, project_env_id, resolver, base_client):
        self.config = config
        self.project_env_id = project_env_id
        self.resolver = resolver
        self.base_client = base_client

    def evaluate(self, props):
        matching_env_row_values = self.matching_environment_row_values()
        default_row_index = 1 if matching_env_row_values else 0
        for value_index, conditional_value in enumerate(matching_env_row_values):
            if self.all_criteria_match(conditional_value, props):
                return Evaluation(
                    self.config,
                    conditional_value.value,
                    value_index,
                    0,
                    props,
                    self.resolver,
                )
        for value_index, conditional_value in enumerate(self.default_row_values()):
            if self.all_criteria_match(conditional_value, props):
                return Evaluation(
                    self.config,
                    conditional_value.value,
                    value_index,
                    default_row_index,
                    props,
                    self.resolver,
                )
        return None

    def all_criteria_match(self, conditional_value, props):
        for criterion in conditional_value.criteria:
            if not self.evaluate_criterion(criterion, props):
                return False
        return True

    def evaluate_criterion(self, criterion, properties):
        if criterion.property_name in ["prefab.current-time", "reforge.current-time"]:
            value_from_properties = int(time.time() * 1000)
        else:
            value_from_properties = properties.get(criterion.property_name)

        deepest_value = ConfigValueUnwrapper.deepest_value(
            criterion.value_to_match, self.config, properties
        )

        if criterion.operator in [OPS.LOOKUP_KEY_IN, OPS.PROP_IS_ONE_OF]:
            return self.one_of(criterion, value_from_properties, properties)
        if criterion.operator in [OPS.LOOKUP_KEY_NOT_IN, OPS.PROP_IS_NOT_ONE_OF]:
            return not self.one_of(criterion, value_from_properties, properties)
        if criterion.operator == OPS.IN_SEG:
            return self.in_segment(criterion, properties)
        if criterion.operator == OPS.NOT_IN_SEG:
            return not self.in_segment(criterion, properties)
        if criterion.operator in StringOperators.SUPPORTED_OPERATORS:
            return StringOperators.evaluate(
                value_from_properties, criterion.operator, deepest_value.unwrap()
            )
        if criterion.operator == OPS.HIERARCHICAL_MATCH:
            return value_from_properties.startswith(criterion.value_to_match.string)
        if criterion.operator == OPS.ALWAYS_TRUE:
            return True
        if criterion.operator in DateOperators.SUPPORTED_OPERATORS:
            return DateOperators.evaluate(
                value_from_properties, criterion.operator, deepest_value.unwrap()
            )
        if criterion.operator in NumericOperators.SUPPORTED_OPERATORS:
            return NumericOperators.evaluate(
                value_from_properties, criterion.operator, deepest_value.unwrap()
            )
        if criterion.operator in RegexMatchOperators.SUPPORTED_OPERATORS:
            return RegexMatchOperators.evaluate(
                value_from_properties, criterion.operator, deepest_value.unwrap()
            )
        if criterion.operator in SemverOperators.SUPPORTED_OPERATORS:
            return SemverOperators.evaluate(
                value_from_properties, criterion.operator, deepest_value.unwrap()
            )

        logger.info(f"Unknown criterion operator {criterion.operator}")
        return False

    @staticmethod
    def negate(negate, value):
        return not value if negate else value

    @staticmethod
    def _ensure_list(value):
        if isinstance(value, list):
            return value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return list(value)  # Convert other sequences to lists
        return [value]  # Wrap everything else in a list

    def one_of(self, criterion, value, properties):
        criterion_value_or_values = ConfigValueUnwrapper.deepest_value(
            criterion.value_to_match, self.config, properties
        ).unwrap()

        criterion_values = self._ensure_list(criterion_value_or_values)
        values = self._ensure_list(value)

        return any(str(v1) == str(v2) for v1 in criterion_values for v2 in values)

    def in_segment(self, criterion, properties):
        return (
            self.resolver.get(criterion.value_to_match.string, context=properties)
            .raw_config_value()
            .bool
        )

    def matching_environment_row_values(self):
        env_rows = [
            row for row in self.config.rows if row.project_env_id == self.project_env_id
        ]
        if env_rows == []:
            return []
        else:
            return env_rows[0].values

    def default_row_values(self):
        env_rows = [
            row for row in self.config.rows if row.project_env_id != self.project_env_id
        ]
        if env_rows == []:
            return []
        else:
            return env_rows[0].values


class Evaluation:
    def __init__(
        self,
        config: Prefab.Config | None,
        value: Prefab.ConfigValue | None,
        value_index: int,
        config_row_index: int,
        context: Context,
        resolver: ConfigResolver,
    ):
        self.config = config
        self.value = value
        self.value_index = value_index
        self.config_row_index = config_row_index
        self.context = context
        self.resolver = resolver

    def unwrapped_value(self):
        return self.deepest_value().unwrap()

    def raw_config_value(self):
        return self.value

    @functools.cache
    def deepest_value(self):
        return ConfigValueUnwrapper.deepest_value(
            self.value, self.config, self.resolver, self.context
        )
