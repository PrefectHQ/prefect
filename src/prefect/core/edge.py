import keyword
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

    At a minimum, edges link an `upstream_task` and a `downstream_task`
    indicating that the downstream task shouldn't run until the upstream
    task is complete.

    In addition, edges can specify a key that describe how upstream results
    are passed to the downstream task.

    Args:
        - upstream_task (Task): the task that must run before the `downstream_task`
        - downstream_task (Task): the task that will be run after the
            `upstream_task`. The upstream task state is passed to the
            downstream task's trigger function to determine whether the
            downstream task should run.
        - key (str): Optional. Passing a key indicates
            that the upstream result should be passed to the downstream
            task as a keyword argument.

    The key indicates that the result of the upstream task should be passed
    to the downstream task under the key.
    """

    def __init__(
        self, upstream_task: Task, downstream_task: Task, key: str = None
    ) -> None:
        self.upstream_task = upstream_task
        self.downstream_task = downstream_task

        if key is not None:
            if not (isinstance(key, str) and is_valid_identifier(key)):
                raise ValueError(
                    'Key must be a valid identifier (received "{}")'.format(key)
                )
        self.key = key

    # Comparison --------------------------------------------------------------

    def __repr__(self) -> str:
        return "<Edge{k}: {u} to {d}>".format(
            u=self.upstream_task.name,
            d=self.downstream_task.name,
            k=" (key={})".format(self.key) if self.key else "",
        )

    def __eq__(self, other: "Edge") -> bool:  # type: ignore
        if type(self) == type(other):
            self_cmp = (self.upstream_task, self.downstream_task, self.key)
            other_cmp = (other.upstream_task, other.downstream_task, other.key)
            return self_cmp == other_cmp
        return False

    def __hash__(self) -> int:
        return hash((self.upstream_task, self.downstream_task, self.key))
