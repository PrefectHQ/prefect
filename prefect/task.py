import base64
import datetime
import functools
import hashlib
import importlib
import prefect
from prefect.signals import PrefectError
from prefect.edges import Edge, Pipe
from prefect.utilities.strings import is_valid_identifier
import ujson


class TaskResult:
    """
    An object that represents the symbolic result (output) of a Task.

    TaskResults are primarily used to pipe data from one task to another.

    Note that TaskResults are stand-ins for task results, but don't hold
    the actual results.
    """

    def __init__(self, task, index=None):
        if not isinstance(task, Task):
            raise TypeError(
                'task must be a Task; received {}'.format(type(task).__name__))
        self.task = task
        self.index = index

    def _repr_index(self):
        return '[{}]'.format(self.index if self.index is not None else ':')

    def __repr__(self):
        return 'TaskResult({}{})'.format(self.task.id, self._repr_index())


class Edge:

    def __init__(
            self, upstream_task, downstream_task, key=None,
            upstream_index=None):
        """
        Edges represent connections between Tasks.

        At a minimum, edges link an upstream_task and a downstream_task
        indicating that the downstream task shouldn't run until the upstream
        task is complete.

        In addition, edges can specify a key and upstream_index that
        describe how upstream results are passed to the downstream task.

        Args:
            upstream_task (Task): a task that must run before the
                downstream_task

            downstream_task (Task): a task that will be run after the
                upstream_task. The upstream task state is passed to the
                downstream task's trigger function to determine whether the
                downstream task should run.

            key (str): Optional. Passing a key indicates
                that the upstream result should be passed to the downstream
                task as a keyword argument.

            upstream_index (obj): Optional, but a key must also be
                passed. The upstream key is used to index the upstream result
                prior to passing it to the downstream task.

        The key indicates that the result of the upstream task
        should be passed to the downstream task under the key.

        If a key is provided, an upstream_index can also be provided
        """
        self.upstream_task = upstream_task
        self.downstream_task = downstream_task

        if key is not None:
            if not is_valid_identifier(key):
                raise ValueError(
                    'Downstream key ("{}") must be a valid identifier'.format(
                        key))
        elif upstream_index is not None:
            raise ValueError(
                'Downstream key must be supplied to use an upstream key')
        self.key = key
        self.upstream_index = upstream_index

    def serialize(self):
        """
        Returns a serialized version of the edge
        """
        return {
            'upstream_task': self.upstream_task.name,
            'downstream_task': self.downstream_task.name,
            'key': self.key,
            'upstream_index': prefect.utilities.serialize.serialize(
                self.upstream_index)
        }

    @classmethod
    def from_serialized(cls, serialized):
        if 'upstream_index' in serialized:
            upstream_index = prefect.utilities.serialize.deserialize(
                serialized['upstream_index'])
        else:
            upstream_index = None


