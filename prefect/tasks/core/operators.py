from prefect import Task
from prefect.utilities.tasks import task_factory


class GetIndexTask(Task):

    def __init__(self, index, **kwargs):
        self.index = index
        super().__init__(**kwargs)

    def run(self, task_result):
        return task_result[self.index]


@task_factory()
class And(Task):
    """
    Evaluates x and y
    """

    def run(self, x, y):
        return bool(x and y)


@task_factory()
class Or(Task):
    """
    Evaluates x or y
    """

    def run(self, x, y):
        return bool(x or y)


@task_factory()
class Not(Task):
    """
    Evaluates not x
    """

    def run(self, x):
        return bool(not (x))


@task_factory(name='==')
class Eq(Task):
    """
    Evaluates x == y
    """

    def run(self, x, y):
        return bool(x == y)


@task_factory(name='≠')
class Neq(Task):
    """
    Evaluates x != y
    """

    def run(self, x, y):
        return bool(x != y)


@task_factory(name='≥')
class GTE(Task):
    """
    Evaluates x ≥ y
    """

    def run(self, x, y):
        return bool(x >= y)


@task_factory(name='>')
class GT(Task):
    """
    Evaluates x > y
    """

    def run(self, x, y):
        return bool(x > y)


@task_factory(name='≤')
class LTE(Task):
    """
    Evaluates x ≤ y
    """

    def run(self, x, y):
        return bool(x <= y)


@task_factory(name='<')
class LT(Task):
    """
    Evaluates x < y
    """

    def run(self, x, y):
        return bool(x < y)
