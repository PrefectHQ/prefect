import copy
import prefect
from prefect.edges import Edge
from prefect.task import Task
from prefect.exceptions import PrefectError
import prefect.context
from prefect.schedules import NoSchedule
import ujson


class Flow:

    def __init__(
            self,
            name,
            namespace=prefect.config.get('flows', 'default_namespace'),
            version=prefect.config.get('flows', 'default_version'),
            required_params=None,
            schedule=NoSchedule()):
        """
        required_params: a collection of parameter names that must be provided
            when the Flow is run. Flows can be called with any params, but an
            error will be raised if these are missing.
        """

        if required_params is None:
            required_params = set()
        elif isinstance(required_params, str):
            required_params = set([required_params])
        else:
            required_params = set(required_params)

        self.name = name
        self.namespace = namespace
        self.version = version
        self.required_params = required_params
        self.schedule = schedule
        self.tasks = set()
        self.edges = set()
        self.id = '{namespace}.{name}:{version}'.format(
            namespace=self.namespace, name=self.name, version=self.version)

        self._cache = {}
        self.check_cache()

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.id)

    def __eq__(self, other):
        return (
            type(self) == type(other) and self.id == other.id
            and self.tasks == other.tasks and self.edges == other.edges)

    def __hash__(self):
        return id(self)

    def check_cache(self):
        """
        Check if the cache is still valid by comparing it to the flow,
        and reset it if it isn't.
        """
        if (
                self._cache.get('tasks', None) != self.tasks
                or self._cache.get('edges', None) != self.edges):
            self._cache = {'tasks': set(self.tasks), 'edges': set(self.edges)}

    # Graph -------------------------------------------------------------------

    def __iter__(self):
        yield from self.sort_tasks()

    def get_task(self, name=None, id=None):
        """
        Retrieve a task by name
        """
        if (name is None and id is None) or (
                name is not None and id is not None):
            raise ValueError('Provide either name or id, but not both.')

        try:
            if name is not None:
                return next(t for t in self.tasks if t.name == name)
            else:
                return next(t for t in self.tasks if t.id == id)
        except StopIteration:
            raise PrefectError(
                'Task {} was not found in the Flow'.format(name or id))

    def add_task(self, task):
        if not isinstance(task, Task):
            raise TypeError(
                'Expected a Task; received {}'.format(type(task).__name__))
        if task.flow.id != self.id:
            raise ValueError('Task {} is already in another Flow'.format(task))
        if task.name in set(t.name for t in self.tasks):
            raise ValueError(
                'A task named {} already exists in this Flow.'.format(
                    task.name))
        self.tasks.add(task)

    def add_edge(self, edge):
        """
        Adds an Edge to the Flow. Edges create dependencies between tasks.
        The simplest edge simply enforcces an ordering so that the upstream
        task runs before the downstream task, but edges can introduce more
        complex behaviors as well.

        Args:
            edge (Edge): An Edge object representing a relationship between
                an upstream task and a downstream task.
        """
        if not isinstance(edge, Edge):
            raise TypeError(
                'Expected an Edge; received {}'.format(type(edge).__name__))
        self.edges.add(edge)

        # check that the edge doesn't add a cycle
        self.sort_tasks()

    def upstream_tasks(self, task):
        """
        Set of all tasks immediately upstream from a task.

        Args:
            task (Task): tasks upstream from this task will be returned.
        """
        return set(
            e.upstream_task for e in self.edges if e.downstream_task == task)

    def downstream_tasks(self, task):
        """
        Set of all tasks immediately downstream from a task.

        Args:
            task (Task): tasks downstream from this task will be returned.
        """
        return set(
            e.downstream_task for e in self.edges if e.upstream_task == task)

    def sort_tasks(self):
        """
        Returns a topological sort of this Flow's tasks.

        The result will be cached when possible.
        """

        self.check_cache()
        if 'sorted tasks' not in self._cache:
            tasks = set(self.tasks)
            sorted_tasks = []
            while tasks:
                acyclic = False
                for task in sorted(tasks, key=lambda t: t.id):
                    for upstream_task in self.upstream_tasks(task):
                        if upstream_task in tasks:
                            # the previous task hasn't been sorted yet, so
                            # this task can't be sorted either
                            break
                    else:
                        # all previous tasks are sorted, so this one can be
                        # sorted as well
                        acyclic = True
                        tasks.remove(task)
                        sorted_tasks.append(task)
                if not acyclic:
                    # no tasks matched
                    raise ValueError('Flows must be acyclic!')
            self._cache['sorted tasks'] = tuple(sorted_tasks)

        return self._cache['sorted tasks']

    def edges_to(self, task):
        """
        Set of all Edges leading to this Task

        Args:
            task (Task)
        """
        return set(e for e in self.edges if e.downstream_task == task)

    def edges_from(self, task):
        """
        Set of all Edges leading from this Task

        Args:
            task (Task)
        """
        return set(e for e in self.edges if e.upstream_task == task)

    # Context Manager -----------------------------------------------

    def __enter__(self):
        self._previous_context = prefect.context.set_context(flow=self)
        return self
        # global _CONTEXT_FLOW
        # self._old_context_manager_flow = _CONTEXT_FLOW
        # _CONTEXT_FLOW = self
        # return self

    def __exit__(self, _type, _value, _tb):
        prefect.context.reset_context(self._previous_context)
        del self._previous_context

    # Persistence  ------------------------------------------------

    def serialize(self, as_dict=False):
        flow = copy.copy(self)
        del flow.tasks
        del flow.edges

        serialized = dict(
            id=self.id,
            namespace=self.namespace,
            name=self.name,
            version=self.version,
            tasks=[ujson.loads(t.serialize()) for t in self.sort_tasks()],
            edges=[ujson.loads(e.serialize()) for e in self.edges],
            required_params=sorted(self.required_params),
            schedule=prefect.utilities.serialize.serialize(self.schedule),
            serialized=prefect.utilities.serialize.serialize(flow))
        if as_dict:
            return serialized
        else:
            return ujson.dumps(serialized)

    @classmethod
    def deserialize(cls, serialized):
        if not isinstance(serialized, dict):
            serialized = ujson.loads(serialized)
        obj = prefect.utilities.serialize.deserialize(serialized['serialized'])
        if not isinstance(obj, cls):
            raise TypeError(
                'Expected {}; received {}'.format(
                    cls.__name__, type(obj).__name__))
        obj.tasks = set([Task.deserialize(t) for t in serialized['tasks']])
        obj.edges = set([Edge.deserialize(e) for e in serialized['edges']])
        obj._cache.clear()
        return obj

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
