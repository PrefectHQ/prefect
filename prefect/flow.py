import copy
import inspect
import tempfile
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

import graphviz

import prefect
from prefect.task import Parameter, Task
from prefect.utilities.functions import cache
from prefect.utilities.json import Serializable
from prefect.utilities.strings import is_valid_identifier
from prefect.utilities.tasks import as_task_result


def flow_cache_key(flow: 'Flow') -> int:
    """
    Returns a cache key that can be used to determine if the cache is stale.
    """
    return hash((frozenset(flow.tasks), frozenset(flow.edges)))


class TaskResult:
    """
    TaskResults represent the execution of a specific task in a given flow.
    """

    def __init__(self, task: Task, flow: 'Flow' = None) -> None:
        if flow is None:
            flow = Flow()
        flow.add_task(task)
        self.task = task
        self.flow = flow

    def __getitem__(self, index) -> Task:
        name = '{}[{}]'.format(self.task.name, index)
        index_task = prefect.tasks.core.operators.GetIndexTask(
            index=index, name=name)
        return index_task(task_result=self)

    def set_dependencies(
            self,
            upstream_tasks: Iterable[Task] = None,
            downstream_tasks: Iterable[Task] = None,
            keyword_results: Dict[str, Task] = None) -> None:

        self.flow.set_dependencies(
            task=self.task,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            keyword_results=keyword_results)

    # def wait_for(self, task_results):
    #     self.set_dependencies(upstream_tasks=task_results)


class Edge:

    def __init__(
            self, upstream_task: Task, downstream_task: Task,
            key: str = None) -> None:
        """
        Edges represent connections between Tasks.

        At a minimum, edges link an upstream_task and a downstream_task
        indicating that the downstream task shouldn't run until the upstream
        task is complete.

        In addition, edges can specify a key that describe how upstream results
        are passed to the downstream task.

        Args: upstream_task (Task): the task that must run before the
            downstream_task

            downstream_task (Task): the task that will be run after the
                upstream_task. The upstream task state is passed to the
                downstream task's trigger function to determine whether the
                downstream task should run.

            key (str): Optional. Passing a key indicates
                that the upstream result should be passed to the downstream
                task as a keyword argument.

        The key indicates that the result of the upstream task should be passed
        to the downstream task under the key.
        """
        self.upstream_task = upstream_task
        self.downstream_task = downstream_task

        if key is not None:
            if not is_valid_identifier(key):
                raise ValueError(
                    'Key must be a valid identifier (received "{}")'.format(
                        key))
        self.key = key

    # Comparison --------------------------------------------------------------

    def __repr__(self) -> str:
        return '<{cls}: {u} to {d}{k}>'.format(
            cls=type(self).__name__,
            u=self.upstream_task,
            d=self.downstream_task,
            k=' (key={})'.format(self.key) if self.key else '')

    def __eq__(self, other: 'Edge') -> bool:
        if type(self) == type(other):
            self_cmp = (self.upstream_task, self.downstream_task, self.key)
            other_cmp = (other.upstream_task, other.downstream_task, other.key)
            return self_cmp == other_cmp
        return False

    def __hash__(self) -> int:
        return id(self)


