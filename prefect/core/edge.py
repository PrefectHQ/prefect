from prefect.core.task import Task
from prefect.utilities.strings import is_valid_identifier
from prefect.utilities.serialize import Serializable


class Edge(Serializable):

    def __init__(self, upstream_task, downstream_task, key=None):
        """
        Edges represent connections between Tasks.

        At a minimum, edges link an upstream_task and a downstream_task
        indicating that the downstream task shouldn't run until the upstream
        task is complete.

        In addition, edges can specify a key that describe how upstream results
        are passed to the downstream task.

        Args: upstream_task (str): the name of a task that must run before the
            downstream_task

            downstream_task (str): the name of a task that will be run after the
                upstream_task. The upstream task state is passed to the
                downstream task's trigger function to determine whether the
                downstream task should run.

            key (str): Optional. Passing a key indicates
                that the upstream result should be passed to the downstream
                task as a keyword argument.

        The key indicates that the result of the upstream task should be passed
        to the downstream task under the key.

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
        self.key = key
