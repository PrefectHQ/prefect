import copy
import hashlib
import inspect
import itertools
import random
import tempfile
import uuid
from collections import Counter
from contextlib import contextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    AnyStr,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Union,
)

import graphviz
import jsonpickle
from mypy_extensions import TypedDict

import prefect
import prefect.schedules
from prefect.core.edge import Edge
from prefect.core.task import Parameter, Task
from prefect.utilities.json import Serializable
from prefect.utilities.tasks import as_task

ParameterDetails = TypedDict("ParameterDetails", {"default": Any, "required": bool})


class Flow(Serializable):
    def __init__(
        self,
        name: str = None,
        version: str = None,
        project: str = None,
        schedule: prefect.schedules.Schedule = None,
        description: str = None,
        environment: prefect.environments.Environment = None,
        tasks: Iterable[Task] = None,
        edges: Iterable[Edge] = None,
    ) -> None:

        self.name = name or type(self).__name__
        self.version = version or prefect.config.flows.default_version
        self.project = project or prefect.config.flows.default_project
        self.description = description or None
        self.schedule = schedule or prefect.schedules.NoSchedule()
        self.environment = environment

        self.tasks = set()  # type: Set[Task]
        self.edges = set()  # type: Set[Edge]
        self.set_key_tasks([])

        for t in tasks or []:
            self.add_task(t)

        for e in edges or []:
            self.add_edge(
                upstream_task=e.upstream_task,
                downstream_task=e.downstream_task,
                key=e.key,
            )

        self._prefect_version = prefect.__version__

        super().__init__()

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            s = (self.name, self.version, self.tasks, self.edges, self.key_tasks())
            o = (other.name, other.version, other.tasks, other.edges, other.key_tasks())
            return s == o
        return False

    def __repr__(self) -> str:
        template = (
            "<{cls}: project={self.project}, name={self.name}, version={self.version}>"
        )
        return template.format(cls=type(self).__name__, self=self)

    def __iter__(self) -> Iterable[Task]:
        yield from self.sorted_tasks()

    # Identification  ----------------------------------------------------------

    def copy(self) -> "Flow":
        new = copy.copy(self)
        new.tasks = self.tasks.copy()
        new.edges = self.edges.copy()
        new.set_key_tasks(self._key_tasks)
        return new

    # Context Manager ----------------------------------------------------------

    def __enter__(self) -> "Flow":
        self.__previous_flow = prefect.context.get("_flow")
        prefect.context.update(_flow=self)
        return self

    def __exit__(self, _type, _value, _tb) -> None:  # type: ignore
        del prefect.context._flow
        if self.__previous_flow is not None:
            prefect.context.update(_flow=self.__previous_flow)

        del self.__previous_flow

    # Introspection ------------------------------------------------------------

    def root_tasks(self) -> Set[Task]:
        """
        Returns the root tasks of the Flow -- tasks that have no upstream
        dependencies.
        """
        return set(t for t in self.tasks if not self.edges_to(t))

    def terminal_tasks(self) -> Set[Task]:
        """
        Returns the terminal tasks of the Flow -- tasks that have no downstream
        dependencies.
        """
        return set(t for t in self.tasks if not self.edges_from(t))

    def parameters(self, only_required=False) -> Dict[str, ParameterDetails]:
        """
        Returns details about any Parameters of this flow
        """
        return {
            t.name: {"required": t.required, "default": t.default}
            for t in self.tasks
            if isinstance(t, Parameter) and (t.required if only_required else True)
        }

    def key_tasks(self) -> Set[Task]:
        """
        A flow's "key tasks" are used to determine its state when it runs. If all the key
        tasks are successful, then the flow run is considered successful. However, if
        any of the key tasks fail, the flow is considered to fail. (Note that skips are
        counted as successes.)

        By default, a flow's key tasks are its terminal tasks. This means the state of a
        flow is determined by the last tasks that run.

        In some situations, users may want to customize that behavior; for example, if a
        flow's terminal tasks are "clean up" tasks for the rest of the flow. The
        flow.set_key_tasks() method can be used to set custom key_tasks.

        Please note that even if key_tasks are provided that are not terminal tasks, the flow
        will not be considered "finished" until all terminal tasks have completed. Only then
        will state be determined, using the key tasks.
        """
        if self._key_tasks:
            return set(self._key_tasks)
        else:
            return self.terminal_tasks()

    def set_key_tasks(self, tasks: Iterable[Task]) -> None:
        """
        Sets the "key tasks" for the flow. See flow.key_tasks() for more details.

        Args:
            - tasks ([Task]): the tasks that should be set as a flow's key tasks.
        """
        key_tasks = set(tasks)
        if any(t not in self.tasks for t in key_tasks):
            raise ValueError("Key tasks must be part of the flow.")
        self._key_tasks = key_tasks

    # Graph --------------------------------------------------------------------

    def add_task(self, task: Task) -> Task:
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

        self.tasks.add(task)

        return task

    def add_edge(
        self,
        upstream_task: Task,
        downstream_task: Task,
        key: str = None,
        validate: bool = None,
    ) -> Edge:

        if isinstance(downstream_task, Parameter):
            raise ValueError(
                "Parameters must be root tasks and can not have upstream dependencies."
            )

        self.add_task(upstream_task)
        self.add_task(downstream_task)

        # we can only check the downstream task's edges once it has been added to the
        # flow, so we need to perform this check here and not earlier.
        if key and key in {e.key for e in self.edges_to(downstream_task)}:
            raise ValueError(
                'Argument "{a}" for task {t} has already been assigned in '
                "this flow. If you are trying to call the task again with "
                "new arguments, call Task.copy() before adding the result "
                "to this flow.".format(a=key, t=downstream_task)
            )

        edge = Edge(
            upstream_task=upstream_task, downstream_task=downstream_task, key=key
        )
        self.edges.add(edge)

        # check that the edges are valid keywords by binding them
        if key is not None:
            edge_keys = {
                e.key: None for e in self.edges_to(downstream_task) if e.key is not None
            }
            inspect.signature(downstream_task.run).bind_partial(**edge_keys)

        # check for cycles
        if validate is None:
            validate = prefect.config.flows.eager_edge_validation

        if validate:
            self.validate()

        return edge

    def chain(self, *tasks, validate: bool = None) -> List[Edge]:
        """
        Adds a sequence of dependent tasks to the flow.
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

    def all_upstream_edges(self) -> Dict[Task, Set[Edge]]:
        edges = {t: set() for t in self.tasks}  # type: Dict[Task, Set[Edge]]
        for edge in self.edges:
            edges[edge.downstream_task].add(edge)
        return edges

    def all_downstream_edges(self) -> Dict[Task, Set[Edge]]:
        edges = {t: set() for t in self.tasks}  # type: Dict[Task, Set[Edge]]
        for edge in self.edges:
            edges[edge.upstream_task].add(edge)
        return edges

    def edges_to(self, task: Task) -> Set[Edge]:
        if task not in self.tasks:
            raise ValueError(
                "Task {t} was not found in Flow {f}".format(t=task, f=self)
            )
        return self.all_upstream_edges()[task]

    def edges_from(self, task: Task) -> Set[Edge]:
        if task not in self.tasks:
            raise ValueError(
                "Task {t} was not found in Flow {f}".format(t=task, f=self)
            )
        return self.all_downstream_edges()[task]

    def upstream_tasks(self, task: Task) -> Set[Task]:
        return set(e.upstream_task for e in self.edges_to(task))

    def downstream_tasks(self, task: Task) -> Set[Task]:
        return set(e.downstream_task for e in self.edges_from(task))

    def validate(self) -> None:
        """
        Checks the flow for cycles and raises an error if one is found.
        """
        self.sorted_tasks()

    def sorted_tasks(self, root_tasks: Iterable[Task] = None) -> Tuple[Task, ...]:

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
        validate: bool = None,
    ) -> None:
        """
        Convenience function for adding task dependencies on upstream tasks.

        Args:
            task (Object): a Task that will become part of the Flow. If the task is not a
                Task subclass, Prefect will attempt to convert it to one.

            upstream_tasks ([object]): Tasks that will run before the task runs. If any task
                is not a Task subclass, Prefect will attempt to convert it to one.

            downstream_tasks ([object]): Tasks that will run after the task runs. If any task
                is not a Task subclass, Prefect will attempt to convert it to one.

            keyword_tasks ({key: object}): The results of these tasks
                will be provided to the task under the specified keyword
                arguments. If any task is not a Task subclass, Prefect will attempt to
                convert it to one.
        """

        task = as_task(task)
        assert isinstance(task, Task)  # mypy assert

        # add the main task (in case it was called with no arguments)
        self.add_task(task)

        # add upstream tasks
        for t in upstream_tasks or []:
            t = as_task(t)
            assert isinstance(t, Task)  # mypy assert
            self.add_edge(upstream_task=t, downstream_task=task, validate=validate)

        # add downstream tasks
        for t in downstream_tasks or []:
            t = as_task(t)
            assert isinstance(t, Task)  # mypy assert
            self.add_edge(upstream_task=task, downstream_task=t, validate=validate)

        # add data edges to upstream tasks
        for key, t in (keyword_tasks or {}).items():
            t = as_task(t)
            assert isinstance(t, Task)  # mypy assert
            self.add_edge(
                upstream_task=t, downstream_task=task, key=key, validate=validate
            )

    # Execution  ---------------------------------------------------------------

    def run(
        self,
        parameters: Dict[str, Any] = None,
        return_tasks: Iterable[Task] = None,
        **kwargs
    ) -> "prefect.engine.state.State":
        """
        Run the flow.
        """
        runner = prefect.engine.flow_runner.FlowRunner(flow=self)
        parameters = parameters or []

        passed_parameters = {}
        for p in self.parameters():
            if p in kwargs:
                passed_parameters[p] = kwargs.pop(p)
            elif p in parameters:
                passed_parameters[p] = parameters[p]

        state = runner.run(
            parameters=passed_parameters, return_tasks=return_tasks, **kwargs
        )

        # state always should return a dict of tasks. If it's None (meaning the run was
        # interrupted before any tasks were executed), we set the dict manually.
        if state.result is None:
            state.result = {}
        for task in return_tasks or []:
            if task not in state.result:
                state.result[task] = prefect.engine.state.Pending(
                    message="Task not run."
                )
        return state

    # Serialization ------------------------------------------------------------

    def _generate_obj_ids(self) -> dict:
        obj_ids = {}
        for task in self.tasks:
            obj_ids[task] = str(uuid.uuid4())

        return obj_ids

    def serialize(self) -> dict:

        # Generate obj_ids for the tasks
        obj_ids = self._generate_obj_ids()

        return dict(
            name=self.name,
            version=self.version,
            project=self.project,
            description=self.description,
            environment=self.environment,
            parameters=self.parameters(),
            schedule=self.schedule,
            key_tasks=self.key_tasks(),
            tasks=[dict(obj_id=obj_ids[t], **t.serialize()) for t in self.tasks],
            edges=[
                dict(
                    upstream_task_obj_id=obj_ids[e.upstream_task],
                    downstream_task_obj_id=obj_ids[e.downstream_task],
                    key=e.key,
                )
                for e in self.edges
            ],
        )

    # Visualization ------------------------------------------------------------

    def visualize(self):
        graph = graphviz.Digraph()

        for t in self.tasks:
            graph.node(str(id(t)), t.name)

        for e in self.edges:
            graph.edge(str(id(e.upstream_task)), str(id(e.downstream_task)), e.key)

        with tempfile.NamedTemporaryFile() as tmp:
            graph.render(tmp.name, view=True)

    # IDs ------------------------------------------------------------

    def generate_flow_id(self) -> str:
        """
        Flows are identified by their name and version.
        """
        hash_bytes = get_hash("{}:{}".format(self.name, self.version or ""))
        return str(uuid.UUID(bytes=hash_bytes))

    def generate_task_ids(self) -> Dict["Task", str]:
        final_hashes = {}

        # --- initial pass
        # for each task, generate a hash based on that task's attributes
        hashes = {t: get_hash(t) for t in self.tasks}
        counter = Counter(hashes.values())

        # --- forward pass #1
        # for each task in order:
        # - if the task hash is unique, put it in final_hashes
        # - if not, hash the task with the hash of all incoming edges
        # the result is a hash that represents each task in terms of all ancestors since the
        # last uniquely defined task.
        for t in self.sorted_tasks():
            if counter[hashes[t]] == 1:
                final_hashes[t] = hashes[t]
                continue

            edge_hashes = sorted(
                (e.key, hashes[e.upstream_task]) for e in self.edges_to(t)
            )
            hashes[t] = get_hash((hashes[t], edge_hashes))
            counter[hashes[t]] += 1

        # --- backward pass
        # for each task in reverse order:
        # - if the task hash is unique, put it in final_hashes
        # - if not, hash the task with the hash of all outgoing edges
        # the result is a hash that represents each task in terms of both its ancestors (from
        # the foward pass) and also any descendents.
        for t in reversed(self.sorted_tasks()):
            if counter[hashes[t]] == 1:
                final_hashes[t] = hashes[t]
                continue

            edge_hashes = sorted(
                (e.key, hashes[e.downstream_task]) for e in self.edges_from(t)
            )
            hashes[t] = get_hash(str((hashes[t], edge_hashes)))
            counter[hashes[t]] += 1

        # --- forward pass #2
        # for each task in order:
        # - if the task hash is unique, put it in final_hashes
        # if not, hash the task with the hash of all incoming edges.
        # define each task in terms of the computational path of every task it's
        # connected to
        #
        # any task that is still a duplicate at this stage is TRULY a duplicate;
        # there is nothing about its computational path that differentiates it.
        # We can randomly choose one and modify its hash (and the hash of all
        # following tasks) without consequence.
        for t in self.sorted_tasks():
            if counter[hashes[t]] == 1:
                final_hashes[t] = hashes[t]
                continue

            edge_hashes = sorted(
                (e.key, hashes[e.upstream_task]) for e in self.edges_to(t)
            )
            hashes[t] = get_hash(str((hashes[t], edge_hashes)))
            counter[hashes[t]] += 1

            # duplicate check
            while counter[hashes[t]] > 1:
                hashes[t] = get_hash(hashes[t])
                counter[hashes[t]] += 1
            final_hashes[t] = hashes[t]

        seed = uuid.UUID(self.generate_flow_id()).bytes

        return {t: str(uuid.UUID(bytes=xor(seed, h))) for t, h in final_hashes.items()}


def get_hash(obj: object) -> bytes:
    """
    Returns a deterministic set of bytes for a given input.
    """
    if isinstance(obj, bytes):
        return hashlib.md5(obj).digest()
    elif isinstance(obj, str):
        return hashlib.md5(obj.encode()).digest()
    elif isinstance(obj, Task):
        obj = prefect.core.task.get_task_info(obj)
    elif isinstance(obj, Edge):
        obj = dict(
            upstream=prefect.core.task.get_task_info(obj.upstream_task),
            downstream=prefect.core.task.get_task_info(obj.downstream_task),
            key=obj.key,
        )
    return hashlib.md5(jsonpickle.dumps(obj).encode()).digest()


def xor(hash1: bytes, hash2: bytes) -> bytes:
    """
    Computes the bitwise XOR between two byte hashes
    """
    return bytes([x ^ y for x, y in zip(hash1, itertools.cycle(hash2))])
