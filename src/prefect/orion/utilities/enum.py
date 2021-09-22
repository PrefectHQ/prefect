from enum import Enum, auto


class AutoEnum(Enum):
    """An enum class that automatically generates values
    from variable names. This guards against common errors
    where variable names are updated but values are not.

    See https://docs.python.org/3/library/enum.html#using-automatic-values

    Example:
            >>> from enum import auto
            >>> class MyEnum(AutoEnum):
            ...     red = AutoEnum.auto() # equivalent to red = 'red'
            ...     blue = AutoEnum.auto() # equivalent to blue = 'blue'
            ...
    """

    def _generate_next_value_(name, start, count, last_values):
        return name

    @staticmethod
    def auto():
        """
        Exposes `enum.auto()` to avoid requiring a second import to use `AutoEnum`
        """
        return auto()

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.value}"
