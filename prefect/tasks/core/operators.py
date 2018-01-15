import inspect
from prefect import Task

def operator(cls):
    def wrapper(*args):
        task_instance = cls()
        callargs = inspect.getcallargs(task_instance.run, *args)
        callargs.pop(next(k for k, v in callargs.items() if v is task_instance))
        return task_instance(**callargs)
    return wrapper

@operator
class And(Task):
    """
    Evaluates x and y
    """

    def run(self, x, y):
        return bool(x and y)


@operator
class Or(Task):
    """
    Evaluates x or y
    """

    def run(self, x, y):
        return bool(x or y)


@operator
class Not(Task):
    """
    Evaluates not x
    """

    def run(self, x):
        return bool(not (x))


@operator
class Eq(Task):
    """
    Evaluates x == y
    """

    def run(self, x, y):
        return bool(x == y)


@operator
class Neq(Task):
    """
    Evaluates x != y
    """

    def run(self, x, y):
        return bool(x != y)


@operator
class GTE(Task):
    """
    Evaluates x ≥ y
    """

    def run(self, x, y):
        return bool(x >= y)


@operator
class GT(Task):
    """
    Evaluates x > y
    """

    def run(self, x, y):
        return bool(x > y)


@operator
class LTE(Task):
    """
    Evaluates x ≤ y
    """

    def run(self, x, y):
        return bool(x <= y)


@operator
class LT(Task):
    """
    Evaluates x < y
    """

    def run(self, x, y):
        return bool(x < y)
