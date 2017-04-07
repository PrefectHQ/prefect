import functools
import ujson
import pendulum
import prefect
from prefect.exceptions import PrefectError
from prefect.edges import Edge, Pipe


def retry_delay(
        interval=None,
        *,
        exponential_backoff=False,
        max_delay=pendulum.interval(hours=2),
        **kwargs):
    """
    A helper function for generating task retry delays.

    Args:
        interval (pendulum.interval or timedelta): The amount of time to wait.
            This value is optional; users can also instantiate a new interval
            by passing keyword arguments directly to retry_delay. So:
                retry_delay(interval=pendulum.interval(days=1))
            is equivalent to:
                retry_delay(days=1)
        **kwargs: Keyword arguments are passed to pendulum.interval and
            are compatible with the datetime.timedelta API.
        exponential_backoff: if True, each retry delay will be exponentially
            longer than the last, starting with the second retry. For example,
            if the retry delay is 1 minute, then:
                - first retry starts after 1 minute
                - second retry also starts after 1 minute (no backoff applied)
                - third retry starts after 2 minutes
                - fourth retry starts after 4 minutes
                - etc.
        max_delay (pendulum.interval): If exponential_backoff is supplied,
            delays will be capped by this amount.
    """
    if interval is not None and kwargs:
        raise ValueError(
            'Provide an interval or interval keywords, but not both.')
    elif interval is None and not kwargs:
        raise ValueError('Provide either an interval or interval keywords.')
    elif kwargs:
        interval = pendulum.interval(**kwargs)

    def retry_delay(run_number):
        if exponential_backoff:
            scale = 2 ** (max(0, run_number - 2))
        else:
            scale = 1
        if max_delay is not None:
            return min(interval * scale, max_delay)
        else:
            return interval * scale

    return retry_delay


@functools.total_ordering
class Task:
    """
    Tasks are basic units of work. Each task performs a specific funtion.
    """

    def __init__(
            self,
            name=None,
            flow=None,
            fn=None,
            max_retries=0,
            retry_delay=retry_delay(minutes=5),
            trigger=None):
        """

        Args:
            fn (callable): By default, the Task's run() method calls this
                function. Task subclasses can also override run() instead of
                passing a function.

            retry_delay (pendulum.interval or callable): a function that
                is passed the most recent run number and returns an amount of
                time to wait before retrying the task. It is recommended to
                build the function with the retry_delay() helper function in
                this module. If a pendulum interval is passed, retry_delay is
                called on the interval automatically.

            max_retries: the number of times this task can be retried. -1 indicates
                an infinite number of times.

        """
        if fn is not None:
            self.run = fn

        if flow is None:
            flow = prefect.context.flow
            if flow is None:
                raise ValueError(
                    'Tasks must be created with a Flow or inside '
                    'a Flow context manager.')
        self.flow = flow

        if name is None:
            name = prefect.utilities.strings.name_with_suffix(
                name=getattr(fn, '__name__', type(self).__name__),
                predicate=lambda n: n not in [t.name for t in flow.tasks])
        if not prefect.utilities.strings.is_valid_identifier(name):
            raise ValueError(
                'Task names must be valid Python identifiers '
                '(received {})'.format(name))

        self.name = name
        self.id = '{}/{}'.format(self.flow.id, self.name)

        self.max_retries = max_retries

        if not callable(retry_delay):
            retry_delay = prefect.tasks.retry_delay(retry_delay)

        self.retry_delay = retry_delay

        if trigger is None:
            trigger = prefect.triggers.all_success
        self.trigger = trigger

        self.flow.add_task(self)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.id)

    # Comparison --------------------------------------------------------------

    def __eq__(self, other):
        return type(self) == type(other) and self.id == other.id

    def __lt__(self, other):
        if not isinstance(other, Task):
            return super().__lt__(other)
        self_order = (self.flow.id, self.flow.sort_tasks().index(self))
        other_order = (other.flow.id, other.flow.sort_tasks().index(other))
        return self_order < other_order

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

    # Serialize ---------------------------------------------------------------

    def serialize(self, as_dict=False):
        serialized = dict(
            id=self.id,
            name=self.name,
            flow=self.flow.id,
            max_retries=self.max_retries,
            retry_delay=prefect.utilities.serialize.serialize(self.retry_delay),
            serialized=prefect.utilities.serialize.serialize(self))

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
        return obj

    # Run  --------------------------------------------------------------------

    def run(self, **inputs):
        raise NotImplementedError(
            'Pass a `fn` to this task or override this method!')

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
        return 'TaskResult({}{})'.format(self.task.id, self._repr_index())
