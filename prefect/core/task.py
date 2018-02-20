import importlib
from datetime import timedelta
import json
from typing import Iterable, Mapping

from slugify import slugify

import prefect
from prefect.utilities.serialize import (
    Encrypted,
    Serializable,
    serialize_to_encrypted_pickle,
)
# from prefect.utilities.datetimes import retry_delay
from prefect.utilities.strings import name_with_suffix


class Task(Serializable):
    """
    Tasks are basic units of work. Each task performs a specific funtion.
    """

    serialize_encrypted = True
    serialize_restore_fields = ['parent']

    @prefect.context.apply_context_annotations
    def __init__(
            self,
            name=None,
            parent=None,
            description=None,
            max_retries=0,
            retry_delay=timedelta(minutes=5),
            timeout=None,
            trigger=None,
            flow: prefect.context.Annotations.flow = None,
            autorename=False,
            upstream_tasks=None,
            downstream_tasks=None,
            upstream_results=None):
        """

        Args:

            name (str): a name for the Task

            parent (str): a '.'-delimited chain of parents. This can be modified
                by context.

            description (str): a description of the task. Markdown is supported.

            retry_delay (timedelta): the time to wait before retrying the task.

            timeout (timedelta): the maximum amount of time the task is allowed
                to run. Note that while a task will be considered FAILED if it
                exceeds this time limit, it may not be possible to actually
                halt a task once it starts.

            max_retries: the number of times this task can be retried. -1
                indicates an infinite number of times.

            serializer (Serializer): the class used to serialize and
                deserialize the task result.

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
        elif name is None:
            name = type(self).__name__
        if not isinstance(name, str):
            raise ValueError(
                'Name is invalid or could not be inferred '
                'from Flow: "{}"'.format(name))
        self.name = name
        self._init_args['name'] = name

        context_parent = prefect.context.Context.get('task_parent')
        if context_parent:
            parent = context_parent + '.' + parent
        self.parent = parent
        self.description = description or ''

        self.retry_delay = retry_delay
        self.timeout = timeout
        self.max_retries = max_retries

        # set up up trigger
        if trigger is None:
            trigger = prefect.tasks.triggers.AllSuccessful
        if not isinstance(trigger, prefect.tasks.triggers.Trigger):
            raise TypeError('Trigger must be a Trigger subclass.')
        self.trigger = trigger

        # misc
        self._indexed_results_cache = {}

        # add the task to the flow
        if flow:
            flow.add_task(self)

            self.set(
                upstream_tasks=upstream_tasks,
                downstream_tasks=downstream_tasks,
                flow=flow,
                **(upstream_results or {}))

    @property
    def slug(self):
        return slugify(self.name)

    def __repr__(self):
        if type(self).__name__ == self.name:
            return self.name
        else:
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

    def __call__(self, *tasks, downstream_tasks=None, **upstream_results):
        return self.set(
            upstream_tasks=tasks,
            downstream_tasks=downstream_tasks,
            **upstream_results)

    #TODO set a type annotation for Flow
    def set(
            self,
            *,
            upstream_tasks: Iterable['Task'] = None,
            downstream_tasks: Iterable['Task'] = None,
            flow=None,
            **upstream_results: Mapping[str, 'Task']):
        """
        Create dependencies between tasks or (optionally) task outputs

        Args:
            upstream_tasks ([Task]): A list of tasks that will run before this
                task runs.

            downstream_tasks ([Task]): A list of tasks that will run after this
                task runs.

            flow: The flow in which to set these dependencies. If none is
                provided it will be inferred from the Prefect context.

            **upstream_results ({str: Task}): The result of each task in this
                dictionary will be provided to this task when it runs as the
                specified keyword argument.

        """
        if flow is None:
            flow = prefect.context.Context.get('flow')
        if not flow:
            raise ValueError(
                'Dependencies can only be set within an active Flow context.')

        flow.set_dependencies(
            task=self,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            upstream_results=upstream_results)

        return self

    def run_after(self, *upstream_tasks, **upstream_results):
        """
        Adds a dependency to the Flow so that this task runs after other
        tasks, optionally receiving their results at runtime as keyword
        arguments.

        Tasks that are provided as kwarg results do not also have to be
        supplied as upstream tasks.

        Args:
            *upstream_tasks (Task[]): The provided tasks will become upstream
                dependencies of this task.

            **upstream_results (dict[kwarg, Task]): The provided tasks will become
                upstream dependencies of this task AND their results will be
                provided to this task as the specified keyword argument.
        """
        self.set(upstream_tasks=upstream_tasks, **upstream_results)
        return self

    def run_before(self, *downstream_tasks):
        """
        Adds a dependency to the Flow so that this task runs before other
        tasks.

        Args:
            downstream_tasks (Task[]): The provided tasks will become downstream
                dependencies of this task.
        """
        self.set(downstream_tasks=downstream_tasks)
        return self

    # Serialize ---------------------------------------------------------------

    def serialize(self):
        serialized = super().serialize()

        serialized.update(
            dict(
                name=self.name,
                slug=self.slug,
                parent=self.parent,
                description=self.description,
                max_retries=self.max_retries,
                retry_delay=self.retry_delay,
                timeout=self.timeout,
                trigger=self.trigger,
                type=type(self).__name__,
                serialized=serialize_to_encrypted_pickle(self)
            ))

        return serialized

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
                    cls.__name__,
                    type(obj).__name__))
        return obj

    @classmethod
    def safe_deserialize(cls, serialized):
        """
        Creates a dummy Task that approximates the serialized task.
        """
        return Task(
            name=serialized['name'],
            max_retries=serialized['max_retries'],
            trigger=getattr(
                prefect.tasks.triggers, serialized['trigger'], None),
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
