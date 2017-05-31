import base64
import copy
import hashlib
import prefect
from prefect.task import Task, TaskResult
from prefect.signals import PrefectError
import prefect.context
from prefect.schedules import NoSchedule
from prefect.utilities.strings import is_valid_identifier
import ujson


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
            upstream_task (str): the name of a task that must run before the
                downstream_task

            downstream_task (str): the name of a task that will be run after the
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
        if isinstance(upstream_task, Task):
            upstream_task = upstream_task.name
        if isinstance(downstream_task, Task):
            downstream_task = downstream_task.name
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

        try:
            ujson.loads(ujson.dumps(upstream_index))
            self.upstream_index = upstream_index
        except TypeError:
            raise ValueError('upstream_index must be JSON-encodable')

    def serialize(self):
        """
        Returns a serialized version of the edge
        """
        return {
            'upstream_task': self.upstream_task,
            'downstream_task': self.downstream_task,
            'key': self.key,
            'upstream_index': self.upstream_index
        }

    @classmethod
    def deserialize(cls, serialized):
        serialized = serialized.copy()
        if serialized['upstream_index'] is not None:
            serialized['upstream_index'] = ujson.loads(
                serialized['upstream_index'])
        return cls(**serialized)



class Flow:

    def __init__(
            self,
            name,
            namespace=prefect.config.get('flows', 'default_namespace'),
            version=prefect.config.get('flows', 'default_version'),
            required_params=None,
            schedule=NoSchedule(),
            concurrent_runs=None,  #TODO
            cluster=None):
        """
        Args:
            required_params: a collection of parameter names that must be
                provided when the Flow is run. Flows can be called with any
                params, but an error will be raised if these are missing.
            schedule (prefect.Schedule): a Schedule object that returns the
                Flow's schedule
            cluster (str): The address of a specific cluster that this Flow
                should run in. If not provided, the default cluster will be
                used.

        """

        if required_params is None:
            required_params = set()
        elif isinstance(required_params, str):
            required_params = set([required_params])
        else:
            required_params = set(required_params)

        self.name = name
        self.namespace = namespace
        self.version = version
        #
        # h = hashlib.sha1(f'{self.namespace}{self.name}{self.version}'.encode())
        # self.id = base64.b32encode(h.digest()).decode()

        self.required_params = required_params
        self.schedule = schedule
        self.tasks = dict()
        self.edges = set()
        self.concurrent_runs = concurrent_runs
        self.cluster = cluster
        self._terminal_tasks = set()

        self._cache = {}
        self.check_cache()

    def __repr__(self):
        flow_type = type(self).__name__
        return f'{flow_type}({self.namespace}.{self.name}:{self.version})'

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.namespace == other.namespace
            and self.name == other.name
            and self.version == other.version
            and self.tasks == other.tasks
            and self.edges == other.edges)

    def __hash__(self):
        return id(self)

    def __json__(self):
        return self.serialize()

    def check_cache(self):
        """
        Check if the cache is still valid by comparing it to the flow,
        and reset it if it isn't.
        """
        if (
                self._cache.get('tasks', None) != self.tasks
                or self._cache.get('edges', None) != self.edges):
            self._cache = {'tasks': dict(self.tasks), 'edges': set(self.edges)}

    # Graph -------------------------------------------------------------------

    def __iter__(self):
        yield from self.sorted_tasks()

    def get_task(self, name):
        """
        Retrieve a task by name
        """
        if name in self.tasks:
            return self.tasks[name]
        else:
            raise ValueError(
                'Task {} was not found in the Flow'.format(name))

    def add_task(self, task):
        if not isinstance(task, Task):
            raise TypeError(
                f'Expected a Task; received {type(task).__name__}')
        if task.name in self.tasks:
            raise ValueError(
                f'A task named "{task.name}" already exists in this Flow.')
        self.tasks[task.name] = task

    def add_edge(self, upstream_task, downstream_task, key=None, upstream_index=None):
        """
        Adds an Edge to the Flow. Edges create dependencies between tasks.
        The simplest edge simply enforcces an ordering so that the upstream
        task runs before the downstream task, but edges can introduce more
        complex behaviors as well.
        """

        if isinstance(upstream_task, TaskResult):
            upstream_task = upstream_task.task
            upstream_index = upstream_task.index

        edge = Edge(
            upstream_task=upstream_task.name,
            downstream_task=downstream_task.name,
            upstream_index=upstream_index,
            key=key,
        )

        if upstream_task.name not in self.tasks:
            self.add_task(upstream_task)
        if downstream_task.name not in self.tasks:
            self.add_task(downstream_task)

        if edge.key is not None:
            existing_edges = [
                e for e in self.edges
                if e.downstream_task == downstream_task.name
                and e.key == edge.key
            ]
            if existing_edges:
                raise ValueError(
                    f'An edge to task {edge.downstream_task} with '
                    f'key "{edge.key}" already exists!')

        self.edges.add(edge)

        # check that the edge doesn't add a cycle
        self.sorted_tasks()

    def set_up_task(self, task, upstream_tasks, **results):
        """
        Convenience function for adding task relationships.

        Args:
            task (Task): a Task that will become part of the Flow

            upstream_tasks ([Task]): Tasks that will run before the task runs

            results ({key: Task or TaskResult}): Tasks that will run
                before the task runs and pass their output to the task under
                the key
        """
        if task.name not in self.tasks:
            self.add_task(task)

        for t in upstream_tasks:
            self.add_edge(upstream_task=t, downstream_task=task)

        for key, t in results.items():
            self.add_edge(upstream_task=t, downstream_task=task, key=key)

    def upstream_tasks(self, task):
        """
        Set of all tasks immediately upstream from a task.

        Args:
            task (Task): tasks upstream from this task will be returned.
        """
        if isinstance(task, str):
            name = task
        else:
            name = task.name
        return set(
            e.upstream_task for e in self.edges if e.downstream_task == task)

    def downstream_tasks(self, task):
        """
        Set of all tasks immediately downstream from a task.

        Args:
            task (Task): tasks downstream from this task will be returned.
        """
        if isinstance(task, str):
            name = task
        else:
            name = task.name

        return set(
            e.downstream_task for e in self.edges if e.upstream_task == task)

    def sorted_tasks(self):
        """
        Returns a topological sort of this Flow's tasks.

        The result will be cached when possible.
        """

        self.check_cache()
        if 'sorted tasks' not in self._cache:
            tasks = set(self.tasks.values())
            sorted_tasks = []
            while tasks:
                acyclic = False
                for task in list(tasks):
                    for upstream_task in self.upstream_tasks(task):
                        if upstream_task in tasks:
                            # the previous task hasn't been sorted yet, so
                            # this task can't be sorted either
                            break
                    else:
                        # all previous tasks are sorted, so this one can be
                        # sorted as well
                        acyclic = True
                        tasks.remove(task)
                        sorted_tasks.append(task)
                if not acyclic:
                    # no tasks matched
                    raise ValueError('Flows must be acyclic!')
            self._cache['sorted tasks'] = tuple(sorted_tasks)

        return self._cache['sorted tasks']

    def edges_to(self, task):
        """
        Set of all Edges leading to this Task

        Args:
            task (Task or str)
        """
        if isinstance(task, str):
            name = task
        else:
            name = task.name
        return set(e for e in self.edges if e.downstream_task == name)

    def edges_from(self, task):
        """
        Set of all Edges leading from this Task

        Args:
            task (Task or str)
        """
        if isinstance(task, str):
            name = task
        else:
            name = task.name
        return set(e for e in self.edges if e.upstream_task == name)

    def root_tasks(self):
        """
        Returns the root tasks of the Flow -- tasks that have no upstream
        dependencies.
        """
        self.check_cache()
        if 'root tasks' not in self._cache:
            root_tasks = set()
            for task in self.tasks.values():
                if not self.edges_to(task):
                    root_tasks.add(task)
            self._cache['root tasks'] = root_tasks

        return self._cache['root tasks']

    def terminal_tasks(self):
        """
        Returns the terminal tasks of the Flow -- tasks that have no downstream
        dependencies.

        Terminal task states are used to determine the state of a Flow.
        To override the default, call set_terminal_tasks()
        """
        if self._terminal_tasks:
            return self._terminal_tasks

        self.check_cache()
        if 'terminal tasks' not in self._cache:
            terminal_tasks = set()
            for task in self.tasks.values():
                if not self.edges_from(task):
                    terminal_tasks.add(task)
            self._cache['terminal tasks'] = terminal_tasks

        return self._cache['terminal tasks']

    def set_terminal_tasks(self, tasks):
        """
        Override the default terminal tasks. The state of these tasks is used
        to determine the state of the Flow.
        """
        if set(tasks).difference(self.tasks.values()):
            raise ValueError('Terminal tasks must be part of the Flow')
        self._terminal_tasks = set(tasks)

    # Context Manager -----------------------------------------------

    def __enter__(self):
        self._previous_context = prefect.context.to_dict()
        prefect.context.update(flow=self)
        return self

    def __exit__(self, _type, _value, _tb):
        prefect.context.reset(**self._previous_context)
        del self._previous_context

    # Persistence  ------------------------------------------------

    def serialize(self):
        flow = copy.copy(self)
        del flow.schedule
        del flow.tasks
        del flow.edges

        return {
            'namespace': self.namespace,
            'name': self.name,
            'version': self.version,
            'tasks': [t.serialize() for t in self.sorted_tasks()],
            'edges': [e.serialize() for e in self.edges],
            'required_params': sorted(str(p) for p in self.required_params),
            'schedule': self.schedule.serialize(),
            'serialized': prefect.utilities.serialize.serialize(flow),
            'executor_args': {
                'cluster': self.cluster,
                },
        }

    @classmethod
    def deserialize(cls, serialized):
        obj = prefect.utilities.serialize.deserialize(serialized['serialized'])
        if not isinstance(obj, cls):
            raise TypeError(
                'Expected {}; received {}'.format(
                    cls.__name__, type(obj).__name__))
        for task in serialized['tasks']:
            obj.add_task(Task.deserialize(task))
        obj.edges = set([Edge.deserialize(e) for e in serialized['edges']])
        obj.schedule = prefect.schedules.Schedule.deserialize(
            serialized['schedule'])
        obj._cache.clear()
        return obj
