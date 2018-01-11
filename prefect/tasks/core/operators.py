from prefect import Task


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
