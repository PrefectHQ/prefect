import base64
import distributed
import prefect
from prefect.exceptions import PrefectError
from prefect.utilities.schedules import (
    NoSchedule, DateSchedule, CronSchedule, IntervalSchedule)

_CONTEXT_MANAGER_FLOW = None


class Flow:

    def __init__(
            self,
            name,
            schedule=NoSchedule(),
            params=None,
            namespace=prefect.config.get('flows', 'default_namespace'),
            version=1,
            active=prefect.config.getboolean('flows', 'default_active')):

        if not isinstance(name, str):
            raise TypeError(
                'Name must be a string; received {}'.format(type(name)))

        if params is None:
            params = {}

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

    def get_task(self, name):
        """
        Retrieve a task by name
        """
        try:
            return next(t for t in self.graph if t.name == name)
        except StopIteration:
            raise PrefectError('Task {} was not found in the Flow'.format(name))

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
        global _CONTEXT_MANAGER_FLOW
        self._old_context_manager_flow = _CONTEXT_MANAGER_FLOW
        _CONTEXT_MANAGER_FLOW = self
        return self

    def __exit__(self, _type, _value, _tb):
        global _CONTEXT_MANAGER_FLOW
        _CONTEXT_MANAGER_FLOW = self._old_context_manager_flow

    # Serialization  ------------------------------------------------

    def serialize(self):
        return prefect.utilities.serialize.serialize(self)

    @staticmethod
    def from_serialized(serialized_obj):
        deserialized = prefect.utilities.serialize.deserialize(serialized_obj)
        if not isinstance(deserialized, Flow):
            raise TypeError('Deserialized object is not a Flow!')
        return deserialized

    def save(self):
        flow_model = prefect.models.FlowModel(
            _id=self.id,
            name=self.name,
            version=str(self.version),
            namespace=self.namespace,
            active=self.active,
            schedule=self.schedule,
            serialized=self.serialize())
        flow_model.save()
        return flow_model
