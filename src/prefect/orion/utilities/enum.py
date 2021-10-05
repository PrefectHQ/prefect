from enum import Enum, auto


class AutoEnum(str, Enum):
    """An enum class that automatically generates values
    from variable names. This guards against common errors
    where variable names are updated but values are not.

    In addition, because AutoEnums inherit from `str`, they
    are automatically JSON-serializable.

    See https://docs.python.org/3/library/enum.html#using-automatic-values

    Example:
        ```python
        class MyEnum(AutoEnum):
            RED = AutoEnum.auto() # equivalent to RED = 'RED'
            BLUE = AutoEnum.auto() # equivalent to BLUE = 'BLUE'
        ```
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
