import keyword
from typing import Set, Any

import prefect
from prefect.core.task import Task


def is_valid_identifier(string: str) -> bool:
    """
    Determines whether a string is a valid Python identifier (meaning it can
    be used as a variable name or keyword argument).

    Args:
        - string (str): string to be validated

    Returns:
        - bool: boolean specifying whether the provided string is a valid Python
            identifier

    Example:
        ```python
        >>> is_valid_identifier('hi5')
        True
        >>> is_valid_identifier('5hi')
        False
        >>> is_valid_identifier('from')
        False
        >>> is_valid_identifier('hi.5')
        False
        ```
    """
    return string.isidentifier() and not keyword.iskeyword(string)


class Edge:
    """
    Edges represent connections between Tasks.

    At a minimum, an edge links an `upstream_task` and a `downstream_task`
    indicating that the downstream task shouldn't attempt to run until the upstream
    task is complete.

    In addition, edges can specify a key that describe how upstream results
    are passed to the downstream task.

    Args:
        - upstream_task (Any): the task that must run before the
            `downstream_task`. It will be converted to as task with
            `prefect.utilities.tasks.as_task()`
        - downstream_task (Any): the task that will be run after the
            `upstream_task`. The upstream task state is passed to the
            downstream task's trigger function to determine whether the
            downstream task should run. It will be converted to as task with
            `prefect.utilities.tasks.as_task()`
        - key (str, optional): Passing a key indicates
            that the upstream result should be passed to the downstream
            task as a keyword argument given by `key`.
        - mapped (bool, optional): boolean indicating whether this edge
            represents a downstream mapped task; defaults to `False`
        - flattened (bool, optional): boolean indicating whether this edge
            represents an upstream flattened task; defaults to `False
        - flow (prefect.Flow, optional): a flow object that will be used
            if either the `upstream_task` or `downstream_task` is a
            collection that needs to be bound to a flow. If not provided,
            the context flow will be used instead.

    The key indicates that the result of the upstream task should be passed
    to the downstream task under the key.

    In general, Edges are created and handled in the background by the [Flow](flow.html)
    class and will not be directly instantiated by users.

    Example:
        ```python
        from prefect import *
        from prefect.core import Edge

        class Add(Task):
            def run(self, x):
                return x + 1

        class Number(Task):
            def run(self):
                return 2

        # passes the result of the Number() task to Add() as 'x'
        edge = Edge(Number(), Add(), key='x')
        ```
    """

    def __init__(
        self,
        upstream_task: Any,
        downstream_task: Any,
        key: str = None,
        mapped: bool = None,
        flattened: bool = None,
        flow: "prefect.core.flow.Flow" = None,
    ):
        if upstream_task is downstream_task:
            raise ValueError("Edges can not connect a task to itself.")

        if key is not None:
            if not (isinstance(key, str) and is_valid_identifier(key)):
                raise ValueError(
                    'Key must be a valid identifier (received "{}")'.format(key)
                )

        annotations = {}
        if isinstance(upstream_task, prefect.utilities.edges.EdgeAnnotation):
            annotations.update(upstream_task.annotations)
        if isinstance(downstream_task, prefect.utilities.edges.EdgeAnnotation):
            annotations.update(downstream_task.annotations)
        upstream_task = prefect.utilities.tasks.as_task(upstream_task, flow=flow)
        downstream_task = prefect.utilities.tasks.as_task(downstream_task, flow=flow)

        self.key = key
        self.upstream_task = upstream_task
        self.downstream_task = downstream_task
        self.mapped = annotations.get("mapped", mapped or False)
        self.flattened = annotations.get("flattened", flattened or False)

    # Comparison --------------------------------------------------------------

    @property
    def tasks(self) -> Set[Task]:
        """
        Returns a set of both upstream and downstream tasks for this edge.
        """
        return {self.upstream_task, self.downstream_task}

    def __repr__(self) -> str:
        desc = f"Edge(key={self.key}, mapped={self.mapped}, flattened={self.flattened})"
        return f"<{desc}: {self.upstream_task.name} to {self.downstream_task.name}>"

    def __eq__(self, other: "Edge") -> bool:  # type: ignore
        if type(self) == type(other):
            attrs = ["upstream_task", "downstream_task", "key", "mapped", "flattened"]
            return all(getattr(self, a) == getattr(other, a) for a in attrs)
        return False

    def __hash__(self) -> int:
        return hash(
            (
                self.upstream_task,
                self.downstream_task,
                self.key,
                self.mapped,
                self.flattened,
            )
        )

    def serialize(self) -> dict:
        """
        Represents the Edge as a dict.
        """
        return prefect.serialization.edge.EdgeSchema().dump(self)
