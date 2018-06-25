from typing import Any

from prefect import Task


class GetItem(Task):
    """
    Helper task that retrieves a specific index of an upstream task's result.
    """

    def __init__(self, index: Any, **kwargs: Any) -> None:
        self.index = index
        super().__init__(**kwargs)

    def run(self, task_result: Any) -> Any:
        return task_result[self.index]


class And(Task):
    """
    Evaluates x and y
    """

    def run(self, x, y):
        return bool(x and y)


class Or(Task):
    """
    Evaluates x or y
    """

    def run(self, x, y):
        return bool(x or y)


class Not(Task):
    """
    Evaluates not x
    """

    def run(self, x):
        return bool(not (x))


class Eq(Task):
    """
    Evaluates x == y
    """

    def run(self, x, y):
        return bool(x == y)


class Neq(Task):
    """
    Evaluates x != y
    """

    def run(self, x, y):
        return bool(x != y)


class GTE(Task):
    """
    Evaluates x ≥ y
    """

    def run(self, x, y):
        return bool(x >= y)


class GT(Task):
    """
    Evaluates x > y
    """

    def run(self, x, y):
        return bool(x > y)


class LTE(Task):
    """
    Evaluates x ≤ y
    """

    def run(self, x, y):
        return bool(x <= y)


class LT(Task):
    """
    Evaluates x < y
    """

    def run(self, x, y):
        return bool(x < y)
