# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any

from prefect import Task


class GetItem(Task):
    """
    Helper task that retrieves a specific index of an upstream task's result.
    """

    def run(self, task_result: Any, key: Any) -> Any:
        return task_result[key]


# ---------------------------------------------------------
# Math
# ---------------------------------------------------------
class Add(Task):
    """
    Evaluates x + y
    """

    def run(self, x: Any, y: Any) -> Any:
        return x + y


class Sub(Task):
    """
    Evaluates x - y
    """

    def run(self, x: Any, y: Any) -> Any:
        return x - y


class Mul(Task):
    """
    Evaluates x * y
    """

    def run(self, x: Any, y: Any) -> Any:
        return x * y


class Div(Task):
    """
    Evaluates x / y
    """

    def run(self, x: Any, y: Any) -> Any:
        return x / y


class FloorDiv(Task):
    """
    Evaluates x // y
    """

    def run(self, x: Any, y: Any) -> Any:
        return x // y


class Pow(Task):
    """
    Evaluates x ** y
    """

    def run(self, x: Any, y: Any) -> Any:
        return x ** y


class Mod(Task):
    """
    Evaluates x % y
    """

    def run(self, x: Any, y: Any) -> Any:
        return x % y


# ---------------------------------------------------------
# Logic
# ---------------------------------------------------------
class And(Task):
    """
    Evaluates x and y
    """

    def run(self, x: Any, y: Any) -> bool:
        return bool(x and y)


class Or(Task):
    """
    Evaluates x or y
    """

    def run(self, x: Any, y: Any) -> bool:
        return bool(x or y)


class Not(Task):
    """
    Evaluates not x
    """

    def run(self, x):
        return bool(not (x))


class Equal(Task):
    """
    Evaluates x == y
    """

    def run(self, x: Any, y: Any) -> bool:
        return bool(x == y)


class NotEqual(Task):
    """
    Evaluates x != y
    """

    def run(self, x: Any, y: Any) -> bool:
        return bool(x != y)


class GreaterThanOrEqual(Task):
    """
    Evaluates x ≥ y
    """

    def run(self, x: Any, y: Any) -> bool:
        return bool(x >= y)


class GreaterThan(Task):
    """
    Evaluates x > y
    """

    def run(self, x: Any, y: Any) -> bool:
        return bool(x > y)


class LessThanOrEqual(Task):
    """
    Evaluates x ≤ y
    """

    def run(self, x: Any, y: Any) -> bool:
        return bool(x <= y)


class LessThan(Task):
    """
    Evaluates x < y
    """

    def run(self, x: Any, y: Any) -> bool:
        return bool(x < y)
