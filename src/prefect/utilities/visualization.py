from typing import Any
import graphviz


class TaskRunTrackerState:
    current = None


def get_task_run_tracker():
    return TaskRunTrackerState.current


def track_task_run(task_name, parameters, mock_return_val=None):
    task_run_tracker = get_task_run_tracker()
    if task_run_tracker:
        upstream_tasks = []
        for k, v in parameters.items():
            if isinstance(v, TrackableTask):
                upstream_tasks.append(v)

        trackable_task = TrackableTask(
            name=task_name,
            upstream_tasks=upstream_tasks,
            value=mock_return_val,
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
        # TODO: show example of how to add to task decorator
        if not self.value:
            raise ValueError("Task needs a mock return value.")
        else:
            try:
                iter(self.value)
            except TypeError:
                raise TypeError("Task needs an iterable mock return value.")
            else:
                for value in self.value:
                    yield value


class TaskRunTracker:
    def __init__(self):
        self.tasks = []
        self.dynamic_task_counter = {}

    def add_trackable_task(self, task):
        # dynamic tracking for multiple task calls with the same name?

        # TODO use task key? not name?
        if task.name not in self.dynamic_task_counter:
            self.dynamic_task_counter[task.name] = 0
            self.tasks.append(task)
        else:
            self.dynamic_task_counter[task.name] += 1

        task.name = f"{task.name}-{self.dynamic_task_counter[task.name]}"
        self.tasks.append(task)

    def __enter__(self):
        TaskRunTrackerState.current = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        TaskRunTrackerState.current = None

    def visualize(self):
        g = graphviz.Digraph()
        for task in self.tasks:
            g.node(task.name)
            for upstream in task.upstream_tasks:
                g.edge(upstream.name, task.name)
        g.render(filename="my_flow", view=True, format="png")
