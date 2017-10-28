from prefect import Task

class And(Task):

    def run(self, x, y):
        return bool(x and y)


class Or(Task):

    def run(self, x, y):
        return bool(x or y)


class Not(Task):

    def run(self, x):
        return bool(not (x))
