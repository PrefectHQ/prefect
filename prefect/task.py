import copy
import datetime
from mongoengine import DoesNotExist
import prefect
from prefect.models import TaskModel, FlowModel
from prefect.utilities.logging import LoggingMixin


class Task(LoggingMixin):
    """
    Tasks are basic units of work. Each task performs a specific funtion.
    """

    def __init__(
            self,
            name=None,
            flow=None,
            fn=None,
            max_retries=0,
            retry_delay=datetime.timedelta(minutes=5),
            pass_params=False,
            trigger=None):
        """
        fn: By default, the Task's run() method calls this function.

        max_retries: the number of times this task can be retried. -1 indicates
            an infinite number of times.

        pass_params: Whether to pass the parameters to the Task function. If
            True, the function must accept **kwargs.
        """

        self.fn = fn

        if flow is None:
            flow = prefect.flow._CONTEXT_FLOW
            if flow is None:
                raise ValueError(
                    'Tasks must be created with a Flow or inside '
                    'a Flow context manager.')
        self.flow = flow

        if name is None:
            name = self.fn.__name__

        if not isinstance(name, str):
            raise TypeError(
                'Name must be a string; received {}'.format(type(name)))
        self.name = name

        if not isinstance(max_retries, int):
            raise TypeError(
                'Retries must be an int; received {}'.format(max_retries))
        self.max_retries = max_retries

        self.retry_delay = retry_delay

        if trigger is None:
            trigger = prefect.utilities.triggers.all_success
        self.trigger = trigger

        self.pass_params = pass_params

        self.flow.add_task(self)

    @property
    def id(self):
        return '{}/{}'.format(self.flow.id, self.name)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.id)

    def run_before(self, tasks):
        """
        Adds a relationship to the Flow so that this task runs before another
        task.
        """
        if isinstance(tasks, Task):
            tasks = [tasks]
        for t in tasks:
            self.flow.add_task_relationship(before=self, after=t)

    def run_after(self, tasks):
        """
        Adds a relationship to the Flow so that this task runs after another
        task.
        """
        if isinstance(tasks, Task):
            tasks = [tasks]
        for t in tasks:
            self.flow.add_task_relationship(before=t, after=self)

    def run(self, **params):
        if self.fn is not None:
            kwargs = {}
            if self.pass_params:
                kwargs.update(params)
            return self.fn(**kwargs)

    # Results  ------------------------------------------------------

    def __iter__(self):
        raise NotImplementedError('Tasks can not be iterated.')

    def __getitem__(self, item):
        return TaskResult(self, item)

    # Serialization  ------------------------------------------------

    def serialize(self):
        return prefect.utilities.serialize.serialize(self)

    @staticmethod
    def from_serialized(serialized_obj):
        deserialized = prefect.utilities.serialize.deserialize(serialized_obj)
        if not isinstance(deserialized, Task):
            raise TypeError('Deserialized object is not a Task!')
        return deserialized

    # Sugar ---------------------------------------------------------

    def __or__(self, task):
        """ self | task -> self.run_before(task)"""
        self.run_before(task)
        return task

    def __ror__(self, obj):
        """
        obj | self -> self.run_after(obj)
        """
        self.run_after(obj)
        return self

    def __rshift__(self, task):
        """ self >> task -> self.run_before(task)"""
        self.run_before(task)
        return task

    def __rrshift__(self, obj):
        """ obj >> self -> self.run_after(obj)"""
        self.run_after(obj)
        return obj

    def __lshift__(self, task):
        """ self << task -> self.run_after(task)"""
        self.run_after(task)
        return task

    def __rlshift__(self, obj):
        """ obj << self -> self.run_before(obj)"""
        self.run_before(obj)
        return obj

    # Serialization  ------------------------------------------------

    def serialize(self):
        return prefect.utilities.serialize.serialize(self)

    @staticmethod
    def from_serialized(serialized_obj):
        task = prefect.utilities.serialize.deserialize(serialized_obj)
        if not isinstance(task, Task):
            raise TypeError('Deserialized object is not a Task!')
        return task

    # ORM ----------------------------------------------------------

    def to_model(self):
        return TaskModel(
            _id=self.id,
            name=self.name,
            type=type(self).__name__,
            flow_id=self.flow.id,
            max_retries=self.max_retries)

    @classmethod
    def from_id(cls, task_id):
        flow_id = TaskModel.objects.only('flow_id').get(_id=task_id)['flow_id']
        flow = prefect.utilities.serialize.deserialize(
            FlowModel.objects.only('serialized').get(_id=flow_id)['serialized'])
        return flow.get_task(id=task_id)

    def save(self):
        model = self.to_model()
        model.save()


class TaskResult:

    def __init__(self, task, index=None):
        self.task = task
        self.index = index

    def __repr__(self):
        if self.index is not None:
            return 'TaskResult({}/{})'.format(self.task.id, self.index)
        else:
            return 'TaskResult({})'.format(self.task.id)
