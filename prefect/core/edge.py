import uuid
from prefect.utilities.strings import is_valid_identifier
from prefect.core.base import PrefectObject


class Edge(PrefectObject):

    def __init__(self, upstream_task, downstream_task, key=None, id=None):
        """
        Edges represent connections between Tasks.

        At a minimum, edges link an upstream_task and a downstream_task
        indicating that the downstream task shouldn't run until the upstream
        task is complete.

        In addition, edges can specify a key that describe how upstream results
        are passed to the downstream task.

        Args: upstream_task (str): the id of a task that must run before the
            downstream_task

            downstream_task (str): the id of a task that will be run after the
                upstream_task. The upstream task state is passed to the
                downstream task's trigger function to determine whether the
                downstream task should run.

            key (str): Optional. Passing a key indicates
                that the upstream result should be passed to the downstream
                task as a keyword argument.

        The key indicates that the result of the upstream task should be passed
        to the downstream task under the key.
        """
        self.upstream_task = upstream_task
        self.downstream_task = downstream_task

        if key is not None:
            if not is_valid_identifier(key):
                raise ValueError(
                    'Key must be a valid identifier (received "{}")'.format(
                        key))
        self.key = key
        super().__init__(id=id)

    # Comparison --------------------------------------------------------------

    @property
    def _cmp(self):
        return (self.upstream_task, self.downstream_task, self.key)

    def __repr__(self):
        if self.key:
            return 'Edge({} to {} as "{}")'.format(*self._cmp)
        else:
            return 'Edge({} to {})'.format(
                self.upstream_task, self.downstream_task)

    def __eq__(self, other):
        if type(self) == type(other):
            return self._cmp == other._cmp
        return False

    def __hash__(self):
        return hash(self._cmp)

    def serialize(self):
        serialized = super().serialize(self)
        serialized.update(
            {
                'upstream_task': self.upstream_task,
                'downstream_task': self.downstream_task,
                'key': key
            })
        return serialized
