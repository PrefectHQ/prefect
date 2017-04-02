import base64
import distributed
import ujson
import prefect
from prefect.models import Namespace, FlowModel
from prefect.task import Task
from prefect.exceptions import PrefectError
from prefect.utilities.logging import LoggingMixin
from prefect.schedules import (
    Schedule,
    NoSchedule,
    DateSchedule,
    CronSchedule,
    IntervalSchedule,)

_CONTEXT_FLOW = None


class Graph:

    def __init__(self):
        """
        A Directed Acyclic Graph
        """
        self._nodes = set()
        self._edges_to_node = {}
        self._edges_from_node = {}
        self._pipes = {}

    def __repr__(self):
        return '<Directed Acyclic Graph>'.format(
            num=len(self._nodes), plural='' if len(self._nodes) == 1 else 's')

    def __iter__(self):
        yield from self.sort_nodes()

    @property
    def nodes(self):
        return set(self._nodes)

    def edges_to(self, node):
        """
        Set of all nodes with edges leading TO the specified node
        """
        return set(self._edges_to_node[node])

    def edges_from(self, node):
        """
        Set of all nodes with edges leading FROM the specified node
        """
        return set(self._edges_from_node[node])

    # def pipes(self, node):
    #     return dict(self._pipes[node])

    def sort_nodes(self):

        nodes = set(self.nodes)
        sort_nodes = []

        while nodes:
            acyclic = False
            for node in list(nodes):
                for upstream_node in self.edges_to(node):
                    if upstream_node in nodes:
                        # the previous node hasn't been sorted yet, so
                        # this node can't be sorted either
                        break
                else:
                    # all previous nodes are sorted, so this one can be
                    # sorted as well
                    acyclic = True
                    nodes.remove(node)
                    sort_nodes.append(node)
            if not acyclic:
                # no nodes matched
                raise ValueError('Cycle detected in graph!')
        return tuple(sort_nodes)

    def add_node(self, node):
        if node not in self._nodes:
            self._nodes.add(node)
            self._edges_to_node[node] = set()
            self._edges_from_node[node] = set()
            self._pipes[node] = {}

    def add_edge(self, from_obj, to_obj):
        self.add_node(from_obj)
        self.add_node(to_obj)
        self._edges_to_node[to_obj].update([from_obj])
        self._edges_from_node[from_obj].update([to_obj])

        # try sorting nodes to make sure there are no cycles (an error is
        # raised otherwise)
        self.sort_nodes()


class Flow(LoggingMixin):

    def __init__(
            self,
            name,
            required_params=None,
            schedule=NoSchedule(),
            namespace=prefect.config.get('flows', 'default_namespace'),
            version=prefect.config.get('flows', 'default_version'),
            active=prefect.config.getboolean('flows', 'default_active'),
            **_kw):
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
        self.active = active
        self.graph = Graph()
        self.pipes = Graph()
        self.flow_id = '{namespace}.{name}:{version}'.format(
            namespace=self.namespace, name=self.name, version=self.version)
        self._id = None

    @property
    def id(self):
        """ The ID of this Flow's FlowModel, if known """
        return self._id

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.flow_id)

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
                return next(t for t in self.graph if t.name == name)
            else:
                return next(t for t in self.graph if t.id == id)
        except StopIteration:
            raise PrefectError(
                'Task {} was not found in the Flow'.format(name or id))

    def add_task(self, task):
        if not isinstance(task, Task):
            raise TypeError(
                'Expected a Task; received {}'.format(type(task).__name__))
        if task.flow_id != self.flow_id:
            raise ValueError('Task {} is already in another Flow'.format(task))

        task_names = set(t.name for t in self.graph)
        if task.name in task_names:
            raise ValueError(
                'A task named {} already exists in this Flow.'.format(
                    task.name))

        self.graph.add_node(task)

    def add_dependency(self, upstream_task, downstream_task):
        """
        Create a dependent relationship between the upstream task and the
        downstream_task. The downstream_task will not run until its trigger is
        met by the upstream task.
        """
        self.graph.add_edge(upstream_task, downstream_task)

    def add_pipe(self, task, upstream_task_result, key):
        """
        Create a data pipe between the upstream task result
        and the downstream task. The upstream task result will be passed to
        the downstream task as a parameter under `key`.
        """
        self.graph.add_pipe(
            task=task, upstream_task_result=upstream_task_result, key=key)

    def upstream_tasks(self, task):
        """
        Set of all tasks immediately upstream from a task
        """
        return self.graph.edges_to(task)

    def downstream_tasks(self, task):
        """
        Set of all tasks immediately downstream from a task
        """
        return self.graph.edges_from(task)

    def sort_tasks(self):
        """
        Returns a topological sort of this Flow's tasks.

        Note that the resulting sort will not always be in the same order!
        """
        return self.graph.sort_nodes()

    # Context Manager -----------------------------------------------

    def __enter__(self):
        global _CONTEXT_FLOW
        self._old_context_manager_flow = _CONTEXT_FLOW
        _CONTEXT_FLOW = self
        return self

    def __exit__(self, _type, _value, _tb):
        global _CONTEXT_FLOW
        _CONTEXT_FLOW = self._old_context_manager_flow

    # Persistence  ------------------------------------------------

    @staticmethod
    def from_id(id):
        """
        Load a serialized Flow from the database
        """
        model = (
            FlowModel
            .select(FlowModel.serialized)
            .where(FlowModel.id == id)
            .get())  # yapf: disable
        flow = prefect.utilities.serialize.deserialize(
            model.serialized,
            decryption_key=prefect.config.get('db', 'encryption_key'))
        flow._id = id
        return flow

    def reload(self):
        model = FlowModel.from_flow_id(
            name=self.name,
            namespace=self.namespace,
            version=self.version,)
        if model.id:
            self.active = model.active
            self._id = model.id

    def save(self):
        model = FlowModel.from_flow_id(
            name=self.name,
            namespace=self.namespace,
            version=self.version,
            create_if_not_found=True)
        model.active = self.active
        model.serialized = prefect.utilities.serialize.serialize(
            self, encryption_key=prefect.config.get('db', 'encryption_key'))
        model.save()
        self._id = model.id

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
