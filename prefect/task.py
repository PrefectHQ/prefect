import copy
import datetime
import peewee
import prefect
from prefect.exceptions import PrefectError
from prefect.edges import Edge, Pipe
from prefect.models import TaskModel, FlowModel
from prefect.utilities.logging import LoggingMixin
from prefect.utilities.strings import name_with_suffix


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
            trigger=None):
        """
        fn: By default, the Task's run() method calls this function.

        max_retries: the number of times this task can be retried. -1 indicates
            an infinite number of times.

        """
        self.fn = fn

        if flow is None:
            flow = prefect.flow._CONTEXT_FLOW
            if flow is None:
                raise ValueError(
                    'Tasks must be created with a Flow or inside '
                    'a Flow context manager.')
        self.flow = flow
        self.flow_id = flow.flow_id

        if name is None:
            name = name_with_suffix(
                name=getattr(self.fn, '__name__', type(self).__name__),
                predicate=lambda n: n not in [t.name for t in flow.tasks])

        self.name = name
        self.task_id = '{}/{}'.format(self.flow_id, self.name)

        self.max_retries = max_retries
        self.retry_delay = retry_delay

        if trigger is None:
            trigger = prefect.triggers.all_success
        self.trigger = trigger

        self.flow.add_task(self)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.task_id)

    # Comparison --------------------------------------------------------------

    def __eq__(self, other):
        return type(self) == type(other) and self.task_id == other.task_id

    def __hash__(self):
        return id(self)

    # Relationships  ----------------------------------------------------------

    def run_before(self, tasks):
        """
        Adds a relationship to the Flow so that this task runs before another
        task.

        Args:
            Tasks (Task or collection of Tasks): Tasks that this task should
                run before.
        """
        if isinstance(tasks, Task):
            tasks = [tasks]
        for t in tasks:
            self.flow.add_edge(Edge(upstream_task=self, downstream_task=t))

    def run_after(self, tasks):
        """
        Adds a relationship to the Flow so that this task runs after another
        task.

        Args:
            Tasks (Task or collection of Tasks): Tasks that this task should
                run after.
        """
        if isinstance(tasks, Task):
            tasks = [tasks]
        for t in tasks:
            self.flow.add_edge(Edge(upstream_task=t, downstream_task=self))

    def then(self, task):
        """
        Create simple dependency chains by linking tasks:
            task1.then(task2).then(task3)

        Args:
            task (Task): the task that should run after this one

        Returns:
            The downstream task (`task`)

        """
        self.flow.add_edge(Edge(upstream_task=self, downstream_task=task))
        return task

    def add_pipes(self, **kwargs):
        """
        Adds a data pipe to the Flow so this task receives the results
        of upstream tasks.

        Args:
            **kwargs (Tasks or TaskResults): The provided Tasks / TaskResults
                will be piped into this Task under the key corresponding to
                that task / taskresult's kwarg.
        """
        for key, task_result in kwargs.items():
            if isinstance(task_result, Task):
                task_result = TaskResult(task_result)
            self.flow.add_edge(
                Pipe(
                    upstream_task_result=task_result,
                    downstream_task=self,
                    key=key))

    # Run  --------------------------------------------------------------------

    def run(self, **inputs):
        if self.fn is not None:
            return self.fn(**inputs)
        else:
            raise NotImplementedError('No `fn` was passed to this task!')

    # Results  ----------------------------------------------------------------

    def __iter__(self):
        raise NotImplementedError('Tasks are not iterable.')

    def __getitem__(self, index):
        return TaskResult(task=self, index=index)

    # Sugar -------------------------------------------------------------------

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


class TaskResult:
    """
    An object that represents the result (output) of a Task.

    TaskResults are primarily used to pipe data from one task to another.
    """

    class NoIndex:
        pass

    def __init__(self, task, index=NoIndex):
        if not isinstance(task, Task):
            raise TypeError(
                'task must be a Task; received {}'.format(type(task).__name__))
        self.task = task
        self.index = index

    def _repr_index(self):
        return '[{}]'.format(
            self.index if self.index is not self.NoIndex else ':')

    def __repr__(self):
        return 'TaskResult({}{})'.format(self.task.task_id, self._repr_index())
