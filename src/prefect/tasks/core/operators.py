"""
The tasks in this module can be used to represent builtin operations, including math,
indexing, and logical comparisons.

In general, users will not instantiate these tasks by hand; they will automatically be
applied when users apply inline Python operators to a task and another value.
"""

from typing import Any

from prefect import Task


class GetItem(Task):
    """
    Helper task that retrieves a specific index of an upstream task's result.

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, task_result: Any, key: Any) -> Any:  # type: ignore
        """
        Args:
            - task_result (Any): a value
            - key (Any): the index to retrieve as `task_result[key]`
        """
        return task_result[key]


# ---------------------------------------------------------
# Math
# ---------------------------------------------------------
class Add(Task):
    """
    Evaluates `x + y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> Any:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - Any
        """
        return x + y


class Sub(Task):
    """
    Evaluates `x - y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> Any:  # type: ignore
        """
        Args:
           - x (Any): a value
           - y (Any): a value

        Returns:
            - Any
        """
        return x - y


class Mul(Task):
    """
    Evaluates `x * y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> Any:  # type: ignore
        """
        Args:
           - x (Any): a value
           - y (Any): a value

        Returns:
            - Any
        """
        return x * y


class Div(Task):
    """
    Evaluates `x / y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> Any:  # type: ignore
        """
        Args:
           - x (Any): a value
           - y (Any): a value

        Returns:
            - Any
        """
        return x / y


class FloorDiv(Task):
    """
    Evaluates `x // y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> Any:  # type: ignore
        """
        Args:
           - x (Any): a value
           - y (Any): a value

        Returns:
            - Any
        """
        return x // y


class Pow(Task):
    """
    Evaluates `x ** y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> Any:  # type: ignore
        """
        Args:
           - x (Any): a value
           - y (Any): a value

        Returns:
            - Any
        """
        return x ** y


class Mod(Task):
    """
    Evaluates `x % y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> Any:  # type: ignore
        """
        Args:
           - x (Any): a value
           - y (Any): a value

        Returns:
            - Any
        """
        return x % y


# ---------------------------------------------------------
# Logic
# ---------------------------------------------------------
class And(Task):
    """
    Evaluates `x and y.`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - bool
        """
        return bool(x and y)


class Or(Task):
    """
    Evaluates `x or y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - bool
        """
        return bool(x or y)


class Not(Task):
    """
    Evaluates `not x`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value

        Returns:
            - bool
        """
        return bool(not (x))


class Equal(Task):
    """
    Evaluates `x == y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - bool
        """
        return bool(x == y)


class NotEqual(Task):
    """
    Evaluates `x != y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - bool
        """
        return bool(x != y)


class GreaterThanOrEqual(Task):
    """
    Evaluates `x ≥ y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - bool
        """
        return bool(x >= y)


class GreaterThan(Task):
    """
    Evaluates `x > y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - bool
        """
        return bool(x > y)


class LessThanOrEqual(Task):
    """
    Evaluates `x ≤ y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - bool
        """
        return bool(x <= y)


class LessThan(Task):
    """
    Evaluates `x < y`

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, x: Any, y: Any) -> bool:  # type: ignore
        """
        Args:
            - x (Any): a value
            - y (Any): a value

        Returns:
            - bool
        """
        return bool(x < y)
