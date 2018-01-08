import importlib

from slugify import slugify

import prefect
from prefect.utilities.datetimes import retry_delay
from prefect.utilities.strings import name_with_suffix


class Task:
    """
    Tasks are basic units of work. Each task performs a specific funtion.
    """

    def __new__(base, *args, **kwargs):
        """
        Each Task tracks the arguments that were used to create it. These
        variables are available as Task._init_args and Task._init_kwargs.
        """
        instance = super().__new__(base)
        instance._init_args = args
        instance._init_kwargs = kwargs
        return instance

    def __init__(
            self,
            name=None,
            description=None,
            max_retries=0,
            retry_delay=retry_delay(minutes=5),
            trigger=None,
            serializer=None,
            flow=None,
            resources=None,
            image=None,
            autorename=False,
            cluster=None,
    ):
        """

        Args:

            description (str): a description of the task. Markdown is supported.

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

            autorename (bool): if True, the task will automatically have a
                suffix added to its name if it conflicts with an existing
                task in the flow


        """

        # see if this task was created inside a flow context
        flow = flow or prefect.context.Context.get('flow')

        # if a flow was provided, try to infer a name
        if flow and (name is None or autorename):
            if name is None:
                name = type(self).__name__
            name = name_with_suffix(
                name,
                predicate=lambda n: n not in flow.tasks,
                first_suffix=2,
                delimiter='-')

        if not isinstance(name, str):
            raise ValueError(
                'Name is invalid or could not be inferred '
                'from provided Flow: {}'.format(name))
        self.name = name
        self.description = description or ''

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
                importlib.import_module(default_module), default_class)
            serializer = serializer_class()
        self.serializer = serializer

        # misc
        self.resources = resources or {}
        self.image = image
        self.cluster = cluster
        self._indexed_results_cache = {}

        # add the task to the flow
        if flow:
            flow.add_task(self)

    @property
    def slug(self):
        return slugify(self.name)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.name)

    # Comparison --------------------------------------------------------------

    def __eq__(self, other):
        """
        Equality is determined by examining the serialized Task
        """
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

    def __call__(self, *tasks, **kwarg_tasks):
        return self.run_after(*tasks, **kwarg_tasks)

    def run_after(self, *tasks, **kwarg_tasks):
        """
        Adds a relationship to the Flow so that this task runs after other
        tasks, optionally receiving their results at runtime as keyword
        arguments.

        Args:
            *tasks (Task[]): The provided tasks will become upstream
                dependencies of this task.

            **kwarg_tasks (dict[kwarg, Task]): The provided tasks will become
                upstream dependencies of this task AND their results will be
                provided to this task as the specified keyword argument.
        """
        flow = prefect.context.Context.get('flow')
        if not flow:
            raise ValueError(
                'This function can only be called inside a Flow context')
        flow.set_up_task(
            task=self, upstream_tasks=tasks, upstream_results=kwarg_tasks)

        return self

    def run_before(self, *tasks, kwarg=None):
        """
        Adds a relationship to the Flow so that this task runs before other
        tasks.

        Args:
            tasks (Task[]): The provided tasks will become downstream
                dependencies of this task.

            kwarg (str): If provided, this task's result will be provided
                to any downstream tasks under the specified keyword argument.
        """
        flow = prefect.context.Context.get('flow')
        if not flow:
            raise ValueError(
                'This function can only be called inside a Flow context')

        if kwarg:
            if not isinstance(kwarg, str):
                raise TypeError('kwarg must be a string.')
            upstream_results = {kwarg: self}
        else:
            upstream_results = None

        for t in tasks:
            flow.set_up_task(
                task=t,
                upstream_tasks=[self],
                upstream_results=upstream_results)

        return self

    def then(self, task, kwarg=None):
        """
        Create simple dependency chains by linking tasks:
            task1.then(task2, kwarg=t1).then(task3)

        Args:
            task (Task): The task that should run after this one
            kwarg (str): If provided, this task's result will be provided to
                the downstream task under this keyword argument.

        Returns:
            The downstream task (`task`)
        """
        self.run_before(task, kwarg=kwarg)
        return task

    # Serialize ---------------------------------------------------------------

    def serialize(self):
        return {
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
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
        """
        Indexing a task automatically creates an IndexR
        """
        from prefect.tasks.core import IndexResultTask

        name = '{}[{}]'.format(self.name, index)
        # use a cache so we can reuse IndexResultTasks when possible
        if name not in self._indexed_results_cache:
            self._indexed_results_cache[name] = IndexResultTask(
                index=index, name=name)
            self._indexed_results_cache[name].run_after(upstream_task=self)
        return self._indexed_results_cache[name]

    # Sugar -------------------------------------------------------------------

    def __or__(self, task):
        """
        self | task -> self.run_before(task)
        """
        self.run_before(task)
        return task

    def __ror__(self, task):
        """
        task | self -> self.run_after(task)
        """
        self.run_after(task)
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
