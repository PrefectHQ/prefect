import peewee
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
        self.upstream_task = upstream_task
        self.downstream_task = downstream_task

    def __repr__(self):
        return '{}({} -> {})'.format(
            type(self).__name__, self.upstream_task, self.downstream_task)

    def run_upstream(self, result):
        """
        Called after the upstream task runs.

        Args:
            result: The result of the upstream task's run() function.
        """
        pass

    def run_downstream(self):
        """
        Called after the upstream task runs.
        """
        pass

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and (self.upstream_task, self.downstream_task) ==
                (other.upstream_task, other.downstream_task))  #yapf: disable

    def __hash__(self):
        return id(self)


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

    def id(self, run_id):
        return '{}/{}/{}'.format(run_id, self.task.id, self._repr_index)

    def __repr__(self):
        return '{}({} -> {})'.format(
            type(self).__name__, self.task_result, self.downstream_task)

    def serialize(self, result, run_id):
        """
        Given a task result and run_id, returns a value that should be
        serialized to store the task result.
        """
        return result

    def deserialize(self, result, run_id):
        """
        Given a serialized representation of a task result, returns the
        original result
        """
        return result

    def run_upstream(self, result, run_id):
        """
        Takes the (optionally indexed) result, applies the serialization,
        and stores the result in the database.
        """
        if self.index is not None:
            result = result[self.index]
        model = prefect.models.TaskResultModel.get_or_build(
            task_run_id=run_id, index=self._repr_index)
        model.result = result
        model.save()

    def run_downstream(self, run_id):
        """
        Retrieves the result from the database and deserializes it
        """
        if self.index is not None:
            _id = '{}/{}/{}'.format(run_id, self.task.id, self.index)
        else:
            _id = '{}/{}'.format(run_id, self.task.id)

        result = prefect.models.TaskResultModel.first(
            task_run_id=run_id, index=self._repr_index).result
        return {self.key: self.deserialize(result, run_id)}
