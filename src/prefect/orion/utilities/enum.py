from enum import Enum


class AutoEnum(Enum):
    """An enum class that automatically generates values
    from variable names. This guards against common errors
    where variable names are updated but values are not.

    See https://docs.python.org/3/library/enum.html#using-automatic-values

    Example:
            >>> from enum import auto
            >>> class MyEnum(AutoEnum):
            ...     red = auto() # equivalent to red = 'red'
            ...     blue = auto() # equivalent to blue = 'blue'
            ...
    """

    def _generate_next_value_(name, start, count, last_values):
        return name
