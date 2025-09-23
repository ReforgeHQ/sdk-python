from typing import Optional, Union, TYPE_CHECKING
from datetime import timedelta, date, datetime

import prefab_pb2 as Prefab

if TYPE_CHECKING:
    from .context import Context

NoDefaultProvided = object()
ConfigValueType = Optional[Union[int, float, bool, str, list[str], timedelta, dict]]
ContextDictType = dict[
    str,
    dict[
        str, Union[int, float, bool, str, date, datetime, list[str], Prefab.ConfigValue]
    ],
]
ContextDictOrContext = Union[ContextDictType, "Context"]

PostBodyType = bytes
