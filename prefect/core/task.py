import inspect
import uuid
from datetime import timedelta
from typing import Iterable, Mapping

from slugify import slugify

import prefect
from prefect.utilities.serialize import (Encrypted, EncryptedPickle)
from prefect.core.base import PrefectObject


class Task(PrefectObject):

    def __init__(
            self,
            name='Task',
            description=None,
            id=None,
            max_retries=0,
            retry_delay=timedelta(minutes=1),
            timeout=None,
            trigger=None,
            **kwargs):
        self.name = name
        self.id = id or str(uuid.uuid4())
        self.description = description

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.trigger = trigger or prefect.tasks.triggers.AllSuccessful
        self._set_dependencies(upstream_task_results=kwargs)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.name)

    def __eq__(self, other):
        return type(self) == type(other) and self.id == other.id

    def __hash__(self):
        return id(self)

    def __getitem__(self, index):
        return self()[index]

    def __call__(
            self, *args, upstream_tasks=None, downstream_tasks=None, **kwargs):
        signature = inspect.signature(self.run)
        callargs = dict(signature.bind_partial(*args, **kwargs).arguments)

        return self._set_dependencies(
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            upstream_task_results=callargs)

    def _set_dependencies(
            self,
            *,
            upstream_tasks=None,
            downstream_tasks=None,
            upstream_task_results=None,
            flow=None):
        flow = flow or prefect.context.Context.get('flow')
        if flow is None:
            flow = prefect.core.flow.Flow()

        flow.set_dependencies(
            task=self,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            upstream_results=upstream_task_results)
        return TaskResult(flow=flow, task=self)

    # Run  --------------------------------------------------------------------

    def inputs(self):
        return tuple(inspect.signature(self.run).parameters.keys())

    def run(self):
        """
        The main entrypoint for tasks.

        In addition to running arbitrary functions, tasks can interact with
        Prefect in a few ways:
            1. Return an optional result. When this function runs successfully,
                the task is considered successful and the result (if any) is
                made available to downstream edges.
            2. Raise an error. Errors are interpreted as failure.
            3. Raise a signal. Signals can include FAIL, SUCCESS, WAIT, etc.
                and indicate that the task should be put in the indicated
                state.
                - FAIL will lead to retries if appropriate
                - WAIT will end execution and skip all downstream tasks with
                    state WAITING_FOR_UPSTREAM (unless appropriate triggers
                    are set). The task can be run again and should check
                    context.is_waiting to see if it was placed in a WAIT.
        """
        raise NotImplementedError()

    # Serialize ---------------------------------------------------------------

    def serialize(self, pickle=False):

        serialized = super().serialize()

        serialized.update(
            dict(
                name=self.name,
                slug=self.slug,
                description=self.description,
                max_retries=self.max_retries,
                retry_delay=self.retry_delay,
                timeout=self.timeout,
                trigger=self.trigger,
                type=type(self).__name__))

        if pickle:
            serialized['pickle'] = EncryptedPickle(self)

        return serialized
