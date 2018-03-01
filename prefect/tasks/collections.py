from prefect import Task
from prefect.utilities.tasks import TaskFactory


class Sequence(Task):

    def __init__(self, fn, name):
        self.fn = fn
        super().__init__(name=name)

    def run(self, **task_results):
        return self.fn(task_results.values())

    def __call__(self, *args):
        kwargs = {'arg_{}'.format(i+1): a for i, a in enumerate(args)}
        return super().__call__(**kwargs)


class Dict(Task):

    def run(self, *, base_dict=None, **task_results):
        result = {}
        result.update(base_dict or {})
        result.update(task_results)
        return result


list_ = TaskFactory(Sequence(fn=list, name='list'))
set_ = TaskFactory(Sequence(fn=set, name='set'))
tuple_ = TaskFactory(Sequence(fn=tuple, name='tuple'))
dict_ = TaskFactory(Dict(name='dict'))