def retry_delay(
        interval=None,
        *,
        exponential_backoff=False,
        max_delay=datetime.timedelta(hours=2),
        **kwargs):
    """
    A helper function for generating task retry delays.

    Args:
        interval (timedelta): The amount of time to wait.
            This value is optional; users can also instantiate a new interval
            by passing keyword arguments directly to retry_delay. So:
                retry_delay(interval=timedelta(days=1))
            is equivalent to:
                retry_delay(days=1)

        **kwargs: Keyword arguments are passed to timedelta and
            are compatible with the datetime.timedelta API.

        exponential_backoff: if True, each retry delay will be exponentially
            longer than the last, starting with the second retry. For example,
            if the retry delay is 1 minute, then:
                - first retry starts after 1 minute
                - second retry also starts after 1 minute (no backoff applied)
                - third retry starts after 2 minutes
                - fourth retry starts after 4 minutes
                - etc.

        max_delay (timedelta): If exponential_backoff is supplied,
            delays will be capped by this amount.
    """
    if interval is not None and kwargs:
        raise ValueError(
            'Provide an interval or interval keywords, but not both.')
    elif interval is None and not kwargs:
        raise ValueError('Provide either an interval or interval keywords.')
    elif kwargs:
        interval = datetime.timedelta(**kwargs)

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
            trigger=None,
            serializer=None,
            resources=None,
            image=None):
        """

        Args:
            fn (callable): By default, the Task's run() method calls this
                function. Task subclasses can also override run() instead of
                passing a function.

            retry_delay (timedelta or callable): a function that
                is passed the most recent run number and returns an amount of
                time to wait before retrying the task. It is recommended to
                build the function with the retry_delay() helper function in
                this module. If a timedelta is passed, retry_delay is
                called on the interval automatically.

            max_retries: the number of times this task can be retried. -1
                indicates an infinite number of times.

            serializer (Serializer): the class used to serialize and
                deserialize the task result.

            resources (dict): a dictionary of resources that the Dask scheduler
                can use to allocate the task (requires cluster configuration)
                See https://distributed.readthedocs.io/en/latest/resources.html

            image (str): the Docker image the task should be run in (requires
                cluster configuration)


        """
        # override self.run if a function was passed
        if fn is not None:
            self.run = fn

        # set the flow
        if flow is None:
            flow = prefect.context.flow
            if flow is None:
                raise ValueError(
                    'Tasks must be created with a Flow or inside '
                    'a Flow context manager.')
        self.flow = flow

        # set the name and id
        if name is None:
            name = getattr(fn, '__name__', type(self).__name__)
            name = name.replace('<lambda>', '__lambda__')
            name = prefect.utilities.strings.name_with_suffix(
                name=name,
                predicate=lambda n: n not in [t.name for t in flow.tasks])
        if not is_valid_identifier(name):
            raise ValueError(
                'Task names must be valid Python identifiers '
                '(received {})'.format(name))
        self.name = name

        h = hashlib.sha1(f'{self.flow}{self.name}'.encode())
        self.id = base64.b32encode(h.digest()).decode().lower()

        # set up retries
        if not callable(retry_delay):
            retry_delay = prefect.tasks.retry_delay(retry_delay)
        self.retry_delay = retry_delay
        self.max_retries = max_retries

        # set up up trigger
        if trigger is None:
            trigger = prefect.triggers.all_successful
        self.trigger = trigger

        # set up result serialization
        if serializer is None:
            default = prefect.config.get('tasks', 'default_serializer')
            default_module, default_class = default.rsplit('.', 1)
            serializer_class = getattr(
                importlib.import_module(default_module),
                default_class)
            serializer = serializer_class()
        self.serializer = serializer

        # misc
        self.resources = resources or {}
        self.image = image

        # add the task to the flow
        self.flow.add_task(self)

    def __repr__(self):
        return f'{type(self).__name__}({self.flow.name}/{self.name})'

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

    def run_with(self, *tasks, **results):
        """
        Adds a data pipe to the Flow so this task receives the results
        of upstream tasks.

        Args:
            *tasks (Tasks): The provided Tasks will be set as upstream
                dependencies of this task

            **results (Tasks or TaskResults): The provided Tasks / TaskResults
                will be made upstream dependencies of this task AND their
                results will passed to the task under the provided keyword.
        """

        self.run_after(tasks)

        for key, task_result in results.items():
            if isinstance(task_result, Task):
                task_result = TaskResult(task_result)
            self.flow.add_edge(
                Edge(
                    upstream_task=task_result.task,
                    downstream_task=self,
                    key=key,
                    upstream_index=task_result.index))

    # Serialize ---------------------------------------------------------------

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'flow': self.flow.id,
            'type': type(self).__name__,
            'max_retries': self.max_retries,
            'serialized': prefect.utilities.serialize.serialize(self)
        }

    @classmethod
    def deserialize(cls, serialized):
        obj = prefect.utilities.serialize.deserialize(serialized['serialized'])
        if not isinstance(obj, cls):
            raise TypeError(
                'Expected {}; received {}'.format(
                    cls.__name__, type(obj).__name__))
        return obj

    # Run  --------------------------------------------------------------------

    def run(self, **inputs):
        """
        The main entrypoint for tasks.

        In addition to running arbitrary functions, tasks can interact with
        Prefect in a few ways:
            1. Return an optional result. When this function runs successfully,
                the task is considered successful and the result (if any) is
                made available to downstream edges.
            2. Raise an error. Errors are interpreted as failure.
            3. Raise a signal. Signals can include FAIL, SUCCESS, WAIT, etc.
                and indicate that the task should be put in the indicated
                state.
                - FAIL will lead to retries if appropriate
                - WAIT will end execution and skip all downstream tasks with
                    state WAITING_FOR_UPSTREAM (unless appropriate triggers
                    are set). The task can be run again and should check
                    context.is_waiting to see if it was placed in a WAIT.
            4. Yield new tasks or flows. If a task yields tasks or flows,
                they are submitted for execution. Execution should be treated
                as asynchronous; the task does not stop after yielding.
        """
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
