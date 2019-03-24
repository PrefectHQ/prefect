import collections
import copy
import functools
import inspect
import json
import tempfile
import time
import uuid
import warnings
from collections import Counter
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

import pendulum
import xxhash
from mypy_extensions import TypedDict

import prefect
import prefect.schedules
from prefect.core.edge import Edge
from prefect.core.task import Parameter, Task
from prefect.engine.result import NoResult
from prefect.engine.result_handlers import ResultHandler
from prefect.environments import Environment
from prefect.utilities import logging
from prefect.utilities.notifications import callback_factory
from prefect.utilities.serialization import to_qualified_name
from prefect.utilities.tasks import as_task, unmapped

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
    The Flow class is used as the representation of a collection of dependent Tasks.
    Flows track Task dependencies, parameters and provide the main API for constructing and managing workflows.

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
        - environment (prefect.environments.Environment, optional): The environment
            type that the flow should be run in. If None, a LocalEnvironment will be created.
        - tasks ([Task], optional): If provided, a list of tasks that will initialize the flow
        - edges ([Edge], optional): A list of edges between tasks
        - reference_tasks ([Task], optional): A list of tasks which determine the final
            state of a flow
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the flow changes state, providing an
            opportunity to inspect or modify the new state. The handler
            will be passed the flow instance, the old (prior) state, and the new
            (current) state, with the following signature:
                `state_handler(flow: Flow, old_state: State, new_state: State) -> Optional[State]`
            If multiple functions are passed, then the `new_state` argument will be the
            result of the previous handler.
        - on_failure (Callable, optional): A function with signature `fn(flow: Flow, state: State) -> None`
            which will be called anytime this Flow enters a failure state
        - validate (bool, optional): Whether or not to check the validity of
            the flow (e.g., presence of cycles and illegal keys) after adding the edges passed
            in the `edges` argument. Defaults to the value of `eager_edge_validation` in
            your prefect configuration file.
        - result_handler (ResultHandler, optional): the handler to use for
            retrieving and storing state results during execution; if not provided, will default
            to the one specified in your config

    """

    def __init__(
        self,
        name: str,
        schedule: prefect.schedules.Schedule = None,
        environment: Environment = None,
        tasks: Iterable[Task] = None,
        edges: Iterable[Edge] = None,
        reference_tasks: Iterable[Task] = None,
        state_handlers: List[Callable] = None,
        on_failure: Callable = None,
        validate: bool = None,
        result_handler: ResultHandler = None,
    ):
        self._cache = {}  # type: dict

        # set random id
        self.id = str(uuid.uuid4())

        self.logger = logging.get_logger("Flow")

        if not name:
            raise ValueError("A name must be provided for the flow.")

        self.name = name
        self.schedule = schedule
        self.environment = environment or prefect.environments.LocalEnvironment()
        self.result_handler = (
            result_handler or prefect.engine.get_default_result_handler_class()()
        )

        self.tasks = set()  # type: Set[Task]
        self.edges = set()  # type: Set[Edge]

        for t in tasks or []:
            self.add_task(t)

        self.set_reference_tasks(reference_tasks or [])
        for e in edges or []:
            self.add_edge(
                upstream_task=e.upstream_task,
                downstream_task=e.downstream_task,
                key=e.key,
                mapped=e.mapped,
                validate=validate,
            )

        self._prefect_version = prefect.__version__

        if state_handlers and not isinstance(state_handlers, collections.Sequence):
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
        # create new id
        new.id = str(uuid.uuid4())
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
            - [Task]: a list of tasks which meet the required conditions
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

        new = as_task(new)

        # update tasks
        self.tasks.remove(old)
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

    @property
    def id(self) -> str:
        return self._id

    @id.setter
    def id(self, value: str) -> None:
        """
        Args:
            - value (str): a UUID-formatted string
        """
        try:
            uuid.UUID(value)
        except Exception:
            raise ValueError("Badly formatted UUID string: {}".format(value))
        self._id = value

    @property  # type: ignore
    @cache
    def task_ids(self) -> Dict[str, Task]:
        """
        Returns a dictionary of {task_id: Task} pairs.
        """
        return {task.id: task for task in self.tasks}

    # Context Manager ----------------------------------------------------------

    def __enter__(self) -> "Flow":
        self.__previous_flow = prefect.context.get("flow")
        prefect.context.update(flow=self)
        return self

    def __exit__(self, _type, _value, _tb) -> None:  # type: ignore
        del prefect.context.flow
        if self.__previous_flow is not None:
            prefect.context.update(flow=self.__previous_flow)

        del self.__previous_flow

    # Introspection ------------------------------------------------------------

    @cache
    def root_tasks(self) -> Set[Task]:
        """
        Get the tasks in the flow that have no upstream dependencies; these are
        the tasks which, by default, flow execution begins with.

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

    def reference_tasks(self) -> Set[Task]:
        """
        A flow's "reference tasks" are used to determine its state when it runs. If all the reference
        tasks are successful, then the flow run is considered successful. However, if
        any of the reference tasks fail, the flow is considered to fail. (Note that skips are
        counted as successes; see [the state documentation](../engine/state.html) for a full description
        of what is considered failure, success, etc.)

        By default, a flow's reference tasks are its terminal tasks. This means the state of a
        flow is determined by those tasks which have no downstream dependencies.

        In some situations, users may want to customize this behavior; for example, if a
        flow's terminal tasks are "clean up" tasks for the rest of the flow that only run
        if certain (more relevant) tasks fail, we might not want them determining the overall
        state of the flow run. The `flow.set_reference_tasks()` method can be used to set such custom `reference_tasks`.

        Please note that even if `reference_tasks` are provided that are not terminal tasks, the flow
        will not be considered "finished" until all terminal tasks have completed. Only then
        will state be determined, using the reference tasks.

        Returns:
            - set of Task objects which are the reference tasks in the flow
        """
        if self._reference_tasks:
            return set(self._reference_tasks)
        else:
            return self.terminal_tasks()

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
            if task.slug and task.slug in [t.slug for t in self.tasks]:
                raise ValueError(
                    'A task with the slug "{}" already exists in this '
                    "flow.".format(task.slug)
                )

        if task not in self.tasks:
            self.tasks.add(task)
            self._cache.clear()

        return task

    def add_edge(
        self,
        upstream_task: Task,
        downstream_task: Task,
        key: str = None,
        mapped: bool = False,
        validate: bool = None,
    ) -> Edge:
        """
        Add an edge in the flow between two tasks. All edges are directed beginning with
        an upstream task and ending with a downstream task.

        Args:
            - upstream_task (Task): The task that the edge should start from
            - downstream_task (Task): The task that the edge should end with
            - key (str, optional): The key to be set for the new edge; this is
                the argument name the result of the upstream task will be bound to in the
                `run()` method of the downstream task
            - mapped (bool, optional): Whether this edge represents a call to `Task.map()`; defaults to `False`
            - validate (bool, optional): Whether or not to check the validity of
                the flow (e.g., presence of cycles and illegal keys). Defaults to the value
                of `eager_edge_validation` in your prefect configuration file.

        Returns:
            - prefect.core.edge.Edge: The `Edge` object that was successfully added to the flow

        Raises:
            - ValueError: if the `downstream_task` is of type `Parameter`
            - ValueError: if the edge exists with this `key` and `downstream_task`
        """
        if validate is None:
            validate = cast(bool, prefect.config.flows.eager_edge_validation)
        if isinstance(downstream_task, Parameter):
            raise ValueError(
                "Parameters must be root tasks and can not have upstream dependencies."
            )

        self.add_task(upstream_task)
        self.add_task(downstream_task)

        # we can only check the downstream task's edges once it has been added to the
        # flow, so we need to perform this check here and not earlier.
        if validate and key and key in {e.key for e in self.edges_to(downstream_task)}:
            raise ValueError(
                'Argument "{a}" for task {t} has already been assigned in '
                "this flow. If you are trying to call the task again with "
                "new arguments, call Task.copy() before adding the result "
                "to this flow.".format(a=key, t=downstream_task)
            )

        edge = Edge(
            upstream_task=upstream_task,
            downstream_task=downstream_task,
            key=key,
            mapped=mapped,
        )
        self.edges.add(edge)

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
                the flow (e.g., presence of cycles).  Defaults to the value of `eager_edge_validation`
                in your prefect configuration file.

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

    def update(self, flow: "Flow", validate: bool = None) -> None:
        """
        Take all tasks and edges in another flow and add it to this flow

        Args:
            - flow (Flow): A flow which is used to update this flow
            - validate (bool, optional): Whether or not to check the validity of the flow

        Returns:
            - None
        """
        for task in flow.tasks:
            if task not in self.tasks:
                self.add_task(task)

        for edge in flow.edges:
            if edge not in self.edges:
                self.add_edge(
                    upstream_task=edge.upstream_task,
                    downstream_task=edge.downstream_task,
                    key=edge.key,
                    validate=validate,
                )

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
            - dict with the key as the task passed in and the value as a set of all edges
            leading to that task

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
            - dict with the key as the task passed in and the value as a set of all edges
            leading from that task

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
        task: object,
        upstream_tasks: Iterable[object] = None,
        downstream_tasks: Iterable[object] = None,
        keyword_tasks: Mapping[str, object] = None,
        mapped: bool = False,
        validate: bool = None,
    ) -> None:
        """
        Convenience function for adding task dependencies.

        Args:
            - task (object): a Task that will become part of the Flow. If the task is not a
                Task subclass, Prefect will attempt to convert it to one.
            - upstream_tasks ([object], optional): Tasks that will run before the task runs. If any task
                is not a Task subclass, Prefect will attempt to convert it to one.
            - downstream_tasks ([object], optional): Tasks that will run after the task runs. If any task
                is not a Task subclass, Prefect will attempt to convert it to one.
            - keyword_tasks ({key: object}, optional): The results of these tasks
                will be provided to the task under the specified keyword
                arguments. If any task is not a Task subclass, Prefect will attempt to
                convert it to one.
            - mapped (bool, optional): Whether the upstream tasks (both keyed
                and non-keyed) should be mapped over; defaults to `False`. If `True`, any
                tasks wrapped in the `prefect.utilities.tasks.unmapped` container will
                _not_ be mapped over.
            - validate (bool, optional): Whether or not to check the validity of
                the flow (e.g., presence of cycles).  Defaults to the value of `eager_edge_validation`
                in your prefect configuration file.

        Returns:
            - None
        """

        task = as_task(task)
        assert isinstance(task, Task)  # mypy assert

        # add the main task (in case it was called with no arguments)
        self.add_task(task)

        # add upstream tasks
        for t in upstream_tasks or []:
            is_mapped = mapped & (not isinstance(t, unmapped))
            t = as_task(t)
            assert isinstance(t, Task)  # mypy assert
            self.add_edge(
                upstream_task=t,
                downstream_task=task,
                validate=validate,
                mapped=is_mapped,
            )

        # add downstream tasks
        for t in downstream_tasks or []:
            t = as_task(t)
            assert isinstance(t, Task)  # mypy assert
            self.add_edge(upstream_task=task, downstream_task=t, validate=validate)

        # add data edges to upstream tasks
        for key, t in (keyword_tasks or {}).items():
            is_mapped = mapped & (not isinstance(t, unmapped))
            t = as_task(t)
            assert isinstance(t, Task)  # mypy assert
            self.add_edge(
                upstream_task=t,
                downstream_task=task,
                key=key,
                validate=validate,
                mapped=is_mapped,
            )

    # Execution  ---------------------------------------------------------------

    def _run_on_schedule(
        self, parameters: Dict[str, Any], runner_cls: type, **kwargs: Any
    ) -> "prefect.engine.state.State":

        ## determine time of first run
        try:
            if self.schedule is not None:
                next_run_time = self.schedule.next(1)[0]
            else:
                next_run_time = pendulum.now("utc")
        except IndexError:
            raise ValueError("Flow has no more scheduled runs.") from None

        ## setup initial states
        flow_state = prefect.engine.state.Scheduled(start_time=next_run_time, result={})
        flow_state = kwargs.pop("state", flow_state)
        if not isinstance(flow_state.result, dict):
            flow_state.result = {}
        task_states = kwargs.pop("task_states", {})
        flow_state.result.update(task_states)

        ## run this flow indefinitely, so long as its schedule has future dates
        while True:
            if flow_state.is_scheduled():
                next_run_time = flow_state.start_time
                now = pendulum.now("utc")
                naptime = max((next_run_time - now).total_seconds(), 0)
                if naptime > 0:
                    self.logger.info(
                        "Waiting for next scheduled run at {}".format(next_run_time)
                    )
                time.sleep(naptime)

            ## begin a single flow run
            while not flow_state.is_finished():
                runner = runner_cls(flow=self)
                flow_state = runner.run(
                    parameters=parameters,
                    return_tasks=self.tasks,
                    state=flow_state,
                    task_states=flow_state.result,
                    **kwargs
                )
                if not isinstance(flow_state.result, dict):
                    return flow_state  # something went wrong

                task_states = list(flow_state.result.values())
                for s in filter(lambda x: x.is_mapped(), task_states):
                    task_states.extend(s.map_states)
                earliest_start = min(
                    [s.start_time for s in task_states if s.is_scheduled()],
                    default=pendulum.now("utc"),
                )

                ## wait until first task is ready for retry
                now = pendulum.now("utc")
                naptime = max((earliest_start - now).total_seconds(), 0)
                if naptime > 0:
                    self.logger.info(
                        "Waiting for next available Task run at {}".format(
                            earliest_start
                        )
                    )
                time.sleep(naptime)

            ## create next scheduled run
            try:
                if self.schedule is not None:
                    next_run_time = self.schedule.next(1)[0]
                else:
                    break
            except IndexError:
                break
            flow_state = prefect.engine.state.Scheduled(
                start_time=next_run_time, result={}
            )
        return flow_state

    def run(
        self, parameters: Dict[str, Any] = None, runner_cls: type = None, **kwargs: Any
    ) -> "prefect.engine.state.State":
        """
        Run the flow on its schedule using an instance of a FlowRunner.  If the Flow has no schedule,
        a single stateful run will occur (including retries).

        Note that this command will block and run this Flow on its schedule indefinitely (if it has one);
        all task states will be stored in memory, and task retries will not occur until every Task in the Flow has had a chance
        to run.

        Args:
            - parameters (Dict[str, Any], optional): values to pass into the runner
            - runner_cls (type): an optional FlowRunner class (will use the default if not provided)
            - **kwargs: additional keyword arguments; if any provided keywords
                match known parameter names, they will be used as such. Otherwise they will be passed to the
                `FlowRunner.run()` method

        Raises:
            - ValueError: if this Flow has a Schedule with no more scheduled runs
            - ValueError: if the `return_tasks` keyword argument is provided

        Returns:
            - State: the state of the flow after its final run
        """
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

        state = self._run_on_schedule(
            parameters=parameters, runner_cls=runner_cls, **kwargs
        )

        # state always should return a dict of tasks. If it's NoResult (meaning the run was
        # interrupted before any tasks were executed), we set the dict manually.
        if state.result == NoResult:
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

    def visualize(self, flow_state: "prefect.engine.state.State" = None) -> object:
        """
        Creates graphviz object for representing the current flow; this graphviz
        object will be rendered inline if called from an IPython notebook, otherwise
        it will be rendered in a new window.

        Args:
            - flow_state (State, optional): flow state object used to optionally color the nodes

        Raises:
            - ImportError: if `graphviz` is not installed
        """

        try:
            import graphviz
        except ImportError:
            msg = (
                "This feature requires graphviz.\n"
                "Try re-installing prefect with `pip install prefect[viz]`"
            )
            raise ImportError(msg)

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
                for map_index, _ in enumerate(flow_state.result[t].map_states):
                    kwargs = dict(
                        color=get_color(t, map_index=map_index),
                        style="filled",
                        colorscheme="svg",
                    )
                    graph.node(str(id(t)) + str(map_index), name, shape=shape, **kwargs)
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
                for map_index, _ in enumerate(
                    flow_state.result[e.downstream_task].map_states
                ):
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

        try:
            from IPython import get_ipython

            if get_ipython().config.get("IPKernelApp") is not None:
                return graph
        except Exception:
            pass

        with tempfile.NamedTemporaryFile() as tmp:
            graph.render(tmp.name, view=True)

        return graph

    # Building / Serialization ----------------------------------------------------

    def to_environment_file(self, path: str) -> None:
        """
        Serializes the flow as an environment file.

        Args:
            - path (str): the path of the environment file to create
        """
        self.environment.build(self).to_file(path)

    def serialize(self, build: bool = False) -> dict:
        """
        Creates a serialized representation of the flow.

        Args:
            - build (bool, optional): if `True`, the flow's environment is built
                prior to serialization

        Returns:
            - dict representing the flow
        """

        self.validate()
        schema = prefect.serialization.flow.FlowSchema
        serialized = schema(exclude=["environment"]).dump(self)

        if build:
            environment = self.environment.build(
                flow=self
            )  # type: Optional[Environment]
        else:
            environment = self.environment

        serialized.update(
            schema(only=["environment"]).dump({"environment": environment})
        )

        return serialized

    def generate_local_task_ids(
        self, *, _debug_steps: bool = False
    ) -> Dict["Task", bytes]:
        """
        Generates stable IDs for each task that track across flow versions

        If our goal was to create an ID for each task, we would simply produce a random
        hash. However, we would prefer to generate deterministic IDs. That way, identical
        flows will have the same task ids and near-identical flows will have overlapping
        task ids.

        If all tasks were unique, we could simply produce unique IDs by hashing the tasks
        themselves. However, Prefect allows duplicate tasks in a flow. Therefore, we take a
        few steps to iteratively produce unique IDs. There are five steps, and tasks go
        through each step until they have a unique ID:

            1. Generate an ID from the task's attributes.
                This fingerprints a task in terms of its own attributes.
            2. Generate an ID from the task's ancestors.
                This fingerprints a task in terms of the computational graph leading to it.
            3. Generate an ID from the task's descendents
                This fingerprints a task in terms of how it is used in a computational graph.
            4. Iteratively generate an ID from the task's neighbors
                This fingerprints a task in terms of a widening concentric circle of its neighbors.
            5. Adjust a root task's ID and recompute all non-unique descendents
                This step is only reached if a flow contains more than one unconnected but
                identical computational paths. The previous 4 steps are unable to distinguish
                between those two paths, so we pick one at random and adjust the leading tasks'
                IDs, as well as all following tasks. This is safe because we are sure that the
                computational paths are identical.

        Args:
            - flow (Flow)
            - _debug_steps (bool, optional): if True, the function will return a dictionary of
                {step_number: ids_produced_at_step} pairs, where ids_produced_at_step is the
                id dict following that step. This is used for debugging/testing only.

        Returns:
            - dict: a dictionary of {task: task_id} pairs
        """

        # precompute flow properties since we'll need to access them repeatedly
        tasks = self.sorted_tasks()
        edges_to = self.all_upstream_edges()
        edges_from = self.all_downstream_edges()

        # dictionary to hold debug information
        debug_steps = {}

        # -- Step 1 ---------------------------------------------------
        #
        # Generate an ID for each task by hashing:
        # - its flow's name
        #
        # This "fingerprints" each task in terms of its own characteristics
        #
        # -----------------------------------------------------------

        ids = {}
        for t in tasks:
            serialized = t.serialize()
            del serialized["id"]  # remove the ID since it is unique but random
            ids[t] = _hash(json.dumps(serialized, sort_keys=True))

        if _debug_steps:
            debug_steps[1] = ids.copy()

        # -- Step 2 ---------------------------------------------------
        #
        # Next, we iterate over the tasks in topological order and, for any task without
        # a unique ID, produce a new ID based on its current ID and the ID of any
        # upstream nodes. This fingerprints each task in terms of all its ancestors.
        #
        # -----------------------------------------------------------

        counter = Counter(ids.values())
        for task in tasks:
            if counter[ids[task]] == 1:
                continue

            # create a new id by hashing (task id, upstream edges, downstream edges)
            edges = sorted((e.key, ids[e.upstream_task]) for e in edges_to[task])
            ids[task] = _hash(str((ids[task], edges)))

        if _debug_steps:
            debug_steps[2] = ids.copy()

        # -- Step 3 ---------------------------------------------------
        #
        # Next, we iterate over the tasks in reverse topological order and, for any task
        # without a unique ID, produce a new ID based on its current ID and the ID of
        # any downstream nodes. After this step, each task is fingerprinted by its
        # position in a computational chain (both ancestors and descendents).
        #
        # -----------------------------------------------------------

        counter = Counter(ids.values())
        for task in reversed(tasks):
            if counter[ids[task]] == 1:
                continue

            # create a new id by hashing (task id, upstream edges, downstream edges)
            edges = sorted((e.key, ids[e.downstream_task]) for e in edges_from[task])
            ids[task] = _hash(str((ids[task], edges)))

        if _debug_steps:
            debug_steps[3] = ids.copy()

        # -- Step 4 ---------------------------------------------------
        #
        # It is still possible for tasks to have duplicate IDs. For example, the
        # following flow of identical tasks would not be able to differentiate between
        # y3 and z3 after a forward and backward pass.
        #
        #               x1 -> x2 -> x3 -> x4
        #                  \
        #               y1 -> y2 -> y3 -> y4
        #                  \
        #               z1 -> z2 -> z3 -> z4
        #
        # We could continue running forward and backward passes to diffuse task
        # dependencies through the graph, but that approach is inefficient and
        # introduces very long dependency chains. Instead, we take each task and produce
        # a new ID by hashing it with the IDs of all of its upstream and downstream
        # neighbors.
        #
        # Each time we repeat this step, the non-unique task ID incorporates information
        # from tasks farther and farther away, because its neighbors are also updating
        # their IDs from their own neighbors. (note that we could use this algorithm
        # exclusively, but starting with a full forwards and backwards pass is much
        # faster!)
        #
        # However, it is still possible for this step to fail to generate a unique ID
        # for every task. The simplest example of this case is a flow with two
        # unconnected but identical tasks; the algorithm will be unable to differentiate
        # between the two based solely on their neighbors.
        #
        # Therefore, we continue updating IDs in this step only until the number of
        # unique IDs stops increasing. At that point, any remaining duplicates can not
        # be distinguished on the basis of neighboring nodes.
        #
        # -----------------------------------------------------------

        counter = Counter(ids.values())

        # continue this algorithm as long as the number of unique ids keeps changing
        while True:

            # store the number of unique ids at the beginning of the loop
            starting_unique_id_count = len(counter)

            for task in tasks:

                # if the task already has a unique id, just go to the next one
                if counter[ids[task]] == 1:
                    continue

                # create a new id by hashing the task ID with upstream dn downstream IDs
                edges = [  # type: ignore
                    sorted((e.key, ids[e.upstream_task]) for e in edges_to[task]),
                    sorted((e.key, ids[e.downstream_task]) for e in edges_from[task]),
                ]
                ids[task] = _hash(str((ids[task], edges)))

            # recompute a new counter.
            # note: we can't do this incremenetally because we can't guarantee the
            # iteration order, and incremental updates would implicitly depend on order
            counter = Counter(ids.values())

            # if the new counter has the same number of unique IDs as the old counter,
            # then the algorithm is no longer able to produce useful ids
            if len(counter) == starting_unique_id_count:
                break

        if _debug_steps:
            debug_steps[4] = ids.copy()

        # -- Step 5 ---------------------------------------------------
        #
        # If the number of unique IDs is less than the number of tasks at this stage, it
        # means that the algorithm in step 4 was unable to differentiate between some
        # tasks. This is only possible if the self contains identical but unconnected
        # computational paths.
        #
        # To remedy this, we change the ids of the duplicated root tasks until they are
        # unique, then recompute the ids of all downstream tasks. While this chooses the
        # affected root task at random, we are confident that the tasks are exact
        # duplicates so this is of no consequence.
        #
        # -----------------------------------------------------------

        while len(counter) < len(tasks):
            for task in tasks:
                # recompute each task's ID until it is unique
                while counter[ids[task]] != 1:
                    edges = sorted(
                        (e.key, ids[e.upstream_task]) for e in edges_to[task]
                    )
                    ids[task] = _hash(str((ids[task], edges)))
                    counter[ids[task]] += 1

        if _debug_steps:
            debug_steps[5] = ids.copy()
            return debug_steps  # type: ignore

        return ids

    # Deployment ------------------------------------------------------------------

    def deploy(self, project_name: str, set_schedule_active: bool = False) -> str:
        """
        Deploy the flow to Prefect Cloud

        Args:
            - project_name (str): the project that should contain this flow.
            - set_schedule_active (bool, optional): if `True`, will set the
                schedule to active in the database and begin scheduling runs (if the Flow has a schedule).
                Defaults to `False`. This can be changed later.

        Returns:
            - str: the ID of the flow that was deployed
        """
        client = prefect.Client()
        deployed_flow = client.deploy(
            flow=self,
            project_name=project_name,
            set_schedule_active=set_schedule_active,
        )
        return deployed_flow


def _hash(value: str) -> bytes:
    return xxhash.xxh64(value).digest()
