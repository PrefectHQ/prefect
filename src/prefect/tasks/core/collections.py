# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any, Iterable

from prefect import Task


class VarArgsTask(Task):
    """
    Task that can be bound to *args and transforms them into **kwargs
    """

    def bind(
        self, *args: Any, upstream_tasks: Iterable[Task] = None, mapped: bool = False
    ) -> Task:
        kwargs = {"arg_{}".format(i + 1): a for i, a in enumerate(args)}
        return super().bind(upstream_tasks=upstream_tasks, **kwargs)


class List(VarArgsTask):
    def run(self, **task_results) -> list:  # type: ignore
        return [v for (k, v) in sorted(task_results.items())]


class Tuple(VarArgsTask):
    def run(self, **task_results) -> tuple:  # type: ignore
        return tuple([v for (k, v) in sorted(task_results.items())])


class Set(VarArgsTask):
    def run(self, **task_results) -> set:  # type: ignore
        return set(task_results.values())


class Dict(Task):
    def run(self, **task_results) -> dict:  # type: ignore
        return task_results
