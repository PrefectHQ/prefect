from typing import Dict, Any


class EdgeAnnotation:
    """
    A parent class for containers like `unmapped` and `flatten` that indicate
    an annotation for an edge

    EdgeAnnotations store a set of annotations, allowing multiple annotations
    to be applied.
    """

    annotations = {}  # type: Dict[str, Any]

    def __init__(self, value: Any):
        # copy class attribute to the instance
        self.annotations = self.annotations.copy()

        if isinstance(value, EdgeAnnotation):
            self.annotations.update(value.annotations)
            value = value.value
        self.value = value  # type: Any


class mapped(EdgeAnnotation):
    """
    A container for specifying that a task should be mapped over when supplied
    as the input to another task.

    Args:
        - value (Any): the task or value to mark as "mapped"; if not a Task
            subclass, Prefect will attempt to convert it to one when the edge is
            created.

    Example:
        ```python
        from prefect import Flow, Task, mapped

        class AddTask(Task):
            def run(self, x, y):
                return x + y

        class ListTask(Task):
            def run(self):
                return [1, 2, 3]

        with Flow("My Flow"):
            add = AddTask()
            ll = ListTask()
            result = add(x=mapped(ll), y=5)
        ```
    """

    annotations = {"mapped": True}


class unmapped(EdgeAnnotation):
    """
    A container for specifying that a task should _not_ be mapped over when
    called with `task.map`.

    Args:
        - value (Any): the task or value to mark as "unmapped"; if not a Task
            subclass, Prefect will attempt to convert it to one when the edge is
            created.

    Example:
        ```python
        from prefect import Flow, Task, unmapped

        class AddTask(Task):
            def run(self, x, y):
                return x + y

        class ListTask(Task):
            def run(self):
                return [1, 2, 3]

        with Flow("My Flow"):
            add = AddTask()
            ll = ListTask()
            result = add.map(x=ll, y=unmapped(5), upstream_tasks=[unmapped(Task())])
        ```
    """

    annotations = {"mapped": False}


class flatten(EdgeAnnotation):
    """
    A container for specifying that a task's output should be flattened before
    being passed to another task.

    Args:
        - value (Any): the task or value to mark as "flattened"; if not a Task
            subclass, Prefect will attempt to convert it to one when the edge is
            created.

    Example:
        ```python
        from prefect import Flow, Task, flatten

        class Add(Task):
            def run(self, x):
                return x + 100

        class NestedListTask(Task):
            def run(self):
                return [[1], [2, 3]]

        with Flow("My Flow"):
            add = Add()
            ll = NestedListTask()

            result = add.map(x=flatten(ll))

        # result represents [101, 102, 103]
        ```
    """

    annotations = {"flattened": True}
