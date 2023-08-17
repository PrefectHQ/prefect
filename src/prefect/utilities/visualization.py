from functools import partial
from typing import Any, List, Optional

import graphviz

from prefect._internal.concurrency.api import from_async


class FlowVisualizationError(Exception):
    pass


class VisualizationUnsupportedError(Exception):
    pass


class TaskVizTrackerState:
    current = None


class GraphvizExecutableNotFoundError(Exception):
    pass


def get_task_viz_tracker():
    return TaskVizTrackerState.current


def track_viz_task(
    is_async: bool,
    task_name: str,
    parameters: dict,
    viz_return_value: Optional[Any] = None,
):
    """Return a result if sync otherwise return a coroutine that returns the result"""
    if is_async:
        return from_async.wait_for_call_in_loop_thread(
            partial(_track_viz_task, task_name, parameters, viz_return_value)
        )
    else:
        return _track_viz_task(task_name, parameters, viz_return_value)


def _track_viz_task(
    task_name,
    parameters,
    viz_return_value=None,
) -> Any:
    task_run_tracker = get_task_viz_tracker()
    if task_run_tracker:
        upstream_tasks = []
        for k, v in parameters.items():
            if isinstance(v, VizTask):
                upstream_tasks.append(v)
            # if it's an object that we've already seen,
            # we can use the object id to find if there is a trackable task
            # if so, add it to the upstream tasks
            elif id(v) in task_run_tracker.object_id_to_task:
                upstream_tasks.append(task_run_tracker.object_id_to_task[id(v)])

        viz_task = VizTask(
            name=task_name,
            upstream_tasks=upstream_tasks,
        )
        task_run_tracker.add_task(viz_task)

        if viz_return_value:
            task_run_tracker.link_viz_return_value_to_viz_task(
                viz_return_value, viz_task
            )
            return viz_return_value

        return viz_task


class VizTask:
    def __init__(
        self,
        name: str,
        upstream_tasks: Optional[List["VizTask"]] = None,
    ):
        self.name = name
        self.upstream_tasks = upstream_tasks if upstream_tasks else []


class TaskVizTracker:
    def __init__(self):
        self.tasks = []
        self.dynamic_task_counter = {}
        self.object_id_to_task = {}

    def add_task(self, task: VizTask):
        if task.name not in self.dynamic_task_counter:
            self.dynamic_task_counter[task.name] = 0
        else:
            self.dynamic_task_counter[task.name] += 1

        task.name = f"{task.name}-{self.dynamic_task_counter[task.name]}"
        self.tasks.append(task)

    def __enter__(self):
        TaskVizTrackerState.current = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        TaskVizTrackerState.current = None

    def link_viz_return_value_to_viz_task(
        self, viz_return_value: Any, viz_task: VizTask
    ) -> None:
        """
        We cannot track booleans, Ellipsis, None, NotImplemented, or the integers from -5 to 256
        because they are singletons.
        """
        from prefect.engine import UNTRACKABLE_TYPES

        if (type(viz_return_value) in UNTRACKABLE_TYPES) or (
            isinstance(viz_return_value, int) and (-5 <= viz_return_value <= 256)
        ):
            return
        self.object_id_to_task[id(viz_return_value)] = viz_task


def build_task_dependencies(task_run_tracker: TaskVizTracker):
    g = graphviz.Digraph()
    for task in task_run_tracker.tasks:
        g.node(task.name)
        for upstream in task.upstream_tasks:
            g.edge(upstream.name, task.name)
    return g


def visualize_task_dependencies(graph: graphviz.Digraph, flow_run_name: str):
    try:
        graph.render(filename=flow_run_name, view=True, format="png", cleanup=True)
    except graphviz.backend.ExecutableNotFound as exc:
        msg = (
            "It appears you do not have Graphviz installed, or it is not on your "
            "PATH. Please install Graphviz from http://www.graphviz.org/download/. "
            "Note: Just installing the `graphviz` python package is not "
            "sufficient."
        )
        raise GraphvizExecutableNotFoundError(msg) from exc
