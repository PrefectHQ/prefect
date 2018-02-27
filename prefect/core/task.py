import copy
import uuid
import inspect
from datetime import timedelta
from typing import Iterable, Mapping

import prefect
from prefect.utilities.serialize import SerializedEncryptedPickle
from prefect.core.base import PrefectObject


class Task(PrefectObject):

    def __init__(
            self,
            name='Task',
            id=None,
            description=None,
            max_retries=0,
            retry_delay=timedelta(minutes=1),
            timeout=None,
            trigger=None):
        self.name = name
        self.description = description

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        if trigger is None:
            trigger = prefect.tasks.triggers.AllSuccessful
        elif not isinstance(trigger, prefect.tasks.triggers.Trigger):
            raise TypeError('Expected a Trigger object.')
        self.trigger = trigger

        super().__init__(id=id)

        flow = prefect.context.Context.get('flow')
        if flow:
            flow.add_task(self)

    def __repr__(self):
        return '{}("{}")'.format(type(self).__name__, self.name)

    def __hash__(self):
        return id(self)

    def __getitem__(self, index):
        return self()[index]

    def __call__(self, *args, _wait_for=None, **kwargs):
        # this will raise an error if callargs weren't all provided
        signature = inspect.signature(self.run)
        callargs = dict(signature.bind(*args, **kwargs).arguments)

        return self.set_dependencies(
            upstream_tasks=_wait_for, upstream_task_results=callargs)

    def copy(self):
        new = copy.copy(self)
        new.id = uuid.uuid4()
        return new

    # Dependencies -------------------------------------------------------------

    def set_dependencies(
            self,
            *,
            upstream_tasks=None,
            downstream_tasks=None,
            upstream_task_results=None,
            flow=None):
        flow = flow or prefect.context.Context.get('flow')
        if flow is None:
            raise ValueError(
                'Dependencies can only be set within a Flow context.')

        flow.set_dependencies(
            task=self,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            upstream_results=upstream_task_results)
        return prefect.core.task_result.TaskResult(flow=flow, task=self)

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
                id=self.id,
                description=self.description,
                max_retries=self.max_retries,
                retry_delay=self.retry_delay,
                timeout=self.timeout,
                trigger=self.trigger,
                type=type(self).__name__))

        if pickle:
            serialized['pickle'] = SerializedEncryptedPickle(self)

        return serialized
