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
            # if it's an object that we've already seen,
            # we can use the object id to find if there is a trackable task
            # if so, add it to the upstream tasks
            elif id(v) in task_run_tracker.object_id_to_task:
                upstream_tasks.append(task_run_tracker.object_id_to_task[id(v)])

        trackable_task = TrackableTask(
            name=task_name,
            upstream_tasks=upstream_tasks,
        )
        task_run_tracker.add_trackable_task(trackable_task)

        if mock_return:
            task_run_tracker.link_mock_return_to_trackable_task(
                mock_return, trackable_task
            )
            return mock_return

        return trackable_task


class TrackableTask:
    def __init__(
        self,
        name: str,
        upstream_tasks: list["TrackableTask"],
        mapped_length: int = None,
    ):
        self.name = name
        self.upstream_tasks = upstream_tasks

    # def result(self):
    #     return self


class TaskRunTracker:
    def __init__(self):
        self.tasks = []
        self.dynamic_task_counter = {}
        self.object_id_to_task = {}

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

    def link_mock_return_to_trackable_task(
        self, mock_return: Any, trackable_task: TrackableTask
    ) -> None:
        from prefect.utilities.collections import visit_collection
        from prefect.engine import UNTRACKABLE_TYPES

        def link_if_trackable(obj: Any) -> None:
            """
            We cannot track booleans, Ellipsis, None, NotImplemented, or the integers from -5 to 256
            because they are singletons.
            """
            if (type(obj) in UNTRACKABLE_TYPES) or (
                isinstance(obj, int) and (-5 <= obj <= 256)
            ):
                return
            self.object_id_to_task[id(obj)] = trackable_task

        visit_collection(expr=mock_return, visit_fn=link_if_trackable, max_depth=1)


def visualize_task_dependencies(flow_run_name: str, task_run_tracker: TaskRunTracker):
    g = graphviz.Digraph()
    for task in task_run_tracker.tasks:
        g.node(task.name)
        for upstream in task.upstream_tasks:
            g.edge(upstream.name, task.name)
    g.render(filename=flow_run_name, view=True, format="png")
