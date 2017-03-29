import base64
import distributed
import prefect
from prefect.models import FlowModel
from prefect.task import Task
from prefect.exceptions import PrefectError
from prefect.utilities.logging import LoggingMixin
from prefect.utilities.schedules import (
    Schedule,
    NoSchedule,
    DateSchedule,
    CronSchedule,
    IntervalSchedule,)

_CONTEXT_FLOW = None


class Flow(LoggingMixin):

    def __init__(
            self,
            name,
            params=None,
            schedule=NoSchedule(),
            namespace=prefect.config.get('flows', 'default_namespace'),
            version=1,
            active=prefect.config.getboolean('flows', 'default_active'),
            **_kw):
        """
        params: a collection of parameter names that can be provided when
            the Flow is run and passed to Tasks. Any other keywords will be
            rejected.
        """

        if params is None:
            params = set()
        elif isinstance(params, str):
            params = set([params])
        else:
            params = set(params)

        self.name = name
        self.namespace = namespace
        self.version = version
        self.params = params
        self.schedule = schedule
        self.active = active

        # a graph of task relationships keyed by the `after` task
        # and containing all the `before` tasks as values
        # { after : set(before, ...)}
        self.graph = {}

    @property
    def id(self):
        if self.namespace:
            namespace = '{}.'.format(self.namespace)
        else:
            namespace = ''
        return '{}{}:{}'.format(namespace, self.name, self.version)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.id)

    # Tasks ---------------------------------------------------------

    def __getitem__(self, item):
        return self.graph[item]

    def __iter__(self):
        yield from self.sorted_tasks()

    def add_task(self, task):
        if task.flow.id != self.id:
            raise ValueError('Task {} is already in another Flow'.format(task))

        task_names = set(t.name for t in self.graph)
        if task.name in task_names:
            raise ValueError(
                'A task named {} already exists in this Flow.'.format(
                    task.name))
        self.graph[task] = set()

    def get_task(self, name=None, id=None):
        """
        Retrieve a task by name
        """
        if (name is None and id is None) or (
                name is not None and id is not None):
            raise ValueError('Provide either name or id, but not both.')

        try:
            if name is not None:
                return next(t for t in self.graph if t.name == name)
            else:
                return next(t for t in self.graph if t.id == id)
        except StopIteration:
            raise PrefectError(
                'Task {} was not found in the Flow'.format(name or id))

    def add_task_relationship(self, before, after):
        if before not in self.graph:
            self.add_task(before)
        if after not in self.graph:
            self.add_task(after)
        self.graph[after].add(before)

        # try sorting tasks to make sure there are no cycles (an error is
        # raised otherwise)
        self.sorted_tasks()

    def sorted_tasks(self):
        """
        Returns a topological sort of this Flow's tasks.

        Note that the resulting sort will not always be in the same order!
        """

        graph = self.graph.copy()
        sorted_graph = []

        while graph:
            acyclic = False
            for task in list(graph):
                for preceding_task in graph[task]:
                    if preceding_task in graph:
                        # the previous task hasn't been sorted yet, so
                        # this task can't be sorted either
                        break
                else:
                    # all previous tasks are sorted, so this one can be
                    # sorted as well
                    acyclic = True
                    del graph[task]
                    sorted_graph.append(task)
            if not acyclic:
                # no tasks matched
                raise prefect.exceptions.PrefectError(
                    'Cycle detected in graph!')
        return sorted_graph

    def inverted_graph(self):
        """
        The Flow graph is stored as {task: set(preceding_tasks)} to make it
        easy to look up a task's immediate predecessors.

        Sometimes we want to find a task's immediate descendents. This method
        returns a graph of {task: set(following_nodes)}.
        """
        inverted_graph = {t: set() for t in self.graph}

        for task, preceding_tasks in self.graph.items():
            for t in preceding_tasks:
                inverted_graph[t].add(task)

        return inverted_graph

    # Context Manager -----------------------------------------------

    def __enter__(self):
        global _CONTEXT_FLOW
        self._old_context_manager_flow = _CONTEXT_FLOW
        _CONTEXT_FLOW = self
        return self

    def __exit__(self, _type, _value, _tb):
        global _CONTEXT_FLOW
        _CONTEXT_FLOW = self._old_context_manager_flow

    # Serialization  ------------------------------------------------

    def serialize(self):
        return prefect.utilities.serialize.serialize(self)

    @staticmethod
    def from_serialized(serialized_obj):
        flow = prefect.utilities.serialize.deserialize(serialized_obj)
        if not isinstance(flow, Flow):
            raise TypeError('Deserialized object is not a Flow!')
        return flow

    # ORM ----------------------------------------------------------

    def to_model(self):
        """
        Create a database-compatible version of this Flow
        """
        return FlowModel(
            _id=self.id,
            namespace=self.namespace,
            name=self.name,
            version=str(self.version),
            active=self.active,
            params=sorted(self.params),
            graph={
                t.id: sorted(pt.id for pt in preceding)
                for t, preceding in self.graph.items()
            },
            tasks={task.id: task.to_model()
                   for task in self},
            serialized=self.serialize(),)

    @classmethod
    def from_id(cls, flow_id):
        return cls.from_serialized(
            FlowModel.objects.only('serialized').get(_id=flow_id)['serialized'])

    def save(self):
        for task in self:
            task.save()
        model = self.to_model()
        model.save()

    # Decorator ----------------------------------------------------

    def task(self, fn=None, **kwargs):
        """
        A decorator for creating Tasks from functions.

        Usage:

        with Flow('flow') as f:

            @f.task
            def myfn():
                time.sleep(10)
                return 1

            @f.task(name='hello', retries=3)
            def hello():
                print('hello')

        """
        if 'flow' in kwargs:
            raise ValueError('Flow can not be passed to task decorator')

        if callable(fn):
            return Task(fn=fn, flow=self)
        else:

            def wrapper(fn):
                return Task(fn=fn, flow=self, **kwargs)

            return wrapper
