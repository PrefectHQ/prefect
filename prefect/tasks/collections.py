from prefect import Task
from prefect.utilities.tasks import task_factory


class Sequence(Task):

    def __call__(self, *args):
        kwargs = {'arg_{}'.format(i + 1): a for i, a in enumerate(args)}
        return super().__call__(**kwargs)


@task_factory
class List(Sequence):

    def run(self, **task_results):
        return list(task_results.values())


@task_factory
class Set(Sequence):

    def run(self, **task_results):
        return set(task_results.values())


@task_factory
class Tuple(Sequence):

    def run(self, **task_results):
        return tuple(task_results.values())

@task_factory
class Dict(Task):

    def run(self, *, base_dict=None, **task_results):
        result = {}
        result.update(base_dict or {})
        result.update(task_results)
        return result
