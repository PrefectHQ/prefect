import prefect
from typing import Dict, Any


class EdgeAttribute:
    """
    A parent class for containers like `unmapped` and `flat` that indicate
    an annotation for an edge

    EdgeAttributes store a set of annotations, allowing multiple annotations
    to be applied.
    """

    def __init__(self, task: "prefect.Task", annotations: Dict[str, Any]):
        self.annotations = dict()
        if isinstance(task, EdgeAttribute):
            self.annotations.update(task.annotations)
        self.annotations.update(annotations)
        self.task = prefect.utilities.tasks.as_task(task)


class mapped(EdgeAttribute):
    """
    A container for specifying that a task should be mapped over when supplied as
    the input to another task.

    Args:
        - task (Task): the task to mark as "unmapped"; if not a Task subclass,
            Prefect will attempt to convert it to one.

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

    def __init__(self, task: "Task"):
        super().__init__(task=task, annotations={"mapped": True})


class unmapped(EdgeAttribute):
    """
    A container for specifying that a task should _not_ be mapped over when
    called with `task.map`.

    Args:
        - task (Task): the task to mark as "unmapped"; if not a Task subclass,
            Prefect will attempt to convert it to one.

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

    def __init__(self, task: "Task"):
        super().__init__(task=task, annotations={"mapped": False})


class flat(EdgeAttribute):
    """
    A container for specifying that a task's output should be flattened before
    being passed to another task. 

    Args:
        - task (Task): the task to mark as "flattened"; if not a Task subclass,
            Prefect will attempt to convert it to one.

    Example:
        ```python
        from prefect import Flow, Task, flat

        class Add(Task):
            def run(self, x):
                return x + 100

        class NestedListTask(Task):
            def run(self):
                return [[1], [2, 3]]

        with Flow("My Flow"):
            add = Add()
            ll = ListTask()

            result = add.map(x=flat(ll))

        # result represents [101, 102, 103]
        ```
    """

    def __init__(self, task: "Task"):
        super().__init__(task=task, annotations={"flat": True})
