from prefect.utilities.strings import is_valid_identifier
from prefect.utilities.serialize import Serializable


class Edge(Serializable):

    def __init__(self, upstream_task_id, downstream_task_id, key=None):
        """
        Edges represent connections between Tasks.

        At a minimum, edges link an upstream_task_id and a downstream_task_id
        indicating that the downstream task shouldn't run until the upstream
        task is complete.

        In addition, edges can specify a key that describe how upstream results
        are passed to the downstream task.

        Args: upstream_task_id (str): the id of a task that must run before the
            downstream_task

            downstream_task_id (str): the id of a task that will be run after the
                upstream_task. The upstream task state is passed to the
                downstream task's trigger function to determine whether the
                downstream task should run.

            key (str): Optional. Passing a key indicates
                that the upstream result should be passed to the downstream
                task as a keyword argument.

        The key indicates that the result of the upstream task should be passed
        to the downstream task under the key.

        """
        self.upstream_task_id = upstream_task_id
        self.downstream_task_id = downstream_task_id

        if key is not None:
            if not is_valid_identifier(key):
                raise ValueError(
                    'Downstream key ("{}") must be a valid identifier'.format(
                        key))
        self.key = key

    # Comparison --------------------------------------------------------------

    def __hash__(self):
        return id(self)
