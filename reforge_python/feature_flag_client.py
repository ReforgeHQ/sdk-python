from __future__ import annotations
from typing import Optional

from .context import Context
from .constants import NoDefaultProvided, ConfigValueType
from ._internal_logging import InternalLogger

logger = InternalLogger(__name__)


class FeatureFlagClient:
    def __init__(self, base_client):
        self.base_client = base_client

    def feature_is_on(
        self, feature_name, context: Optional[dict | Context] = None
    ) -> bool:
        return self.feature_is_on_for(feature_name, context)

    def feature_is_on_for(
        self, feature_name, context: Optional[dict | Context] = None
    ) -> bool:
        variant = self.base_client.config_client().get(
            feature_name, False, context=context
        )
        return self._is_on(variant)

    def get(
        self,
        feature_name,
        default=NoDefaultProvided,
        context: Optional[dict | Context] = None,
    ) -> ConfigValueType:
        return self._get(feature_name, default=default, context=context)

    def _get(
        self,
        feature_name,
        default=NoDefaultProvided,
        context: Optional[dict | Context] = None,
    ) -> ConfigValueType:
        return self.base_client.config_client().get(
            feature_name, default=default, context=context
        )

    def _is_on(self, variant) -> bool:
        try:
            if variant is None:
                return False
            if isinstance(variant, bool):
                return variant
            return variant.bool
        except Exception:
            logger.info(
                f"is_on methods only work for boolean feature flag variants. This feature flag's variant is '{variant}'. Returning False",
            )
            return False
