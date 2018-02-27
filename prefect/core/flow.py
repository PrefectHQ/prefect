import inspect
from typing import Iterable, Mapping
from contextlib import contextmanager
from slugify import slugify

import prefect
import prefect.context
from prefect.flows.schedules import NoSchedule
from prefect.core.base import PrefectObject
from prefect.core.task import Task
from prefect.core.edge import Edge
from prefect.core.parameter import Parameter


class Flow(PrefectObject):

    def __init__(
            self,
            name='Flow',
            id=None,
            version=None,
            schedule=None,
            description=None,
            tasks=None,
            edges=None):

        self.name = name
        self.version = version
        self.description = description
        self.schedule = schedule or NoSchedule()

        self.tasks = set()
        self.edges = set()

        for t in tasks or []:
            self.add_task(t)

        for e in edges or []:
            self.add_edge(
                upstream_task=e.upstream_task,
                downstream_task=e.downstream_task,
                key=e.key)

        super().__init__(id=id)

    def __eq__(self, other):
        if type(self) == type(other):
            s = (self.name, self.version, self.tasks, self.edges)
            o = (other.name, other.version, other.tasks, other.edges)
            return s == o
        return False

    def __repr__(self):
        base = self.name
        if self.version:
            base += ':{self.version}'.format(self=self)
        return '{type}("{base}")'.format(type=type(self).__name__, base=base)

    # Context Manager ----------------------------------------------------------

    def __enter__(self):
        self.__previous_context = prefect.context.Context.as_dict()
        prefect.context.Context.update(flow=self)
        return self

    def __exit__(self, _type, _value, _tb):
        prefect.context.Context.reset(self.__previous_context)
        del self.__previous_context

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

    def __iter__(self):
        yield from self.sorted_tasks()

    def add_task(self, task):
        if not isinstance(task, Task):
            raise TypeError(
                'Tasks must be Task instances (received {})'.format(type(task)))

        elif task in self.tasks:
            raise ValueError('Task is already in the flow.')

        elif task not in self.tasks and task.id:
            if next((t for t in self.tasks if t.id == task.id), None):
                raise ValueError(
                    'A different task with the same ID ("{}") already exists '
                    'in the Flow.'.format(task.id))

        elif isinstance(task, Parameter):
            if task.name in self.parameters():
                raise ValueError(
                    'This Flow already has a parameter called "{}"'.format(
                        task.name))

        self.tasks.add(task)

    def add_edge(self, upstream_task, downstream_task, key=None):

        edges_to_task = self.edges_to(downstream_task)
        if key and key in {e.key for e in edges_to_task}:
            raise ValueError(
                'The argument "{a}" for task {t} has already been '
                'assigned.'.format(a=key, t=downstream_task))

        edge = Edge(
            upstream_task=upstream_task,
            downstream_task=downstream_task,
            key=key)

        with self.restore_graph_on_error():
            if upstream_task not in self.tasks:
                self.add_task(upstream_task)
            if downstream_task not in self.tasks:
                self.add_task(downstream_task)
            self.edges.add(edge)

            # check that the edges are valid keywords by binding them
            edge_keys = {e.key: 0 for e in edges_to_task if e.key is not None}
            inspect.signature(downstream_task.run).bind_partial(**edge_keys)

            # check for cycles
            self.sorted_tasks()

    # Dependencies ------------------------------------------------------------

    @contextmanager
    def restore_graph_on_error(self):
        """
        A context manager that saves the Flow's graph (tasks & edges) and
        restores it if an error is raised. It can be used to test potentially
        erroneous configurations (for example, ones that might include cycles)
        without modifying the graph.

        with flow.restore_graph_on_error():
            # this will raise an error, but the flow graph will not be modified
            add_cycle_to_graph(flow)
        """
        tasks, edges = self.tasks.copy(), self.edges.copy()
        try:
            yield
        except Exception:
            self.tasks, self.edges = tasks, edges
            raise

    def set_dependencies(
            self,
            task: Task,
            upstream_tasks: Iterable[Task] = None,
            downstream_tasks: Iterable[Task] = None,
            upstream_results: Mapping[str, Task] = None):
        """
        Convenience function for adding task dependencies on upstream tasks.

        Args:
            task (Task): a Task that will become part of the Flow

            upstream_tasks ([Task]): Tasks that will run before the task runs

            downstream_tasks ([Task]): Tasks that will run after the task runs

            upstream_results ({key: Task}): The results of these tasks
                will be provided to the task under the specified keyword
                arguments.
        """
        with self.restore_graph_on_error():

            # add the task to the graph
            if task not in self.tasks:
                self.add_task(task)

            for t in upstream_tasks or []:
                if isinstance(t, prefect.core.task_result.TaskResult):
                    self.merge(t.flow)
                    t = t.task
                self.add_edge(upstream_task=t, downstream_task=task)

            for t in downstream_tasks or []:
                if isinstance(t, prefect.core.task_result.TaskResult):
                    self.merge(t.flow)
                    t = t.task
                self.add_edge(upstream_task=task, downstream_task=t)

            for key, t in (upstream_results or {}).items():
                if isinstance(t, prefect.core.task_result.TaskResult):
                    self.merge(t.flow)
                    t = t.task
                t = prefect.utilities.tasks.as_task(t)
                self.add_edge(upstream_task=t, downstream_task=task, key=key)

    def edges_to(self, task):
        return set(e for e in self.edges if e.downstream_task == task)

    def edges_from(self, task):
        return set(e for e in self.edges if e.upstream_task == task)

    def upstream_tasks(self, task):
        return set(e.upstream_task for e in self.edges_to(task))

    def downstream_tasks(self, task):
        return set(e.downstream_task for e in self.edges_from(task))

    def merge(self, flow):
        with self.restore_graph_on_error():

            if flow.id != self.id:
                raise ValueError('Flow ids do not match.')

            for task in flow.tasks:
                if task not in self.tasks:
                    self.add_task(task)

            for edge in flow.edges:
                if edge not in self.edges:
                    self.add_edge(
                        upstream_task=edge.upstream_task,
                        downstream_task=edge.downstream_task,
                        key=edge.key)

    def sorted_tasks(self, root_tasks=None):

        # begin by getting all tasks under consideration (root tasks and all
        # downstream tasks)

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
        remaining_tasks = tasks.copy()
        sorted_tasks = []
        while remaining_tasks:
            # mark the flow as cyclic unless we prove otherwise
            cyclic = True

            # iterate over each remaining task
            for task in sorted(remaining_tasks, key=lambda t: (t.name, t.id)):
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

    # Execution  ---------------------------------------------------------------

    # def run(
    #         self,
    #         parameters=None,
    #         executor=None,
    #         return_all_task_states=False,
    #         **kwargs):
    #     """
    #     Run the flow.
    #     """
    #     runner = prefect.engine.flow_runner.FlowRunner(
    #         flow=self, executor=executor)

    #     parameters = parameters or {}
    #     for p in self.parameters():
    #         if p in kwargs:
    #             parameters[p] = kwargs.pop(p)

    #     return runner.run(
    #         parameters=parameters,
    #         return_all_task_states=return_all_task_states,
    #         **kwargs)

    # Serialization ------------------------------------------------------------

    def serialize(self):
        serialized = super().serialize()
        serialized.update(
            name=self.name,
            id=self.id,
            version=self.version,
            description=self.description,
            parameters=self.parameters(),
            schedule=self.schedule,
            tasks=self.tasks,
            edges=self.edges)
        return serialized

    def after_deserialize(self, serialized):
        super().after_deserialize(serialized)
        self.tasks = serialized['tasks']
        self.edges = serialized['edges']
