import inspect
from prefect import Task
from prefect.utilities.tasks import task_factory


@task_factory
class And(Task):
    """
    Evaluates x and y
    """

    def run(self, x, y):
        return bool(x and y)


@task_factory
class Or(Task):
    """
    Evaluates x or y
    """

    def run(self, x, y):
        return bool(x or y)


@task_factory
class Not(Task):
    """
    Evaluates not x
    """

    def run(self, x):
        return bool(not (x))


@task_factory
class Eq(Task):
    """
    Evaluates x == y
    """

    def run(self, x, y):
        return bool(x == y)


@task_factory
class Neq(Task):
    """
    Evaluates x != y
    """

    def run(self, x, y):
        return bool(x != y)


@task_factory
class GTE(Task):
    """
    Evaluates x ≥ y
    """

    def run(self, x, y):
        return bool(x >= y)


@task_factory
class GT(Task):
    """
    Evaluates x > y
    """

    def run(self, x, y):
        return bool(x > y)


@task_factory
class LTE(Task):
    """
    Evaluates x ≤ y
    """

    def run(self, x, y):
        return bool(x <= y)


@task_factory
class LT(Task):
    """
    Evaluates x < y
    """

    def run(self, x, y):
        return bool(x < y)
