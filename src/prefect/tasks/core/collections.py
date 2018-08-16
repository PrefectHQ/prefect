
from typing import Iterable
from prefect import Task


class VarArgsTask(Task):
    """
    Task that can be bound to *args and transforms them into **kwargs
    """
    def bind(self, *args, upstream_tasks: Iterable[Task] = None):
        kwargs = {"arg_{}".format(i + 1): a for i, a in enumerate(args)}
        return super().bind(upstream_tasks=upstream_tasks, **kwargs)


class List(VarArgsTask):
    def run(self, **task_results) -> list:
        return [v for (k, v) in sorted(task_results.items())]


class Tuple(VarArgsTask):
    def run(self, **task_results) -> tuple:
        return tuple([v for (k, v) in sorted(task_results.items())])


class Set(VarArgsTask):
    def run(self, **task_results) -> set:
        return set(task_results.values())


class Dict(Task):
    def run(self, **task_results) -> dict:
        return task_results
