from weakref import WeakValueDictionary
import copy
import uuid
import inspect
from datetime import timedelta
from typing import Iterable, Mapping

import prefect
from prefect.context import Context
from prefect.utilities.serializers import Serializable

TASK_REGISTRY = WeakValueDictionary()

class Task(Serializable):

    def __init__(
            self,
            name=None,
            id=None,
            description=None,
            max_retries=0,
            retry_delay=timedelta(minutes=1),
            timeout=None,
            trigger=None,
            secrets=None):
        self.id = id or uuid.uuid4()
        self.name = name or type(self).__name__
        self.description = description

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        if trigger is None:
            trigger = prefect.triggers.all_successful
        # elif not isinstance(trigger, prefect.triggers.Trigger):
        #     raise TypeError('Expected a Trigger object.')
        self.trigger = trigger

        flow = Context.get('flow')
        if flow:
            flow.add_task(self)
        self.secrets = secrets or {}

        self.register()

    def __repr__(self):
        return '<Task: "{self.name}" type={cls} id={id}>'.format(
            cls=type(self).__name__, self=self, id=self.short_id)

    def __hash__(self):
        return id(self)

    def __getitem__(self, index):
        return self()[index]

    def __call__(self, *args, _wait_for=None, **kwargs):
        # this will raise an error if callargs weren't all provided
        signature = inspect.signature(self.run)
        callargs = dict(signature.bind(*args, **kwargs).arguments)

        # bind() compresses all variable keyword arguments, so we expand them
        var_kw_arg = prefect.utilities.functions.get_var_kw_arg(self.run)
        callargs.update(callargs.pop(var_kw_arg, {}))

        return self.set_dependencies(
            upstream_tasks=_wait_for, keyword_results=callargs)

    def register(self):
        TASK_REGISTRY[self.id] = self

    def copy(self):
        new = copy.copy(self)
        new.id = uuid.uuid4()
        new.register()
        return new

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        self._id = str(value)

    @property
    def short_id(self):
        return self._id[:8]

    @property
    def flow(self):
        return prefect.utilities.flows.get_flow_by_id(self._flow_id)

    @flow.setter
    def flow(self, flow):
        self._flow_id = flow.id

    # Dependencies -------------------------------------------------------------

    def set_dependencies(
            self,
            *,
            upstream_tasks=None,
            downstream_tasks=None,
            keyword_results=None,
            flow=None):
        flow = flow or prefect.context.Context.get('flow')
        if flow is None:
            raise ValueError(
                'Dependencies can only be set within a Flow context.')

        flow.set_dependencies(
            task=self,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            keyword_results=keyword_results)
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

    def serialize(self):

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

        return serialized

    def after_deserialize(self, serialized):
        self.id = serialized['id']
        self.register()
