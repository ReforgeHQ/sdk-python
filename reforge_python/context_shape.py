MAPPING = {int: 1, str: 2, float: 4, bool: 5, list: 10, dict: 16}


class ContextShape:
    @staticmethod
    def field_type_number(value):
        return MAPPING.get(type(value), 2)  # default to string type
