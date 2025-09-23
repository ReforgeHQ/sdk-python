from __future__ import annotations

from threading import current_thread

import prefab_cloud_python
from prefab_cloud_python.config_value_wrapper import ConfigValueWrapper
from prefab_pb2 import Context as ProtoContext, ContextSet as ProtoContextSet


class InvalidContextFormatException(Exception):
    "Raised when a provided context is neither a NamedContext nor a dict"

    def __init__(self, context):
        super().__init__(
            "Expected a NamedContext or dict, received a", str(type(context))
        )


class Context:
    def __init__(self, context={}) -> None:
        self.contexts = {}

        if isinstance(context, NamedContext):
            self.contexts[context.name] = context
        elif isinstance(context, dict):
            for name, values in context.items():
                if isinstance(values, dict):
                    self.contexts[str(name)] = NamedContext(name, values)
                else:
                    print(
                        "Prefab contexts should be a dict with a key of the context name and a value of a dict of the context"
                    )
                    self.contexts[""] = self.contexts.get("") or NamedContext("", {})
                    self.contexts[""].merge({name: values})
        elif context is None:
            pass  # empty context
        else:
            raise InvalidContextFormatException(context)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def set(self, key, value):
        self.contexts[str(key)] = NamedContext(key, value)

    def get(self, property_key):
        name_and_key = property_key.split(".", maxsplit=1)

        if len(name_and_key) == 1:
            name = ""
            key = property_key
        else:
            name, key = name_and_key

        if self.contexts.get(name):
            return self.contexts[name].get(key)

    def merge(self, key, value):
        self.contexts[str(key)] = NamedContext(key, data=value)

    def merge_context_dict(self, context):
        for name, nested_context in context.items():
            self.merge(name, nested_context)

        return self

    def clear(self):
        self.contexts = {}

    def to_dict(self):
        d = {}
        for name, named_context in self.contexts.items():
            d[name] = named_context.to_dict()
        return d

    def scope(context):
        if not isinstance(context, prefab_cloud_python.context.Context):
            context = Context(context)
        return ScopedContext(context)

    @staticmethod
    def set_current(context):
        if isinstance(context, prefab_cloud_python.context.Context):
            current_thread().prefab_context = context
        else:
            current_thread().prefab_context = Context(context)

    @staticmethod
    def get_current():
        if (
            "prefab_context" not in dir(current_thread())
            or current_thread().prefab_context is None
        ):
            Context.set_current(Context())
        return current_thread().prefab_context

    @staticmethod
    def merge_with_current(new_context_attributes):
        return Context(Context.get_current().to_dict() | new_context_attributes)

    @staticmethod
    def normalize_context_arg(context):
        if context is None:
            return Context()
        if isinstance(context, dict):
            return Context(context)
        if isinstance(context, Context):
            return context
        raise ValueError(f"unexpected context type - {str(type(context))}")

    def to_proto(self) -> ProtoContextSet:
        return ProtoContextSet(
            contexts=[value.to_proto() for value in self.contexts.values()]
        )


class NamedContext:
    def __init__(self, name, data={}):
        self.name = str(name)
        self.data = data

    def get(self, key):
        return self.data.get(key)

    def merge(self, other={}):
        for key, value in other.items():
            self.data[str(key)] = self.data.get(str(key)) or value

    def to_dict(self):
        return self.data

    def to_proto(self) -> ProtoContext:
        value_dict = {}
        for key, value in self.data.items():
            value_dict[key] = ConfigValueWrapper.wrap(value)
        return ProtoContext(type=self.name, values=value_dict)


class ScopedContext(object):
    def __init__(self, context):
        self.context = context

    def __enter__(self):
        self.old_context = Context.get_current()
        Context.set_current(self.context)

    def __exit__(self, *args):
        Context.set_current(self.old_context)
