import base64
import datetime
import functools
import hashlib
import importlib
import prefect
from prefect.signals import PrefectError
from prefect.utilities.strings import name_with_suffix
from prefect.utilities.datetimes import retry_delay
import ujson


class Task:
    """
    Tasks are basic units of work. Each task performs a specific funtion.
    """

    def __new__(obj, *args, **kwargs):
        """
        Each Task tracks the arguments that were used to create it. These
        variables are available as Task._init_args and Task._init_kwargs.
        """
        instance = super().__new__(obj)
        instance._init_args = args
        instance._init_kwargs = kwargs
        return instance

    def __init__(
            self,
            name=None,
            max_retries=0,
            retry_delay=retry_delay(minutes=5),
            trigger=None,
            serializer=None,
            flow=None,
            resources=None,
            image=None,
            cluster=None,):
        """

        Args:

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

        # see if this task was created inside a flow context
        flow = flow or prefect.context.get('flow')

        # if a flow was provided, try to infer a name
        if flow and name is None:
            name = name_with_suffix(
                type(self).__name__,
                predicate=lambda n: n not in flow.tasks,
                first_suffix=2,
                delimiter='-')

        if not isinstance(name, str):
            raise ValueError(
                'Name is invalid or could not be inferred '
                f'from provided Flow: {name}')
        self.name = name

        # set up retries
        if not callable(retry_delay):
            retry_delay = prefect.tasks.retry_delay(retry_delay)
        self.retry_delay = retry_delay
        self.max_retries = max_retries

        # set up up trigger
        if trigger is None:
            trigger = prefect.triggers.all_successful
        elif isinstance(trigger, str):
            trigger = getattr(prefect.triggers, trigger)
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
        self.cluster = cluster

        # add the task to the flow
        if flow:
            flow.add_task(self)

    def __repr__(self):
        return f'{type(self).__name__}({self.name})'

    # Comparison --------------------------------------------------------------

    def __eq__(self, other):
        if type(self) == type(other) and self.name == other.name:
            self_comp = self.serialize()
            self_comp.pop('serialized')
            other_comp = other.serialize()
            other_comp.pop('serialized')
            return self_comp == other_comp
        return False

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
        flow = prefect.context.get('flow')
        if not flow:
            raise ValueError(
                'This function can only be called inside a Flow context')
        if isinstance(tasks, Task):
            tasks = [tasks]
        for t in tasks:
            flow.set_up_task(task=t, upstream_tasks=[self])

    def run_after(self, tasks):
        """
        Adds a relationship to the Flow so that this task runs after another
        task.

        Args:
            Tasks (Task or collection of Tasks): Tasks that this task should
                run after.
        """
        flow = prefect.context.get('flow')
        if not flow:
            raise ValueError(
                'This function can only be called inside a Flow context')
        if isinstance(tasks, Task):
            tasks = [tasks]
        flow.set_up_task(task=self, upstream_tasks=tasks)

    def then(self, task):
        """
        Create simple dependency chains by linking tasks:
            task1.then(task2).then(task3)

        Args:
            task (Task): the task that should run after this one

        Returns:
            The downstream task (`task`)

        """
        self.run_before(task)
        return task

    def __call__(self, *upstream_tasks, **results):
        """
        Dynamically create relationships between this task and upstream
        tasks.

        Args:
            *upstream_tasks (Tasks): The provided Tasks will be set as upstream
                dependencies of this task

            **results (Tasks or TaskResults): The provided Tasks / TaskResults
                will be made upstream dependencies of this task AND their
                results will passed to the task under the provided keyword.
        """
        flow = prefect.context.get('flow')
        if not flow:
            raise ValueError(
                'This function can only be called inside a Flow context')
        flow.set_up_task(task=self, upstream_tasks=upstream_tasks, upstream_results=results)
        return self

    # Serialize ---------------------------------------------------------------

    def serialize(self):
        return {
            'name': self.name,
            'type': type(self).__name__,
            'max_retries': self.max_retries,
            'serialized': prefect.utilities.serialize.serialize(self),
            'trigger': self.trigger.__name__,
            'executor_args': {
                'cluster': self.cluster,
                'image': self.image,
                'resources': self.resources,
            }
        }

    @classmethod
    def deserialize(cls, serialized):
        """
        Creates a Task from a serialized task.

        NOTE This method is unsafe and should not be run on untrusted
        serializations. See Task.safe_deserialize() instead.
        """
        obj = prefect.utilities.serialize.deserialize(serialized['serialized'])
        if not isinstance(obj, cls):
            raise TypeError(
                'Expected {}; received {}'.format(
                    cls.__name__, type(obj).__name__))
        return obj

    @classmethod
    def safe_deserialize(cls, serialized):
        """
        Creates a dummy Task that approximates the serialized task.
        """
        return Task(
            name=serialized['name'],
            max_retries=serialized['max_retries'],
            trigger=getattr(prefect.triggers, serialized['trigger'], None),
            # executor_args
        )

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
        """
        raise NotImplementedError()

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
        self.name = task.name
        self.index = index

    def _repr_index(self):
        return '[{}]'.format(self.index if self.index is not None else ':')

    def __repr__(self):
        return 'TaskResult({}{})'.format(self.task.name, self._repr_index())
