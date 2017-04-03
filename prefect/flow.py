import base64
import distributed
import ujson
import peewee
import prefect
from prefect.models import Namespace, FlowModel
from prefect.edges import Edge
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
        self.tasks = set()
        self.edges = set()
        self.flow_id = '{namespace}.{name}:{version}'.format(
            namespace=self.namespace, name=self.name, version=self.version)
        self._id = None
        self.reload()

    @property
    def id(self):
        """ The ID of this Flow's FlowModel, if known """
        if self._id is not None:
            return self._id
        else:
            raise PrefectError(
                '{} has no id because it has not been saved!'.format(self))

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.flow_id)

    def __eq__(self, other):
        return (
            type(self) == type(other) and self.flow_id == other.flow_id
            and self.tasks == other.tasks and self.edges == other.edges)

    def __hash__(self):
        return id(self)

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
        if task.flow_id != self.flow_id:
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

        Note that the resulting sort will not always be in the same order!
        """

        tasks = set(self.tasks)
        sort_tasks = []

        while tasks:
            acyclic = False
            for task in list(tasks):
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
                    sort_tasks.append(task)
            if not acyclic:
                # no tasks matched
                raise ValueError('Flows must be acyclic!')
        return tuple(sort_tasks)

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

    def _get_model(self):
        """
        Retreives the ORM model corresponding to this Flow, but does not
        create it in the database if it does not exist already.
        """
        try:
            namespace = Namespace.get(namespace=self.namespace)
        except peewee.DoesNotExist:
            namespace = Namespace(namespace=self.namespace)
        kwargs = dict(
            namespace=namespace,
            name=self.name,
            version=self.version,)
        try:
            model = FlowModel.get(**kwargs)
        except peewee.DoesNotExist:
            model = FlowModel(**kwargs)
        return model

    def reload(self):
        model = self._get_model()
        if model.id:
            self.active = model.active
            self._id = model.id

    def save(self):
        model = self._get_model()
        model.namespace = Namespace.ensure_exists(self.namespace)
        model.active = self.active
        model.serialized = prefect.utilities.serialize.serialize(
            self, encryption_key=prefect.config.get('db', 'encryption_key'))
        model.save()
        self._id = model.id
        for t in self.tasks:
            t.save()
        for e in self.edges:
            e.save()

    def archive(self):
        model = self._get_model()
        if model.id:
            model.archived = True
            model.save()
        else:
            raise PrefectError('{} has not been saved yet.'.format(self))

    def unarchive(self):
        model = self._get_model()
        if model.id:
            model.archived = False
            model.save()
        else:
            raise PrefectError('{} has not been saved yet.'.format(self))

    def delete(self, confirm=False):
        if not confirm:
            raise ValueError(
                'You must confirm that you want to delete this '
                'Flow and all related data.')
        model = self._get_model()
        if model.id:
            model.delete_instance(recursive=True)
        else:
            raise PrefectError('{} has not been saved yet.'.format(self))

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
