import ujson
import prefect
import prefect.utilities.serialize


class Edge:
    """
    Edges connect tasks, creating a dependency. The downstream
    task will not be run until the upstream task runs.
    """

    def __init__(self, upstream_task, downstream_task):
        """
        upstream_task: Task
            The task that runs first
        downstream_task: Task
            The task that runs second
        """
        if not isinstance(upstream_task, prefect.task.Task):
            raise TypeError(
                'upstream_task must be a Task; received {}'.format(
                    type(upstream_task).__name__))
        if not isinstance(downstream_task, prefect.task.Task):
            raise TypeError(
                'downstream_task must be a Task; received {}'.format(
                    type(downstream_task).__name__))
        self.id = '{}/{}'.format(upstream_task.id, downstream_task.id)
        self.upstream_task = upstream_task
        self.downstream_task = downstream_task

    def __repr__(self):
        return '{}({} -> {})'.format(
            type(self).__name__, self.upstream_task, self.downstream_task)

    def run_after_upstream(self, edge_id, result):
        """
        Called after the upstream task runs.

        Args:
            result: The result of the upstream task's run() function.
        """
        pass

    def run_before_downstream(self, edge_id):
        """
        Called before the downstream task runs.

        Returns a dictionary that will be passed to the task as keyword
        arguments.
        """
        return {}

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and (self.upstream_task, self.downstream_task) ==
                (other.upstream_task, other.downstream_task))  #yapf: disable

    def __hash__(self):
        return id(self)

    def serialize(self):
        return {
            'id': self.id,
            'upstream_task': self.upstream_task.id,
            'downstream_task': self.downstream_task.id,
            'serialized': prefect.utilities.serialize.serialize(self)
        }

    @classmethod
    def deserialize(cls, serialized):
        obj = prefect.utilities.serialize.deserialize(serialized['serialized'])
        if not isinstance(obj, cls):
            raise TypeError(
                'Expected {}; received {}'.format(
                    cls.__name__, type(obj).__name__))
        return obj


class Pipe(Edge):
    """
    Pipes move results from upstream tasks to downstream tasks.
    """

    def __init__(self, upstream_task_result, downstream_task, key):
        """
        task: Task
            The task generating the piped result
        index: Any
            An optional index for the piped result. For example, if the result
            were a dictionary the index could select a specific key.
        """
        if not isinstance(upstream_task_result, prefect.task.TaskResult):
            upstream_task_result = prefect.task.TaskResult(
                task=upstream_task_result,
                index=None,)

        super().__init__(
            upstream_task=upstream_task_result.task,
            downstream_task=downstream_task)
        self.task_result = upstream_task_result
        self.key = key
        self.index = upstream_task_result.index
        self._repr_index = upstream_task_result._repr_index()
        self.id = '{}/{}/{}'.format(
            self.upstream_task.id, self.downstream_task.id, self._repr_index)

    def __repr__(self):
        return '{}({} -> {})'.format(
            type(self).__name__, self.task_result, self.downstream_task)

    def serialize(self, edge_id: str, result) -> bytes:
        """
        Given a task result and id, returns a value that should be
        serialized to store the task result.

        Args:
            edge_id (str): a unique id that identifies this edge in this run
            result (obj): the result of the upstream task
        """
        return result

    def deserialize(self, edge_id: str, serialized_result: bytes):
        """
        Given a serialized representation of a task result, returns the
        original result

        Args:
            edge_id (str): a unique id that identifies this edge in this run
            serialized_result (bytes): the serialized task result
        """
        return result

    def run_after_upstream(self, edge_id: str, result) -> bytes:
        """
        Takes the (optionally indexed) result, applies the serialization,
        and returns a serialized version of the result that can be stored in
        the database.

        Args:
            edge_id (str): a unique id that identifies this edge in this run
            result (obj): the result of the upstream task
        """
        if self.index is not None:
            result = result[self.index]
        return self.serialize(edge_id, result)

    def run_before_downstream(self, edge_id: str, serialized_result: bytes):
        """
        Deserializes the result and returns a dictionary that will be passed
        to the downstream task as keyword arguments.

        Args:
            edge_id (str): a unique id that identifies this edge in this run
            result (bytes): the serialized task result
        """
        return {self.key: self.deserialize(edge_id, serialized_result)}
