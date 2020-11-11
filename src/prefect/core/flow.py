import collections
import collections.abc
import copy
import functools
import hashlib
import inspect
import json
import os
import tempfile
import time
import uuid
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    cast,
    Union,
)

import cloudpickle
import pendulum
from mypy_extensions import TypedDict
from slugify import slugify

import prefect
import prefect.schedules
from prefect.core.edge import Edge
from prefect.core.parameter import Parameter
from prefect.core.task import Task
from prefect.engine.executors import Executor
from prefect.engine.result import NoResult, Result
from prefect.engine.result_handlers import ResultHandler
from prefect.engine.results import ResultHandlerResult
from prefect.environments import Environment
from prefect.environments.storage import Storage, get_default_storage_class
from prefect.run_configs import RunConfig
from prefect.utilities import diagnostics, logging
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.notifications import callback_factory
from prefect.utilities.tasks import as_task

ParameterDetails = TypedDict("ParameterDetails", {"default": Any, "required": bool})


def cache(method: Callable) -> Callable:
    """
    Decorator for caching Flow methods.

    Each Flow has a _cache dict that can be used to memoize expensive functions. This
    decorator automatically compares a hash of the Flow's current tasks, edges, and reference_tasks
    to a cached hash; if the hash is the same, it attempts to retrieve a value from the cache.
    If the hash is different, it invalidates the cache.
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):  # type: ignore

        cache_check = dict(
            tasks=self.tasks.copy(),
            edges=self.edges.copy(),
            reference_tasks=copy.copy(self._reference_tasks),
        )
        if any(self._cache.get(k) != v for k, v in cache_check.items()):
            self._cache.clear()
            self._cache.update(cache_check)

        callargs = inspect.signature(method).bind(self, *args, **kwargs).arguments
        key = (method.__name__, tuple(callargs.items())[1:])
        if key not in self._cache:
            self._cache[key] = method(self, *args, **kwargs)
        return self._cache[key]

    return wrapper


class Flow:
    """
    The Flow class is used as the representation of a collection of dependent Tasks.  Flows
    track Task dependencies, parameters and provide the main API for constructing and managing
    workflows.

    Initializing Flow example:
    ```python
    class MyTask(Task):
        def run(self):
            return "hello"

    task_1 = MyTask()
    flow = Flow(name="my_flow", tasks=[task_1])

    flow.run()
    ```

    Initializing Flow as context manager example:
    ```python
    @task
    def my_task():
        return "hello"

    with Flow("my_flow") as flow:
        task_1 = my_task()

    flow.run()
    ```

    Args:
        - name (str): The name of the flow. Cannot be `None` or an empty string
        - schedule (prefect.schedules.Schedule, optional): A default schedule for the flow
        - executor (prefect.engine.executors.Executor, optional): The executor that the flow
           should use. If `None`, the default executor configured in the runtime environment
           will be used.
        - environment (prefect.environments.Environment, optional): The environment
           that the flow should be run in. If `None`, a `LocalEnvironment` will be created.
        - run_config (prefect.run_configs.RunConfig, optional): The runtime
           configuration to use when deploying this flow.
        - storage (prefect.environments.storage.Storage, optional): The unit of storage
            that the flow will be written into.
        - tasks ([Task], optional): If provided, a list of tasks that will initialize the flow
        - edges ([Edge], optional): A list of edges between tasks
        - reference_tasks ([Task], optional): A list of tasks that determine the final
            state of a flow
        - result (Result, optional, RESERVED FOR FUTURE USE): the result instance used to
            retrieve and store task results during execution
        - result_handler (ResultHandler, optional, DEPRECATED): the handler to use for
            retrieving and storing state results during execution
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the flow changes state, providing an
            opportunity to inspect or modify the new state. The handler
            will be passed the flow instance, the old (prior) state, and the new
            (current) state, with the following signature:
                `state_handler(flow: Flow, old_state: State, new_state: State) -> Optional[State]`
            If multiple functions are passed, then the `new_state` argument will be the
            result of the previous handler.
        - on_failure (Callable, optional): A function with signature `fn(flow: Flow, state:
            State) -> None` which will be called anytime this Flow enters a failure state
        - validate (bool, optional): Whether or not to check the validity of
            the flow (e.g., presence of cycles and illegal keys) after adding the edges passed
            in the `edges` argument. Defaults to the value of `eager_edge_validation` in
            your prefect configuration file.
    """

    def __init__(
        self,
        name: str,
        schedule: prefect.schedules.Schedule = None,
        executor: Executor = None,
        environment: Environment = None,
        run_config: RunConfig = None,
        storage: Storage = None,
        tasks: Iterable[Task] = None,
        edges: Iterable[Edge] = None,
        reference_tasks: Iterable[Task] = None,
        state_handlers: List[Callable] = None,
        on_failure: Callable = None,
        validate: bool = None,
        result_handler: Optional[ResultHandler] = None,
        result: Optional[Result] = None,
    ):
        self._cache = {}  # type: dict

        if not name:
            raise ValueError("A name must be provided for the flow.")

        self.name = name
        self.logger = logging.get_logger(self.name)
        self.schedule = schedule
        self.executor = executor
        self.environment = environment or prefect.environments.LocalEnvironment()
        self.run_config = run_config
        self.storage = storage
        if result_handler:
            warnings.warn(
                "Result Handlers are deprecated; please use the new style Result classes instead.",
                stacklevel=2,
            )
            self.result = ResultHandlerResult.from_result_handler(
                result_handler
            )  # type: Optional[Result]
        else:
            self.result = result

        self.tasks = set()  # type: Set[Task]
        self.edges = set()  # type: Set[Edge]
        self.slugs = dict()  # type: Dict[Task, str]
        self.constants = collections.defaultdict(
            dict
        )  # type: Dict[Task, Dict[str, Any]]

        for t in tasks or []:
            self.add_task(t)

        self.set_reference_tasks(reference_tasks or [])
        for e in edges or []:
            self.add_edge(
                upstream_task=e.upstream_task,
                downstream_task=e.downstream_task,
                key=e.key,
                mapped=e.mapped,
                flattened=e.flattened,
                validate=validate,
            )

        self._prefect_version = prefect.__version__

        if state_handlers and not isinstance(state_handlers, collections.abc.Sequence):
            raise TypeError("state_handlers should be iterable.")
        self.state_handlers = state_handlers or []
        if on_failure is not None:
            self.state_handlers.append(
                callback_factory(on_failure, check=lambda s: s.is_failed())
            )

        super().__init__()

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            s = (self.name, self.tasks, self.edges, self.reference_tasks())
            o = (other.name, other.tasks, other.edges, other.reference_tasks())
            return s == o
        return False

    def __repr__(self) -> str:
        template = '<{cls}: name="{self.name}">'
        return template.format(cls=type(self).__name__, self=self)

    def __iter__(self) -> Iterable[Task]:
        yield from self.sorted_tasks()

    def copy(self) -> "Flow":
        """
        Create and returns a copy of the current Flow.
        """
        new = copy.copy(self)
        # create a new cache
        new._cache = dict()
        new.constants = self.constants.copy()
        new.tasks = self.tasks.copy()
        new.edges = self.edges.copy()
        new.set_reference_tasks(self._reference_tasks)
        return new

    # Identification -----------------------------------------------------------

    def get_tasks(
        self,
        name: str = None,
        slug: str = None,
        tags: Iterable[str] = None,
        task_type: type = None,
    ) -> List[Task]:
        """
        Helper method for retrieving tasks from this flow based on certain attributes.
        The _intersection_ of all provided attributes is taken, i.e., only those tasks
        which match _all_ provided conditions are returned.

        Args:
            - name (str, optional): the name of the task
            - slug (str, optional): the slug of the task
            - tags ([str], optional): an iterable of task tags
            - task_type (type, optional): a possible task class type

        Returns:
            - [Task]: a list of tasks that meet the required conditions
        """

        def sieve(t: Task) -> bool:
            keep = True
            if name is not None:
                keep &= t.name == name
            if slug is not None:
                keep &= t.slug == slug
            if tags is not None:
                keep &= t.tags.issuperset(tags)
            if task_type is not None:
                keep &= isinstance(t, task_type)
            return keep

        keep_tasks = filter(sieve, self.tasks)
        return list(keep_tasks)

    def replace(self, old: Task, new: Task, validate: bool = True) -> None:
        """
        Performs an inplace replacement of the old task with the provided new task.

        Args:
            - old (Task): the old task to replace
            - new (Task): the new task to replace the old with; if not a Prefect
                Task, Prefect will attempt to convert it to one
            - validate (boolean, optional): whether to validate the Flow after
                the replace has been completed; defaults to `True`

        Raises:
            - ValueError: if the `old` task is not a part of this flow
        """
        if old not in self.tasks:
            raise ValueError("Task {t} was not found in Flow {f}".format(t=old, f=self))

        new = as_task(new, flow=self)

        # update tasks
        self.tasks.remove(old)
        self.slugs.pop(old)
        self.add_task(new)

        self._cache.clear()

        affected_edges = {e for e in self.edges if old in e.tasks}

        # remove old edges
        for edge in affected_edges:
            self.edges.remove(edge)

        # replace with new edges
        for edge in affected_edges:
            upstream = new if edge.upstream_task == old else edge.upstream_task
            downstream = new if edge.downstream_task == old else edge.downstream_task
            self.add_edge(
                upstream_task=upstream,
                downstream_task=downstream,
                key=edge.key,
                mapped=edge.mapped,
                flattened=edge.flattened,
                validate=False,
            )

        # update auxiliary task collections
        ref_tasks = self.reference_tasks()
        new_refs = [t for t in ref_tasks if t != old] + (
            [new] if old in ref_tasks else []
        )
        self.set_reference_tasks(new_refs)

        if validate:
            self.validate()

    # Context Manager ----------------------------------------------------------

    @contextmanager
    def _flow_context(self) -> Iterator["Flow"]:
        """
        When entering a flow context, the Prefect context is modified to include:
            - `flow`: the flow itself
            - `_unused_task_tracker`: a set of all tasks created while the context is
                open, in order to provide user friendly warnings if they aren't added
                to the flow itself. This is purely for user experience.
        """
        unused_task_tracker = set()  # type: Set[Task]

        with prefect.context(flow=self, _unused_task_tracker=unused_task_tracker):
            yield self

        if unused_task_tracker.difference(self.tasks):
            warnings.warn(
                "Tasks were created but not added to the flow: "
                f"{unused_task_tracker.difference(self.tasks)}. This can occur "
                "when `Task` classes, including `Parameters`, are instantiated "
                "inside a `with flow:` block but not added to the flow either "
                "explicitly or as the input to another task. For more information, see "
                "https://docs.prefect.io/core/advanced_tutorials/"
                "task-guide.html#adding-tasks-to-flows.",
                stacklevel=2,
            )

    def __enter__(self) -> "Flow":
        self._ctx = self._flow_context()
        return self._ctx.__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore
        self._ctx.__exit__(exc_type, exc_value, traceback)
        # delete _ctx because it's an active generator, which prevents pickling
        del self._ctx

    # Introspection ------------------------------------------------------------

    @cache
    def root_tasks(self) -> Set[Task]:
        """
        Get the tasks in the flow that have no upstream dependencies; these are
        the tasks that, by default, flow execution begins with.

        Returns:
            - set of Task objects that have no upstream dependencies
        """
        return set(t for t in self.tasks if not self.edges_to(t))

    @cache
    def terminal_tasks(self) -> Set[Task]:
        """
        Get the tasks in the flow that have no downstream dependencies

        Returns:
            - set of Task objects that have no downstream dependencies
        """
        return set(t for t in self.tasks if not self.edges_from(t))

    def parameters(self) -> Set[Parameter]:
        """
        Returns any parameters of the flow.

        Returns:
            - set: a set of any Parameters in this flow
        """
        return {p for p in self.tasks if isinstance(p, Parameter)}

    @cache
    def _default_reference_tasks(self) -> Set[Task]:
        from prefect.tasks.core.resource_manager import ResourceCleanupTask

        # Select all tasks that aren't ResourceCleanupTasks and have no
        # downstream dependencies that aren't ResourceCleanupTasks
        #
        # Note: this feels a bit gross, since it special cases a certain
        # subclass inside the flow runner. If this behavior expands to other
        # classes we should think of a general way of indicating this on a Task
        # class instead of special casing.
        return {
            t
            for t in self.tasks
            if not isinstance(t, ResourceCleanupTask)
            and not any(
                t
                for t in self.downstream_tasks(t)
                if not isinstance(t, ResourceCleanupTask)
            )
        }

    def reference_tasks(self) -> Set[Task]:
        """
        A flow's "reference tasks" are used to determine its state when it runs. If all the
        reference tasks are successful, then the flow run is considered successful. However, if
        any of the reference tasks fail, the flow is considered to fail. (Note that skips are
        counted as successes; see [the state documentation](../engine/state.html) for a full
        description of what is considered failure, success, etc.)

        By default, a flow's reference tasks are its terminal tasks. This means the state of a
        flow is determined by those tasks that have no downstream dependencies.

        In some situations, users may want to customize this behavior; for example, if a flow's
        terminal tasks are "clean up" tasks for the rest of the flow that only run if certain
        (more relevant) tasks fail, we might not want them determining the overall state of the
        flow run. The `flow.set_reference_tasks()` method can be used to set such custom
        `reference_tasks`.

        Please note that even if `reference_tasks` are provided that are not terminal tasks,
        the flow will not be considered "finished" until all terminal tasks have completed.
        Only then will state be determined, using the reference tasks.

        Returns:
            - set of Task objects which are the reference tasks in the flow
        """
        if self._reference_tasks:
            return set(self._reference_tasks)
        else:
            return self._default_reference_tasks()

    def set_reference_tasks(self, tasks: Iterable[Task]) -> None:
        """
        Sets the `reference_tasks` for the flow. See `flow.reference_tasks` for more details.

        Args:
            - tasks ([Task]): the tasks that should be set as a flow's reference tasks

        Returns:
            - None
        """
        self._cache.clear()
        reference_tasks = set(tasks)
        if any(t not in self.tasks for t in reference_tasks):
            raise ValueError("reference tasks must be part of the flow.")
        self._reference_tasks = reference_tasks

    # Graph --------------------------------------------------------------------

    def _generate_task_slug(self, task: Task) -> str:
        """
        Given a Task, generates the corresponding slug for this Flow.  Slugs are the unique IDs
        the Prefect API uses to track state updates for each task within a Flow.

        The logic for slug generation within a Flow is essentially "name-tags-#count".  Having
        slugs be properties of (Task, Flow) instead of just Task alone allows Prefect to ensure
        that every time you run the same build script for a Flow, the Task slugs remain
        constant.

        Args:
            - task (Task): the task to generate a slug for

        Returns:
            - str: the corresponding slug
        """
        slug_bases = []
        for t in self.tasks:
            slug_bases.append(f"{t.name}-" + "-".join(sorted(t.tags)))
        new_slug = f"{task.name}-" + "-".join(sorted(task.tags))
        index = slug_bases.count(new_slug)
        return f"{new_slug}{'' if new_slug.endswith('-') else '-'}{index + 1}"

    def add_task(self, task: Task) -> Task:
        """
        Add a task to the flow if the task does not already exist. The tasks are
        uniquely identified by their `slug`.

        Args:
            - task (Task): the new Task to be added to the flow

        Returns:
            - Task: the `Task` object passed in if the task was successfully added

        Raises:
            - TypeError: if the `task` is not of type `Task`
            - ValueError: if the `task.slug` matches that of a task already in the flow
        """
        if not isinstance(task, Task):
            raise TypeError(
                "Tasks must be Task instances (received {})".format(type(task))
            )
        elif task not in self.tasks:
            if task.slug and task.slug in self.slugs.values():
                raise ValueError(
                    'A task with the slug "{}" already exists in this '
                    "flow.".format(task.slug)
                )
            self.slugs[task] = task.slug or self._generate_task_slug(task)

            self.tasks.add(task)
            self._cache.clear()

            # Parameters and constants must be root tasks
            # All other new tasks should be added to the current case/resource (if any)
            if not isinstance(task, (Parameter, prefect.tasks.core.constants.Constant)):
                case = prefect.context.get("case", None)
                if case is not None:
                    case.add_task(task, self)
                resource = prefect.context.get("resource", None)
                if resource is not None:
                    resource.add_task(task, self)

        return task

    def add_edge(
        self,
        upstream_task: Any,
        downstream_task: Any,
        key: str = None,
        mapped: bool = False,
        flattened: bool = False,
        validate: bool = None,
    ) -> Edge:
        """
        Add an edge in the flow between two tasks. All edges are directed beginning with
        an upstream task and ending with a downstream task.

        Args:
            - upstream_task (Any): The task that the edge should start from. If
                it is not a `Task`, it will be converted into one.
            - downstream_task (Any): The task that the edge should end with. If
                it is not a `Task`, it will be converted into one.
            - key (str, optional): The key to be set for the new edge; the result of the
                upstream task will be passed to the downstream task's `run()` method under this
                keyword argument
            - mapped (bool, optional): Whether this edge represents a call to `Task.map()`;
                defaults to `False`
            - flattened (bool, optional): Whether the upstream task result is flattened
            - validate (bool, optional): Whether or not to check the validity of the flow
                (e.g., presence of cycles and illegal keys). Defaults to the value of
                `eager_edge_validation` in your prefect configuration file.

        Returns:
            - prefect.core.edge.Edge: The `Edge` object that was successfully added to the flow

        Raises:
            - ValueError: if the `downstream_task` is of type `Parameter`
            - ValueError: if the edge exists with this `key` and `downstream_task`
        """
        if validate is None:
            validate = cast(bool, prefect.config.flows.eager_edge_validation)

        if mapped and prefect.context.get("mapped", False):
            raise ValueError(
                "Cannot set `mapped=True` when running from inside a mapped context"
            )

        if isinstance(downstream_task, Parameter):
            raise ValueError(
                "Parameters must be root tasks and can not have upstream dependencies."
            )

        edge = Edge(
            upstream_task=upstream_task,
            downstream_task=downstream_task,
            key=key,
            mapped=mapped,
            flattened=flattened,
            flow=self,
        )

        # if the edge represents a keyed, unmapped constant, then we can optimize it
        # out of the graph and into the special `constants` dict. We still return the edge
        # object as a description of the relationship.
        if (
            isinstance(edge.upstream_task, prefect.tasks.core.constants.Constant)
            and edge.key
            and not edge.mapped
            and not edge.flattened
        ):
            self.constants[edge.downstream_task].update(
                {edge.key: edge.upstream_task.value}
            )
            self.add_task(edge.downstream_task)
            return edge

        # add the edge
        self.edges.add(edge)

        # add the tasks from the edge (note they may be different than the passed tasks)
        # due to calling `as_task()` inside the Edge constructor
        self.add_task(edge.upstream_task)
        self.add_task(edge.downstream_task)

        # we can only check the downstream task's edges once it has been added to the
        # flow, so we need to perform this check here and not earlier.
        if (
            validate
            and key is not None
            and key in {e.key for e in self.edges_to(downstream_task) if e is not edge}
        ):
            raise ValueError(
                'Argument "{a}" for task {t} has already been assigned in '
                "this flow. If you are trying to call the task again with "
                "new arguments, call Task.copy() before adding the result "
                "to this flow.".format(a=key, t=downstream_task)
            )

        # check that the edges are valid keywords by binding them
        if validate and key is not None:
            edge_keys = {
                e.key: None for e in self.edges_to(downstream_task) if e.key is not None
            }
            inspect.signature(downstream_task.run).bind_partial(**edge_keys)

        self._cache.clear()

        # check for cycles
        if validate:
            self.validate()

        return edge

    def chain(self, *tasks: Task, validate: bool = None) -> List[Edge]:
        """
        Adds a sequence of dependent tasks to the flow; each task should be provided
        as an argument (or splatted from a list).

        Args:
            - *tasks (list): A list of tasks to chain together
            - validate (bool, optional): Whether or not to check the validity of
                the flow (e.g., presence of cycles).  Defaults to the value of
                `eager_edge_validation` in your prefect configuration file.

        Returns:
            - A list of Edge objects added to the flow
        """
        edges = []
        for u_task, d_task in zip(tasks, tasks[1:]):
            edges.append(
                self.add_edge(
                    upstream_task=u_task, downstream_task=d_task, validate=validate
                )
            )
        return edges

    def update(
        self, flow: "Flow", merge_parameters: bool = False, validate: bool = None
    ) -> None:
        """
        Take all tasks and edges in another flow and add it to this flow.
            When `merge_parameters` is set to`True` -- Duplicate parameters in the input `flow`
            are replaced with those in the flow being updated.

        Args:
            - flow (Flow): A flow which is used to update this flow.
            - merge_parameters (bool, False): If `True`, duplicate paramaeters are replaced
                with parameters from the provided flow. Defaults to `False`.
                If `True`, validate will also be set to `True`.
            - validate (bool, optional): Whether or not to check the validity of the flow.

        Returns:
            - None
        """
        if merge_parameters:
            validate = True
            new_parameters = {p.name: p for p in flow.parameters()}
            for p in self.parameters():
                if p.name in new_parameters:
                    self.replace(p, new_parameters[p.name])

        for task in flow.tasks:
            if task not in self.tasks:
                self.add_task(task)

        for edge in flow.edges:
            if edge not in self.edges:
                self.add_edge(
                    upstream_task=edge.upstream_task,
                    downstream_task=edge.downstream_task,
                    key=edge.key,
                    mapped=edge.mapped,
                    flattened=edge.flattened,
                    validate=validate,
                )

        self.constants.update(flow.constants or {})

    @cache
    def all_upstream_edges(self) -> Dict[Task, Set[Edge]]:
        """
        Returns a dictionary relating each task in the Flow to the set of
        all _upstream_ edges for the task

        Returns:
            - dict with the key as tasks and the value as a set of upstream edges
        """
        edges = {t: set() for t in self.tasks}  # type: Dict[Task, Set[Edge]]
        for edge in self.edges:
            edges[edge.downstream_task].add(edge)
        return edges

    @cache
    def all_downstream_edges(self) -> Dict[Task, Set[Edge]]:
        """
        Returns a dictionary relating each task in the Flow to the set of
        all _downstream_ edges for the task

        Returns:
            - dict with the key as tasks and the value as a set of downstream edges
        """
        edges = {t: set() for t in self.tasks}  # type: Dict[Task, Set[Edge]]
        for edge in self.edges:
            edges[edge.upstream_task].add(edge)
        return edges

    def edges_to(self, task: Task) -> Set[Edge]:
        """
        Get all of the edges leading to a task (i.e., the upstream edges)

        Args:
            - task (Task): The task that we want to find edges leading to

        Returns:
            - Set: set of all edges leading from that task

        Raises:
            - ValueError: if `task` is not found in this flow
        """
        if task not in self.tasks:
            raise ValueError(
                "Task {t} was not found in Flow {f}".format(t=task, f=self)
            )
        return self.all_upstream_edges()[task]

    def edges_from(self, task: Task) -> Set[Edge]:
        """
        Get all of the edges leading from a task (i.e., the downstream edges)

        Args:
            - task (Task): The task that we want to find edges leading from

        Returns:
            - Set: set of all edges leading from that task

        Raises:
            - ValueError: if `task` is not found in this flow
        """
        if task not in self.tasks:
            raise ValueError(
                "Task {t} was not found in Flow {f}".format(t=task, f=self)
            )
        return self.all_downstream_edges()[task]

    def upstream_tasks(self, task: Task) -> Set[Task]:
        """
        Get all of the tasks upstream of a task

        Args:
            - task (Task): The task that we want to find upstream tasks of

        Returns:
            - set of Task objects which are upstream of `task`
        """
        return set(e.upstream_task for e in self.edges_to(task))

    def downstream_tasks(self, task: Task) -> Set[Task]:
        """
        Get all of the tasks downstream of a task

        Args:
            - task (Task): The task that we want to find downstream tasks from

        Returns:
            - set of Task objects which are downstream of `task`
        """
        return set(e.downstream_task for e in self.edges_from(task))

    def validate(self) -> None:
        """
        Checks that the flow is valid.

        Returns:
            - None

        Raises:
            - ValueError: if edges refer to tasks that are not in this flow
            - ValueError: if specified reference tasks are not in this flow
            - ValueError: if any tasks do not have assigned IDs
        """

        self._cache.clear()

        if any(e.upstream_task not in self.tasks for e in self.edges) or any(
            e.downstream_task not in self.tasks for e in self.edges
        ):
            raise ValueError("Some edges refer to tasks not contained in this flow.")

        self.sorted_tasks()

        if any(t not in self.tasks for t in self.reference_tasks()):
            raise ValueError("Some reference tasks are not contained in this flow.")

    def sorted_tasks(self, root_tasks: Iterable[Task] = None) -> Tuple[Task, ...]:
        """
        Get the tasks in this flow in a sorted manner. This allows us to find if any
        cycles exist in this flow's DAG.

        Args:
            - root_tasks ([Tasks], optional): an `Iterable` of `Task` objects to
            start the sorting from

        Returns:
            - tuple of task objects that were sorted

        Raises:
            - ValueError: if a cycle is found in the flow's DAG
        """
        return self._sorted_tasks(root_tasks=tuple(root_tasks or []))

    @cache
    def _sorted_tasks(self, root_tasks: Tuple[Task, ...] = None) -> Tuple[Task, ...]:
        """
        Computes a topological sort of the flow's tasks.

        Flow.sorted_tasks() can accept non-hashable arguments and therefore can't be
        cached, so this private method is called and cached instead.
        """

        # begin by getting all tasks under consideration (root tasks and all
        # downstream tasks)
        if root_tasks:
            tasks = set(root_tasks)
            seen = set()  # type: Set[Task]

            # while the set of tasks is different from the seen tasks...
            while tasks.difference(seen):
                # iterate over the new tasks...
                for t in list(tasks.difference(seen)):
                    # add its downstream tasks to the task list
                    tasks.update(self.downstream_tasks(t))
                    # mark it as seen
                    seen.add(t)
        else:
            tasks = self.tasks

        # build the list of sorted tasks
        remaining_tasks = list(tasks)
        sorted_tasks = []
        while remaining_tasks:
            # mark the flow as cyclic unless we prove otherwise
            cyclic = True

            # iterate over each remaining task
            for task in remaining_tasks.copy():
                # check all the upstream tasks of that task
                for upstream_task in self.upstream_tasks(task):
                    # if the upstream task is also remaining, it means it
                    # hasn't been sorted, so we can't sort this task either
                    if upstream_task in remaining_tasks:
                        break
                else:
                    # but if all upstream tasks have been sorted, we can sort
                    # this one too. We note that we found no cycle this time.
                    cyclic = False
                    remaining_tasks.remove(task)
                    sorted_tasks.append(task)

            # if we were unable to match any upstream tasks, we have a cycle
            if cyclic:
                raise ValueError("Cycle found; flows must be acyclic!")

        return tuple(sorted_tasks)

    # Dependencies ------------------------------------------------------------

    def set_dependencies(
        self,
        task: Any,
        upstream_tasks: Iterable[Any] = None,
        downstream_tasks: Iterable[Any] = None,
        keyword_tasks: Mapping[str, Any] = None,
        mapped: bool = False,
        validate: bool = None,
    ) -> None:
        """
        Convenience function for adding task dependencies.

        Args:
            - task (Any): a Task that will become part of the Flow. If the task is not a
                Task subclass, Prefect will attempt to convert it to one.
            - upstream_tasks ([Any], optional): Tasks that will run before the task runs. If
                any task is not a Task subclass, Prefect will attempt to convert it to one.
            - downstream_tasks ([Any], optional): Tasks that will run after the task runs.
                If any task is not a Task subclass, Prefect will attempt to convert it to one.
            - keyword_tasks ({key: Any}, optional): The results of these tasks
                will be provided to the task under the specified keyword
                arguments. If any task is not a Task subclass, Prefect will attempt to
                convert it to one.
            - mapped (bool, optional): Whether the upstream tasks (both keyed
                and non-keyed) should be mapped over; defaults to `False`. If `True`, any
                tasks wrapped in the `prefect.utilities.edges.unmapped` container will
                _not_ be mapped over.
            - validate (bool, optional): Whether or not to check the validity of the flow
                (e.g., presence of cycles).  Defaults to the value of `eager_edge_validation`
                in your Prefect configuration file.

        Returns:
            - None
        """
        if mapped and prefect.context.get("mapped", False):
            raise ValueError(
                "Cannot set `mapped=True` when running from inside a mapped context"
            )

        task = as_task(task, flow=self)
        assert isinstance(task, Task)  # mypy assert

        # add the main task (in case it was called with no arguments)
        self.add_task(task)

        # add upstream tasks
        for t in upstream_tasks or []:
            self.add_edge(
                upstream_task=t, downstream_task=task, mapped=mapped, validate=validate
            )

        # add downstream tasks
        for t in downstream_tasks or []:
            self.add_edge(upstream_task=task, downstream_task=t, validate=validate)

        # add data edges to upstream tasks
        for key, t in (keyword_tasks or {}).items():
            self.add_edge(
                upstream_task=t,
                downstream_task=task,
                key=key,
                mapped=mapped,
                validate=validate,
            )

    # Execution  ---------------------------------------------------------------

    def _run(
        self,
        parameters: Dict[str, Any],
        runner_cls: type,
        run_on_schedule: bool = True,
        **kwargs: Any,
    ) -> "prefect.engine.state.State":

        base_parameters = parameters or dict()

        # determine time of first run
        try:
            if run_on_schedule and self.schedule is not None:
                next_run_event = self.schedule.next(1, return_events=True)[0]
                next_run_time = next_run_event.start_time  # type: ignore
                parameters = base_parameters.copy()
                parameters.update(next_run_event.parameter_defaults)  # type: ignore
            else:
                next_run_time = pendulum.now("utc")
        except IndexError:
            raise ValueError("Flow has no more scheduled runs.") from None

        # setup initial states
        flow_state = prefect.engine.state.Scheduled(start_time=next_run_time, result={})
        flow_state = kwargs.pop("state", flow_state)
        if not isinstance(flow_state.result, dict):
            flow_state.result = {}
        task_states = kwargs.pop("task_states", {})
        flow_state.result.update(task_states)

        # set context for this flow run
        flow_run_context = kwargs.pop(
            "context", {}
        ).copy()  # copy to avoid modification

        # set flow_run_id from args or uuid if flow_run_id is not an argument
        flow_run_context.setdefault(
            "flow_run_id", kwargs.pop("flow_run_id", str(uuid.uuid4()))
        )

        # set flow_run_name from args or uuid if flow_run_name is not an argument
        flow_run_context.setdefault(
            "flow_run_name", kwargs.pop("flow_run_name", str(uuid.uuid4()))
        )

        # run this flow indefinitely, so long as its schedule has future dates
        while True:

            # add relevant context keys
            # many of these are intended to ensure local runs behave similarly as runs against a backend
            flow_run_context.update(
                scheduled_start_time=next_run_time,
                flow_id=self.name,
                flow_run_id=flow_run_context["flow_run_id"],
                flow_run_name=flow_run_context["flow_run_name"],
            )

            if flow_state.is_scheduled():
                next_run_time = flow_state.start_time
                now = pendulum.now("utc")
                naptime = max((next_run_time - now).total_seconds(), 0)
                if naptime > 0:
                    self.logger.info(
                        "Waiting for next scheduled run at {}".format(next_run_time)
                    )
                time.sleep(naptime)

            error = False

            # begin a single flow run
            while not flow_state.is_finished():
                runner = runner_cls(flow=self)
                task_ctxts = kwargs.pop("task_contexts", {}).copy()
                for t in self.tasks:
                    task_ctxts.setdefault(t, dict())
                    task_ctxts[t].update(
                        task_run_id=str(uuid.uuid4()), task_id=self.slugs[t]
                    )
                flow_state = runner.run(
                    parameters=parameters,
                    return_tasks=self.tasks,
                    state=flow_state,
                    task_states=flow_state.result,
                    context=flow_run_context,
                    task_contexts=task_ctxts,
                    **kwargs,
                )

                # if flow_state is still scheduled; this most likely means
                # that initialize_run failed (possibly due to a connection issue)
                # and so we want to abort instead of creating an infinite loop
                if not isinstance(flow_state.result, dict) or flow_state.is_scheduled():
                    error = True
                    break

                task_states = list(flow_state.result.values())
                for s in filter(lambda x: x.is_mapped(), task_states):
                    task_states.extend(s.map_states)

                # handle Paused states
                for t, s in filter(
                    lambda tup: isinstance(tup[1], prefect.engine.state.Paused),
                    flow_state.result.items(),
                ):
                    approve = input(f"{t} is currently Paused; enter 'y' to resume:\n")
                    if approve.strip().lower() == "y":
                        flow_state.result[t] = prefect.engine.state.Resume(
                            "Approval given to resume."
                        )

                earliest_start = min(
                    [
                        s.start_time
                        for s in task_states
                        if s.is_scheduled() and s.start_time is not None
                    ],
                    default=pendulum.now("utc"),
                )

                # wait until first task is ready for retry
                now = pendulum.now("utc")
                naptime = max((earliest_start - now).total_seconds(), 0)
                if naptime > 0:
                    self.logger.info(
                        "Waiting for next available Task run at {}".format(
                            earliest_start
                        )
                    )
                time.sleep(naptime)

            # create next scheduled run
            if not error:
                # update context cache
                for t, s in flow_state.result.items():
                    if s.is_cached():
                        cached_sub_states = [s]
                    elif s.is_mapped() and any(
                        sub_state.is_cached() for sub_state in s.map_states
                    ):
                        cached_sub_states = [
                            sub_state
                            for sub_state in s.map_states
                            if sub_state.is_cached()
                        ]
                    else:
                        cached_sub_states = []

                    fresh_states = [
                        s
                        for s in prefect.context.caches.get(t.cache_key or t.name, [])
                        + cached_sub_states
                        if s.cached_result_expiration
                        and s.cached_result_expiration > now
                    ]
                    prefect.context.caches[t.cache_key or t.name] = fresh_states

            try:
                if run_on_schedule and self.schedule is not None:
                    next_run_event = self.schedule.next(1, return_events=True)[0]
                    next_run_time = next_run_event.start_time  # type: ignore
                    parameters = base_parameters.copy()
                    parameters.update(next_run_event.parameter_defaults)  # type: ignore
                else:
                    break
            except IndexError:
                # Handle when there are no more events on schedule
                break

            flow_state = prefect.engine.state.Scheduled(
                start_time=next_run_time, result={}
            )
        return flow_state

    def run(
        self,
        parameters: Dict[str, Any] = None,
        run_on_schedule: bool = None,
        runner_cls: type = None,
        **kwargs: Any,
    ) -> Union["prefect.engine.state.State", None]:
        """
        Run the flow on its schedule using an instance of a FlowRunner.  If the Flow has no
        schedule, a single stateful run will occur (including retries).

        Note that this command will block and run this Flow on its schedule indefinitely (if it
        has one); all task states will be stored in memory, and task retries will not occur
        until every Task in the Flow has had a chance to run.

        Args:
            - parameters (Dict[str, Any], optional): values to pass into the runner
            - run_on_schedule (bool, optional): whether to run this flow on its schedule, or
                run a single execution; if not provided, will default to the value set in your
                user config
            - runner_cls (type): an optional FlowRunner class (will use the default if not provided)
            - **kwargs: additional keyword arguments; if any provided keywords match known
                parameter names, they will be used as such. Otherwise they will be passed to
                the `FlowRunner.run()` method

        Raises:
            - ValueError: if this Flow has a Schedule with no more scheduled runs
            - ValueError: if the `return_tasks` keyword argument is provided

        Returns:
            - State: the state of the flow after its final run
        """
        if prefect.context.get("loading_flow", False):
            warnings.warn(
                "Attempting to call `flow.run` during execution of flow file will lead to "
                "unexpected results.",
                stacklevel=2,
            )
            return None

        # protect against old behavior
        if "return_tasks" in kwargs:
            raise ValueError(
                "The `return_tasks` keyword cannot be provided to `flow.run()`; "
                "all task states are always returned. If you want to receive a subset "
                "of task states, use a FlowRunner directly."
            )

        if runner_cls is None:
            runner_cls = prefect.engine.get_default_flow_runner_class()

        # build parameters from passed dictionary and also kwargs
        parameters = parameters or {}
        for p in self.parameters():
            if p.name in kwargs:
                parameters[p.name] = kwargs.pop(p.name)

        # check for parameters that don't match the flow
        unknown_params = [
            p for p in parameters if p not in {fp.name for fp in self.parameters()}
        ]
        if unknown_params:
            fmt_params = ", ".join(unknown_params)
            raise ValueError(
                "Flow.run received the following unexpected parameters: {}".format(
                    fmt_params
                )
            )

        # check for parameters that are required by the flow, but weren't passed
        missing_params = [
            p.name for p in self.parameters() if p.required and p.name not in parameters
        ]
        if missing_params:
            fmt_params = ", ".join(missing_params)
            raise ValueError(
                "Flow.run did not receive the following required parameters: {}".format(
                    fmt_params
                )
            )

        # set global caches that persist across runs
        prefect.context.setdefault("caches", {})

        if run_on_schedule is None:
            run_on_schedule = cast(bool, prefect.config.flows.run_on_schedule)

        state = self._run(
            parameters=parameters,
            runner_cls=runner_cls,
            run_on_schedule=run_on_schedule,
            **kwargs,
        )

        # state always should return a dict of tasks. If it's NoResult (meaning the run was
        # interrupted before any tasks were executed), we set the dict manually.
        if state._result == NoResult:
            state.result = {}
        elif isinstance(state.result, Exception):
            self.logger.error(
                "Unexpected error occured in {runner}: {exc}".format(
                    runner=runner_cls.__name__, exc=repr(state.result)
                )
            )
            return state

        for task in self.tasks or []:
            if task not in state.result:
                state.result[task] = prefect.engine.state.Pending(
                    message="Task not run."
                )
        return state

    # Visualization ------------------------------------------------------------

    def visualize(
        self,
        flow_state: "prefect.engine.state.State" = None,
        filename: str = None,
        format: str = None,
    ) -> Any:
        """
        Creates graphviz object for representing the current flow; this graphviz
        object will be rendered inline if called from an IPython notebook, otherwise
        it will be rendered in a new window.  If a `filename` is provided, the object
        will not be rendered and instead saved to the location specified.

        Args:
            - flow_state (State, optional): flow state object used to optionally color the nodes
            - filename (str, optional): a filename specifying a location to save this
                visualization to; if provided, the visualization will not be rendered
                automatically
            - format (str, optional): a format specifying the output file type; defaults to 'pdf'.
              Refer to http://www.graphviz.org/doc/info/output.html for valid formats

        Raises:
            - ImportError: if `graphviz` is not installed
        """

        try:
            import graphviz
        except ImportError as exc:
            msg = (
                "This feature requires graphviz.\n"
                "Try re-installing prefect with `pip install 'prefect[viz]'`"
            )
            raise ImportError(msg) from exc

        def get_color(task: Task, map_index: int = None) -> str:
            assert flow_state
            assert isinstance(flow_state.result, dict)

            if map_index is not None:
                state = flow_state.result[task].map_states[map_index]
            else:
                state = flow_state.result.get(task)
            if state is not None:
                assert state is not None  # mypy assert
                return state.color + "80"
            return "#00000080"

        graph = graphviz.Digraph()

        for t in self.tasks:
            is_mapped = any(edge.mapped for edge in self.edges_to(t))
            shape = "box" if is_mapped else "ellipse"
            name = "{} <map>".format(t.name) if is_mapped else t.name
            if is_mapped and flow_state:
                assert isinstance(flow_state.result, dict)
                if flow_state.result[t].is_mapped():
                    for map_index, _ in enumerate(flow_state.result[t].map_states):
                        kwargs = dict(
                            color=get_color(t, map_index=map_index),
                            style="filled",
                            colorscheme="svg",
                        )
                        graph.node(
                            str(id(t)) + str(map_index), name, shape=shape, **kwargs
                        )
                else:
                    kwargs = dict(color=get_color(t), style="filled", colorscheme="svg")
                    graph.node(str(id(t)), name, shape=shape, **kwargs)
            else:
                kwargs = (
                    {}
                    if not flow_state
                    else dict(color=get_color(t), style="filled", colorscheme="svg")
                )
                graph.node(str(id(t)), name, shape=shape, **kwargs)

        for e in self.edges:
            style = "dashed" if e.mapped else None
            if (
                e.mapped
                or any(edge.mapped for edge in self.edges_to(e.downstream_task))
            ) and flow_state:
                assert isinstance(flow_state.result, dict)
                down_state = flow_state.result[e.downstream_task]
                if down_state.is_mapped():
                    for map_index, _ in enumerate(down_state.map_states):
                        upstream_id = str(id(e.upstream_task))
                        if any(edge.mapped for edge in self.edges_to(e.upstream_task)):
                            upstream_id += str(map_index)
                        graph.edge(
                            upstream_id,
                            str(id(e.downstream_task)) + str(map_index),
                            e.key,
                            style=style,
                        )
                else:
                    graph.edge(
                        str(id(e.upstream_task)),
                        str(id(e.downstream_task)),
                        e.key,
                        style=style,
                    )
            # this edge represents a "reduce" step from a mapped task -> normal task
            elif flow_state and flow_state.result[e.upstream_task].is_mapped():
                assert isinstance(flow_state.result, dict)  # mypy assert
                up_state = flow_state.result[e.upstream_task]

                for map_index, _ in enumerate(up_state.map_states):
                    downstream_id = str(id(e.downstream_task))
                    if any(edge.mapped for edge in self.edges_to(e.downstream_task)):
                        downstream_id += str(map_index)

                    graph.edge(
                        str(id(e.upstream_task)) + str(map_index),
                        downstream_id,
                        e.key,
                        style=style,
                    )
            else:
                graph.edge(
                    str(id(e.upstream_task)),
                    str(id(e.downstream_task)),
                    e.key,
                    style=style,
                )

        if filename:
            graph.render(filename, view=False, format=format, cleanup=True)
        else:
            try:
                from IPython import get_ipython

                in_ipython = get_ipython().config.get("IPKernelApp") is not None
            except Exception:
                in_ipython = False

            if not in_ipython:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.close()
                    try:
                        graph.render(tmp.name, view=True)
                    except graphviz.backend.ExecutableNotFound as exc:
                        msg = (
                            "It appears you do not have Graphviz installed, or it is not on your "
                            "PATH. Please install Graphviz from http://www.graphviz.org/download/. "
                            "And note: just installing the `graphviz` python package is not "
                            "sufficient!"
                        )
                        raise graphviz.backend.ExecutableNotFound(msg) from exc
                    finally:
                        os.unlink(tmp.name)

        return graph

    # Building / Serialization ----------------------------------------------------

    def serialize(self, build: bool = False) -> dict:
        """
        Creates a serialized representation of the flow.

        Args:
            - build (bool, optional): if `True`, the flow's environment is built
                prior to serialization

        Returns:
            - dict representing the flow

        Raises:
            - ValueError: if `build=True` and the flow has no storage
        """

        self.validate()
        schema = prefect.serialization.flow.FlowSchema

        # because of how our serializers work, we need to make sure that
        # each task has its slug attached as an attribute.  We don't perform this
        # update when the task is added to the flow because the task might get used
        # within another flow (and hence have a different slug)
        flow_copy = self.copy()
        for task, slug in flow_copy.slugs.items():
            task.slug = slug
        serialized = schema(exclude=["storage"]).dump(flow_copy)

        if build:
            if not self.storage:
                raise ValueError("This flow has no storage to build")
            if self.name not in self.storage:
                self.storage.add_flow(self)
            else:
                warnings.warn(
                    "A flow with the same name is already contained in storage; if you "
                    "changed your Flow since the last build, you might experience "
                    "unexpected issues and should re-create your storage object.",
                    stacklevel=2,
                )
            storage = self.storage.build()  # type: Optional[Storage]
        else:
            storage = self.storage

        serialized.update(schema(only=["storage"]).dump({"storage": storage}))

        return serialized

    def serialized_hash(self, build: bool = False) -> str:
        """
        Generate a deterministic hash of the serialized flow. This is useful for
        determining if the flow has changed. If this hash is equal to a previous hash,
        no new information would be passed to the server on a call to `flow.register()`

        Args:
            - build (bool, optional):  if `True`, the flow's environment is built
                prior to serialization. Passed through to `Flow.serialize()`.

        Returns:
            - str: the hash of the serialized flow
        """
        return hashlib.sha256(json.dumps(self.serialize(build)).encode()).hexdigest()

    # Diagnostics  ----------------------------------------------------------------

    def diagnostics(self, include_secret_names: bool = False) -> str:
        """
        Get flow and Prefect diagnostic information

        Args:
            - include_secret_names (bool, optional): toggle output of Secret names, defaults to
                False.  Note: Secret values are never returned, only their names.
        """
        return diagnostics.diagnostic_info(self, include_secret_names)

    # Registration ----------------------------------------------------------------

    @classmethod
    def load(cls, fpath: str) -> "Flow":
        """
        Reads a Flow from a file that was created with `flow.save()`.

        Args:
            - fpath (str): either the absolute filepath where your Flow will be loaded from,
                or the name of the Flow you wish to load
        """
        if not os.path.isabs(fpath):
            path = "{home}/flows".format(home=prefect.context.config.home_dir)  # type: ignore
            fpath = Path(os.path.expanduser(path)) / "{}.prefect".format(  # type: ignore
                slugify(fpath)
            )  # type: ignore
        with open(str(fpath), "rb") as f:
            return cloudpickle.load(f)

    def save(self, fpath: str = None) -> str:
        """
        Saves the Flow to a file by serializing it with cloudpickle.  This method is
        recommended if you wish to separate out the building of your Flow from its registration.

        Args:
            - fpath (str, optional): the filepath where your Flow will be saved; defaults to
                `~/.prefect/flows/FLOW-NAME.prefect`

        Returns:
            - str: the full location the Flow was saved to
        """
        if fpath is None:
            path = "{home}/flows".format(home=prefect.context.config.home_dir)  # type: ignore
            fpath = Path(  # type: ignore
                os.path.expanduser(path)  # type: ignore
            ) / "{}.prefect".format(  # type: ignore
                slugify(self.name)
            )
            assert fpath is not None  # mypy assert
            fpath.parent.mkdir(exist_ok=True, parents=True)
        with open(str(fpath), "wb") as f:
            cloudpickle.dump(self, f)

        return str(fpath)

    def run_agent(
        self, token: str = None, show_flow_logs: bool = False, log_to_cloud: bool = True
    ) -> None:
        """
        Runs a Cloud agent for this Flow in-process.

        Args:
            - token (str, optional): A Prefect Cloud API token with a RUNNER scope;
                will default to the token found in `config.cloud.agent.auth_token`
            - show_flow_logs (bool, optional): a boolean specifying whether the agent should
                re-route Flow run logs to stdout; defaults to `False`
            - log_to_cloud (bool, optional): a boolean specifying whether Flow run logs should
                be sent to Prefect Cloud; defaults to `True`
        """
        temp_config = {
            "cloud.agent.auth_token": token or prefect.config.cloud.agent.auth_token,
            "logging.log_to_cloud": log_to_cloud,
        }
        with set_temporary_config(temp_config):
            if self.run_config is not None:
                labels = list(self.run_config.labels or ())
            else:
                labels = list(self.environment.labels or ())
            agent = prefect.agent.local.LocalAgent(
                labels=labels, show_flow_logs=show_flow_logs
            )
            agent.start()

    def register(
        self,
        project_name: str = None,
        build: bool = True,
        labels: List[str] = None,
        set_schedule_active: bool = True,
        version_group_id: str = None,
        no_url: bool = False,
        idempotency_key: str = None,
        **kwargs: Any,
    ) -> Union[str, None]:
        """
        Register the flow with Prefect Cloud; if no storage is present on the Flow, the default
        value from your config will be used and initialized with `**kwargs`.

        Args:
            - project_name (str, optional): the project that should contain this flow.
            - build (bool, optional): if `True`, the flow's environment is built
                prior to serialization; defaults to `True`
            - labels (List[str], optional): a list of labels to add to this Flow's environment;
                useful for associating Flows with individual Agents; see
                http://docs.prefect.io/orchestration/agents/overview.html#flow-affinity-labels
            - set_schedule_active (bool, optional): if `False`, will set the schedule to
                inactive in the database to prevent auto-scheduling runs (if the Flow has a
                schedule).  Defaults to `True`. This can be changed later.
            - version_group_id (str, optional): the UUID version group ID to use for versioning
                this Flow in Cloud; if not provided, the version group ID associated with this
                Flow's project and name will be used.
            - no_url (bool, optional): if `True`, the stdout from this function will not
                contain the URL link to the newly-registered flow in the Cloud UI
            - idempotency_key (str, optional): a key that, if matching the most recent
                registration call for this flow group, will prevent the creation of
                another flow version and return the existing flow id instead.
            - **kwargs (Any): if instantiating a Storage object from default settings, these
                keyword arguments will be passed to the initialization method of the default
                Storage class

        Returns:
            - str: the ID of the flow that was registered
        """
        if hasattr(self, "_ctx"):
            raise ValueError(
                "Don't call `flow.register()` from within a `Flow` context manager.\n\n"
                "Do:\n\n"
                "  with Flow(...) as flow:\n"
                "      ...\n"
                "  flow.register(...)\n\n"
                "Don't:\n\n"
                "  with Flow(...) as flow:\n"
                "      ...\n"
                "      flow.register(...)"
            )

        if prefect.context.get("loading_flow", False):
            warnings.warn(
                "Attempting to call `flow.register` during execution of flow file will lead "
                "to unexpected results.",
                stacklevel=2,
            )
            return None

        if self.storage is None:
            self.storage = get_default_storage_class()(**kwargs)

        # add auto-labels for various types of storage
        for obj in [self.environment, self.run_config]:
            if obj is not None:
                obj.labels.update(self.storage.labels)
                obj.labels.update(labels or ())

        # register the flow with a default result handler if one not provided
        if not self.result:
            self.result = self.storage.result

        client = prefect.Client()

        registered_flow = client.register(
            flow=self,
            build=build,
            project_name=project_name,
            set_schedule_active=set_schedule_active,
            version_group_id=version_group_id,
            no_url=no_url,
            idempotency_key=idempotency_key,
        )
        return registered_flow

    def __mifflin__(self) -> None:  # coverage: ignore
        "Calls Dunder Mifflin"
        import webbrowser

        webbrowser.open("https://cicdw.github.io/welcome.html")