class Flow(Serializable):

    def __init__(
            self,
            name: str = None,
            version: str = None,
            schedule: 'prefect.schedules.Schedule' = None,
            description: str = None,
            tasks: Iterable[Task] = None,
            edges: Iterable[Edge] = None) -> None:

        self.name = name or type(self).__name__
        self.version = version
        self.description = description
        self.schedule = schedule or prefect.schedules.NoSchedule()

        self.tasks = set()  # type: Set[Task]
        self.edges = set()  # type: Set[Edge]

        for t in tasks or []:
            self.add_task(t)

        for e in edges or []:
            self.add_edge(
                upstream_task=e.upstream_task,
                downstream_task=e.downstream_task,
                key=e.key)

        self._prefect_version = prefect.__version__
        self._cache: dict = {}

        super().__init__()

    def __eq__(self, other: 'Flow') -> bool:
        if type(self) == type(other):
            s = (self.name, self.version, self.tasks, self.edges)
            o = (other.name, other.version, other.tasks, other.edges)
            return s == o
        return False

    def __repr__(self) -> str:
        return '<{cls}: {self.name}{v}>'.format(
            cls=type(self).__name__,
            self=self,
            v=' version={}'.format(self.version) if self.version else '')

    def __iter__(self):
        yield from self.sorted_tasks()

    # Identification  ----------------------------------------------------------

    def copy(self) -> 'Flow':
        new = copy.copy(self)
        new.tasks = self.tasks.copy()
        new.edges = self.edges.copy()
        return new

    # Context Manager ----------------------------------------------------------

    def __enter__(self) -> 'Flow':
        self.__previous_flow = prefect.context.get('flow')
        prefect.context.update(flow=self)
        return self

    def __exit__(self, _type, _value, _tb) -> None:
        prefect.context.update(flow=self.__previous_flow)
        del self.__previous_flow

    # Introspection ------------------------------------------------------------

    @cache(validation_fn=flow_cache_key)
    def root_tasks(self) -> Set[Task]:
        """
        Returns the root tasks of the Flow -- tasks that have no upstream
        dependencies.
        """
        return set(t for t in self.tasks if not self.edges_to(t))

    @cache(validation_fn=flow_cache_key)
    def terminal_tasks(self) -> Set[Task]:
        """
        Returns the terminal tasks of the Flow -- tasks that have no downstream
        dependencies.
        """
        return set(t for t in self.tasks if not self.edges_from(t))

    def parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns details about any Parameters of this flow
        """
        return {
            t.name: {
                'required': t.required,
                'default': t.default
            }
            for t in self.tasks
            if isinstance(t, Parameter)
        }

    # Graph --------------------------------------------------------------------

    @contextmanager
    def restore_graph_on_error(self, validate: bool = True) -> None:
        """
        A context manager that saves the Flow's graph (tasks & edges) and
        restores it if an error is raised. It can be used to test potentially
        erroneous configurations (for example, ones that might include cycles)
        without modifying the graph.

        It will automatically check for cycles when restored.

        with flow.restore_graph_on_error():
            # this will raise an error, but the flow graph will not be modified
            add_cycle_to_graph(flow)
        """
        tasks, edges = self.tasks.copy(), self.edges.copy()
        try:
            yield
            if validate:
                self.validate()
        except Exception:
            self.tasks, self.edges = tasks, edges
            raise

    def add_task(self, task: Task) -> None:
        if not isinstance(task, Task):
            raise TypeError(
                'Tasks must be Task instances (received {})'.format(type(task)))
        elif task not in self.tasks:
            if isinstance(task, Parameter) and task.name in self.parameters():
                raise ValueError(
                    'This flow already has a parameter called "{}"'.format(
                        task.name))
            elif task.slug and task.slug in [t.slug for t in self.tasks]:
                raise ValueError(
                    'A task with the slug "{}" already exists in this '
                    'flow.'.format(task.slug))

        self.tasks.add(task)

    def add_edge(
            self,
            upstream_task: Task,
            downstream_task: Task,
            key: str = None,
            validate: bool = True) -> None:
        if isinstance(upstream_task, TaskResult):
            upstream_task = upstream_task.task
        if isinstance(downstream_task, TaskResult):
            downstream_task = downstream_task.task
        if isinstance(downstream_task, Parameter):
            raise ValueError('Parameters can not have upstream dependencies.')

        if key and key in {e.key for e in self.edges_to(downstream_task)}:
            raise ValueError(
                'Argument "{a}" for task {t} has already been assigned in '
                'this flow. If you are trying to call the task again with '
                'new arguments, call Task.copy() before adding the result '
                'to this flow.'.format(a=key, t=downstream_task))

        edge = Edge(
            upstream_task=upstream_task,
            downstream_task=downstream_task,
            key=key)

        with self.restore_graph_on_error(validate=validate):
            if upstream_task not in self.tasks:
                self.add_task(upstream_task)
            if downstream_task not in self.tasks:
                self.add_task(downstream_task)
            self.edges.add(edge)

            # check that the edges are valid keywords by binding them
            if key is not None:
                edge_keys = {
                    e.key: None
                    for e in self.edges_to(downstream_task)
                    if e.key is not None
                }
                inspect.signature(downstream_task.run).bind_partial(**edge_keys)

    def update(self, flow: 'Flow', validate: bool = True) -> None:
        with self.restore_graph_on_error(validate=validate):

            for task in flow.tasks:
                if task not in self.tasks:
                    self.add_task(task)

            for edge in flow.edges:
                if edge not in self.edges:
                    self.add_edge(
                        upstream_task=edge.upstream_task,
                        downstream_task=edge.downstream_task,
                        key=edge.key,
                        validate=False)

    def add_task_results(self, *task_results, validate: bool = True) -> None:
        with self.restore_graph_on_error(validate=validate):
            for t in task_results:
                self.add_task(t.task)
                self.update(t.flow, validate=False)

    @cache(validation_fn=flow_cache_key)
    def all_upstream_edges(self) -> Dict[Task, Set[Edge]]:
        edges = {t: set() for t in self.tasks}
        for edge in self.edges:
            edges[edge.downstream_task].add(edge)
        return edges

    @cache(validation_fn=flow_cache_key)
    def all_downstream_edges(self) -> Dict[Task, Set[Edge]]:
        edges: Dict[Task, Set[Edge]] = {t: set() for t in self.tasks}
        for edge in self.edges:
            edges[edge.upstream_task].add(edge)
        return edges

    def edges_to(self, task: Task) -> Set[Edge]:
        return self.all_upstream_edges()[task]

    def edges_from(self, task: Task) -> Set[Edge]:
        return self.all_downstream_edges()[task]

    def upstream_tasks(self, task: Task) -> Set[Task]:
        return set(e.upstream_task for e in self.edges_to(task))

    def downstream_tasks(self, task: Task) -> Set[Task]:
        s: Set[Task]
        s = set(e.downstream_task for e in self.edges_from(task))
        return s

    def validate(self) -> None:
        """
        Checks the flow for cycles and raises an error if one is found.
        """
        self.sorted_tasks()

    @cache(validation_fn=flow_cache_key)
    def sorted_tasks(self,
                     root_tasks: Iterable[Task] = None) -> Tuple[Task, ...]:

        # begin by getting all tasks under consideration (root tasks and all
        # downstream tasks)
        if root_tasks:
            tasks = set(root_tasks)
            seen: Set[Task] = set()
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
                raise ValueError('Flows must be acyclic!')

        return tuple(sorted_tasks)

    # Dependencies ------------------------------------------------------------

    def set_dependencies(
            self,
            task: Task,
            upstream_tasks: Iterable[Task] = None,
            downstream_tasks: Iterable[Task] = None,
            keyword_results: Mapping[str, Task] = None,
            validate: bool = True) -> TaskResult:
        """
        Convenience function for adding task dependencies on upstream tasks.

        Args:
            task (Task): a Task that will become part of the Flow

            upstream_tasks ([Task]): Tasks that will run before the task runs

            downstream_tasks ([Task]): Tasks that will run after the task runs

            keyword_results ({key: Task}): The results of these tasks
                will be provided to the task under the specified keyword
                arguments.
        """
        with self.restore_graph_on_error(validate=validate):

            result: TaskResult = as_task_result(task)
            task = result.task

            # validate the task
            if inspect.getfullargspec(task.run).varargs:
                raise ValueError(
                    'Tasks with variable positional arguments (*args) are not '
                    'supported, because all Prefect arguments are stored as '
                    'keywords. As a workaround, consider modifying the run() '
                    'method to accept **kwargs and feeding the values '
                    'to *args.')

            # update this flow with the result
            self.add_task_results(result)

            for t in upstream_tasks or []:
                t = as_task_result(t)
                self.add_task_results(t)
                self.add_edge(
                    upstream_task=t, downstream_task=task, validate=False)

            for t in downstream_tasks or []:
                t = as_task_result(t)
                self.add_task_results(t)
                self.add_edge(
                    upstream_task=task, downstream_task=t, validate=False)

            for key, t in (keyword_results or {}).items():
                t = as_task_result(t)
                self.add_task_results(t)
                self.add_edge(
                    upstream_task=t,
                    downstream_task=task,
                    key=key,
                    validate=False)

        return TaskResult(task=task, flow=self)

    # Execution  ---------------------------------------------------------------

    def run(
            self,
            parameters=None,
            executor=None,
            return_all_task_states=False,
            **kwargs):
        """
        Run the flow.
        """
        runner = prefect.engine.flow_runner.FlowRunner(
            flow=self, executor=executor)

        parameters = parameters or {}
        for p in self.parameters():
            if p in kwargs:
                parameters[p] = kwargs.pop(p)

        return runner.run(
            parameters=parameters,
            return_all_task_states=return_all_task_states,
            **kwargs)

    # Serialization ------------------------------------------------------------

    def serialize(self, seed=None) -> dict:
        ref_ids = self.fingerprint(seed=seed)

        return dict(
            ref_id=ref_ids['flow_id'],
            name=self.name,
            version=self.version,
            description=self.description,
            parameters=self.parameters(),
            schedule=self.schedule,
            tasks=[
                dict(
                    **t.serialize(),
                    ref_id=ref_ids['task_ids'][t],
                ) for t in self.tasks
            ],
            edges=[
                dict(
                    upstream_ref_id=ref_ids['task_ids'][e.upstream_task],
                    downstream_ref_id=ref_ids['task_ids'][e.downstream_task],
                    key=e.key) for e in self.edges
            ],
        )

    def fingerprint(self, seed=None):
        """
        Generates a unique fingerprint for the flow and each task it contains.
        """
        flow_id = prefect.utilities.ids.generate_flow_id(self, seed=seed)
        task_ids = prefect.utilities.ids.generate_task_ids(self, seed=seed)
        return dict(flow_id=flow_id, task_ids=task_ids)

    # Visualization ------------------------------------------------------------

    def visualize(self):
        graph = graphviz.Digraph()

        for t in self.tasks:
            graph.node(str(id(t)), t.name)

        for e in self.edges:
            graph.edge(
                str(id(e.upstream_task)), str(id(e.downstream_task)), e.key)

        with tempfile.NamedTemporaryFile() as tmp:
            graph.render(tmp.name, view=True)
