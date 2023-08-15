from typing import Any
import graphviz


class FlowVisualizationError(Exception):
    pass


class TaskRunTrackerState:
    current = None


def get_task_run_tracker():
    return TaskRunTrackerState.current


def track_task_run(task_name, parameters, mock_return=None):
    task_run_tracker = get_task_run_tracker()
    if task_run_tracker:
        upstream_tasks = []
        for k, v in parameters.items():
            if isinstance(v, TrackableTask):
                upstream_tasks.append(v)

        trackable_task = TrackableTask(
            name=task_name,
            upstream_tasks=upstream_tasks,
            value=mock_return,
        )
        task_run_tracker.add_trackable_task(trackable_task)
        return trackable_task


class TrackableTask:
    def __init__(
        self,
        name: str,
        upstream_tasks: list["TrackableTask"],
        value: Any = None,
    ):
        self.name = name
        self.upstream_tasks = upstream_tasks
        self.value = value

    def __iter__(self):
        if not self.value:
            raise ValueError(
                "Task needs a mock return value e.x. `@task(mock_return=[1, 2, 3])`."
            )
        else:
            try:
                iter(self.value)
            except TypeError:
                raise TypeError(
                    "Task needs an iterable mock return value e.x."
                    " `@task(mock_return=[1, 2, 3])`."
                )
            else:
                for value in self.value:
                    yield value


class TaskRunTracker:
    def __init__(self):
        self.tasks = []
        self.dynamic_task_counter = {}

    def add_trackable_task(self, task):
        if task.name not in self.dynamic_task_counter:
            self.dynamic_task_counter[task.name] = 0
        else:
            self.dynamic_task_counter[task.name] += 1

        task.name = f"{task.name}-{self.dynamic_task_counter[task.name]}"
        self.tasks.append(task)

    def __enter__(self):
        TaskRunTrackerState.current = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        TaskRunTrackerState.current = None


def visualize_task_dependencies(flow_run_name: str, task_run_tracker: TaskRunTracker):
    g = graphviz.Digraph()
    for task in task_run_tracker.tasks:
        g.node(task.name)
        for upstream in task.upstream_tasks:
            g.edge(upstream.name, task.name)
    g.render(filename=flow_run_name, view=True, format="png")
