import inspect
import tempfile
from contextlib import contextmanager
from typing import Iterable, Mapping

import graphviz

import prefect
import prefect.context
from prefect.task import Parameter, Task
from prefect.utilities.json import Serializable
from prefect.utilities.strings import is_valid_identifier
from prefect.utilities.tasks import as_task_result
from prefect.utilities.functions import cache


def flow_cache_validation(flow):
    return hash((frozenset(flow.tasks), frozenset(flow.edges)))


class TaskResult:
    """
    TaskResults represent the execution of a specific task in a given flow.
    """

    def __init__(self, task, flow=None):
        if flow is None:
            flow = Flow()
        flow.add_task(task)
        self.task = task
        self.flow = flow

    def __getitem__(self, index):
        name = '{}[{}]'.format(self.task.name, index)
        index_task = prefect.tasks.core.operators.GetIndexTask(
            index=index, name=name)
        return index_task(task_result=self)

    def set_dependencies(
            self, upstream_tasks=None, downstream_tasks=None,
            keyword_results=None):

        self.flow.set_dependencies(
            task=self,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            keyword_results=keyword_results)

    def wait_for(self, task_results):
        self.set_dependencies(upstream_tasks=task_results)


class Edge:

    def __init__(self, upstream_task, downstream_task, key=None):
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

    def __repr__(self):
        return '<{cls}: {u} to {d}{k}>'.format(
            cls=type(self).__name__,
            u=self.upstream_task,
            d=self.downstream_task,
            k=' (key={})'.format(self.key) if self.key else '')

    def __eq__(self, other):
        if type(self) == type(other):
            self_cmp = (self.upstream_task, self.downstream_task, self.key)
            other_cmp = (other.upstream_task, other.downstream_task, other.key)
            return self_cmp == other_cmp
        return False

    def __hash__(self):
        return id(self)


class Flow(Serializable):

    def __init__(
            self,
            name=None,
            version=None,
            schedule=None,
            description=None,
            tasks=None,
            edges=None):

        self.name = name or type(self).__name__
        self.version = version
        self.description = description
        self.schedule = schedule or prefect.schedules.NoSchedule()

        self.tasks = set()
        self.edges = set()

        for t in tasks or []:
            self.add_task(t)

        for e in edges or []:
            self.add_edge(
                upstream_task=e.upstream_task,
                downstream_task=e.downstream_task,
                key=e.key)

        self._prefect_version = prefect.__version__
        self._cache = {}

        super().__init__()

    def __eq__(self, other):
        if type(self) == type(other):
            s = (self.name, self.version, self.tasks, self.edges)
            o = (other.name, other.version, other.tasks, other.edges)
            return s == o
        return False

    def __repr__(self):
        return '<{cls}: {self.name}{v}>'.format(
            cls=type(self).__name__,
            self=self,
            v=' version={}'.format(self.version) if self.version else '')

    def __iter__(self):
        yield from self.sorted_tasks()

    # Identification  ----------------------------------------------------------

    def copy(self):
        new = super().copy()
        new.tasks = self.tasks.copy()
        new.edges = self.edges.copy()
        return new

    # Context Manager ----------------------------------------------------------

    def __enter__(self):
        self.__previous_flow = prefect.context.get('flow')
        prefect.context.Context.update(flow=self)
        return self

    def __exit__(self, _type, _value, _tb):
        prefect.context.Context.reset(self.__previous_flow)
        del self.__previous_flow

    # Introspection ------------------------------------------------------------

    def root_tasks(self):
        """
        Returns the root tasks of the Flow -- tasks that have no upstream
        dependencies.
        """
        return set(t for t in self.tasks if not self.edges_to(t))

    def terminal_tasks(self):
        """
        Returns the terminal tasks of the Flow -- tasks that have no downstream
        dependencies.
        """
        return set(t for t in self.tasks if not self.edges_from(t))

    def parameters(self):
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
    def restore_graph_on_error(self, validate=True):
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

    def add_task(self, task):
        if not isinstance(task, Task):
            raise TypeError(
                'Tasks must be Task instances (received {})'.format(type(task)))

        elif task not in self.tasks:
            if isinstance(task, Parameter) and task.name in self.parameters():
                raise ValueError(
                    'This Flow already has a parameter called "{}"'.format(
                        task.name))

        self.tasks.add(task)

    def add_edge(self, upstream_task, downstream_task, key=None, validate=True):
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
                    e.key: _
                    for e in self.edges_to(downstream_task)
                    if e.key is not None
                }
                inspect.signature(downstream_task.run).bind_partial(**edge_keys)

    def update(self, flow, validate=True):
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

    def add_task_results(self, *task_results, validate=True):
        with self.restore_graph_on_error(validate=validate):
            for t in task_results:
                self.add_task(t.task)
                self.update(t.flow, validate=False)

    @cache(flow_cache_validation)
    def all_upstream_edges(self):
        edges = {t: set() for t in self.tasks}
        for edge in self.edges:
            edges[edge.downstream_task].add(edge)
        return edges

    @cache(flow_cache_validation)
    def all_downstream_edges(self):
        edges = {t: set() for t in self.tasks}
        for edge in self.edges:
            edges[edge.upstream_task].add(edge)
        return edges

    def edges_to(self, task):
        return self.all_upstream_edges()[task]

    def edges_from(self, task):
        return self.all_downstream_edges()[task]

    def upstream_tasks(self, task):
        return set(e.upstream_task for e in self.edges_to(task))

    def downstream_tasks(self, task):
        return set(e.downstream_task for e in self.edges_from(task))

    def validate(self):
        """
        Checks the flow for cycles and raises an error if one is found.
        """
        self.sorted_tasks()

    @cache(flow_cache_validation)
    def sorted_tasks(self, root_tasks=None):

        # begin by getting all tasks under consideration (root tasks and all
        # downstream tasks)
        # import ipdb; ipdb.set_trace()
        if root_tasks:
            tasks = set(root_tasks)
            seen = set()
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
            validate=True):
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

            result = as_task_result(task)
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

    def serialize(self):
        return dict(
            name=self.name,
            version=self.version,
            description=self.description,
            parameters=self.parameters(),
            schedule=self.schedule,
            tasks=[t.serialize() for t in self.sorted_tasks()],
            edges=[e.serialize() for e in self.edges],
        )

    @classmethod
    def deserialize(cls, serialized):
        return Flow(
            name=serialized['name'],
            version=serialized['version'],
            schedule=serialized['schedule'],
            tasks=set(Task.deserialize(t) for t in serialized['tasks']),
            edges=set(Edge.deserialize(e) for e in serialized['edges']))

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
