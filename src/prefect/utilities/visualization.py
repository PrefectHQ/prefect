"""
Utilities for working with Flow.visualize()
"""

from collections.abc import Coroutine
from functools import partial
from typing import Any, Literal, Optional, Union, overload

import graphviz  # type: ignore  # no typing stubs available
from typing_extensions import Self

from prefect._internal.concurrency.api import from_async


class FlowVisualizationError(Exception):
    pass


class VisualizationUnsupportedError(Exception):
    pass


class TaskVizTrackerState:
    current: Optional["TaskVizTracker"] = None


class GraphvizImportError(Exception):
    pass


class GraphvizExecutableNotFoundError(Exception):
    pass


def get_task_viz_tracker() -> Optional["TaskVizTracker"]:
    return TaskVizTrackerState.current


@overload
def track_viz_task(
    is_async: Literal[True],
    task_name: str,
    parameters: dict[str, Any],
    viz_return_value: Optional[Any] = None,
) -> Coroutine[Any, Any, Any]: ...


@overload
def track_viz_task(
    is_async: Literal[False],
    task_name: str,
    parameters: dict[str, Any],
    viz_return_value: Optional[Any] = None,
) -> Any: ...


def track_viz_task(
    is_async: bool,
    task_name: str,
    parameters: dict[str, Any],
    viz_return_value: Optional[Any] = None,
) -> Union[Coroutine[Any, Any, Any], Any]:
    """Return a result if sync otherwise return a coroutine that returns the result"""
    if is_async:
        return from_async.wait_for_call_in_loop_thread(
            partial(_track_viz_task, task_name, parameters, viz_return_value)
        )
    else:
        return _track_viz_task(task_name, parameters, viz_return_value)


def _track_viz_task(
    task_name: str,
    parameters: dict[str, Any],
    viz_return_value: Optional[Any] = None,
) -> Any:
    task_run_tracker = get_task_viz_tracker()
    if task_run_tracker:
        upstream_tasks: list[VizTask] = []
        for _, v in parameters.items():
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
        upstream_tasks: Optional[list["VizTask"]] = None,
    ):
        self.name = name
        self.upstream_tasks: list[VizTask] = upstream_tasks if upstream_tasks else []


class TaskVizTracker:
    def __init__(self):
        self.tasks: list[VizTask] = []
        self.dynamic_task_counter: dict[str, int] = {}
        self.object_id_to_task: dict[int, VizTask] = {}

    def add_task(self, task: VizTask) -> None:
        if task.name not in self.dynamic_task_counter:
            self.dynamic_task_counter[task.name] = 0
        else:
            self.dynamic_task_counter[task.name] += 1

        task.name = f"{task.name}-{self.dynamic_task_counter[task.name]}"
        self.tasks.append(task)

    def __enter__(self) -> Self:
        TaskVizTrackerState.current = self
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        TaskVizTrackerState.current = None

    def link_viz_return_value_to_viz_task(
        self, viz_return_value: Any, viz_task: VizTask
    ) -> None:
        """
        We cannot track booleans, Ellipsis, None, NotImplemented, or the integers from -5 to 256
        because they are singletons.
        """
        from prefect.utilities.engine import UNTRACKABLE_TYPES

        if (type(viz_return_value) in UNTRACKABLE_TYPES) or (
            isinstance(viz_return_value, int) and (-5 <= viz_return_value <= 256)
        ):
            return
        self.object_id_to_task[id(viz_return_value)] = viz_task


def build_task_dependencies(task_run_tracker: TaskVizTracker) -> graphviz.Digraph:
    """
    Constructs a Graphviz directed graph object that represents the dependencies
    between tasks in the given TaskVizTracker.

    Parameters:
    - task_run_tracker (TaskVizTracker): An object containing tasks and their
      dependencies.

    Returns:
    - graphviz.Digraph: A directed graph object depicting the relationships and
      dependencies between tasks.

    Raises:
    - GraphvizImportError: If there's an ImportError related to graphviz.
    - FlowVisualizationError: If there's any other error during the visualization
      process or if return values of tasks are directly accessed without
      specifying a `viz_return_value`.
    """
    try:
        g = graphviz.Digraph()
        for task in task_run_tracker.tasks:
            g.node(task.name)  # type: ignore[reportUnknownMemberType]
            for upstream in task.upstream_tasks:
                g.edge(upstream.name, task.name)  # type: ignore[reportUnknownMemberType]
        return g
    except ImportError as exc:
        raise GraphvizImportError from exc
    except Exception:
        raise FlowVisualizationError(
            "Something went wrong building the flow's visualization."
            " If you're interacting with the return value of a task"
            " directly inside of your flow, you must set a set a `viz_return_value`"
            ", for example `@task(viz_return_value=[1, 2, 3])`."
        )


def visualize_task_dependencies(graph: graphviz.Digraph, flow_run_name: str) -> None:
    """
    Renders and displays a Graphviz directed graph representing task dependencies.

    The graph is rendered in PNG format and saved with the name specified by
    flow_run_name. After rendering, the visualization is opened and displayed.

    Parameters:
    - graph (graphviz.Digraph): The directed graph object to visualize.
    - flow_run_name (str): The name to use when saving the rendered graph image.

    Raises:
    - GraphvizExecutableNotFoundError: If Graphviz isn't found on the system.
    - FlowVisualizationError: If there's any other error during the visualization
      process or if return values of tasks are directly accessed without
      specifying a `viz_return_value`.
    """
    try:
        graph.render(filename=flow_run_name, view=True, format="png", cleanup=True)  # type: ignore[reportUnknownMemberType]
    except graphviz.backend.ExecutableNotFound as exc:
        msg = (
            "It appears you do not have Graphviz installed, or it is not on your "
            "PATH. Please install Graphviz from http://www.graphviz.org/download/. "
            "Note: Just installing the `graphviz` python package is not "
            "sufficient."
        )
        raise GraphvizExecutableNotFoundError(msg) from exc
    except Exception:
        raise FlowVisualizationError(
            "Something went wrong building the flow's visualization."
            " If you're interacting with the return value of a task"
            " directly inside of your flow, you must set a set a `viz_return_value`"
            ", for example `@task(viz_return_value=[1, 2, 3])`."
        )
