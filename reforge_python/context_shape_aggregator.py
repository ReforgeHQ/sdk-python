from __future__ import annotations

from collections import defaultdict

from .context_shape import ContextShape
import prefab_pb2 as Prefab


class ContextShapeAggregator:
    def __init__(self, max_shapes: int = 1000):
        self.max_fields = max_shapes
        self.field_tuples = set()
        self.dirty = False

    def push(self, context):
        for name, named_context in context.contexts.items():
            for key, value in named_context.data.items():
                if len(self.field_tuples) < self.max_fields:
                    field_tuple = (name, key, ContextShape.field_type_number(value))
                    self.dirty |= field_tuple not in self.field_tuples
                    self.field_tuples.add(field_tuple)

    def flush(self, return_if_not_dirty=False) -> Prefab.ContextShapes | None:
        if return_if_not_dirty or self.dirty:
            to_ship = defaultdict(dict)
            for field_tuple in self.field_tuples:
                to_ship[field_tuple[0]][field_tuple[1]] = field_tuple[2]
            shapes = []
            for name in to_ship.keys():
                shapes.append(Prefab.ContextShape(name=name, field_types=to_ship[name]))
            self.dirty = False
            return Prefab.ContextShapes(shapes=shapes)
        return None
