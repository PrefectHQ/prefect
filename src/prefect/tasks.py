import inspect
import time
from functools import update_wrapper
from typing import Any, Callable, Dict, Iterable, Tuple, Union
from uuid import UUID

import pendulum

from prefect.client import OrionClient
from prefect.futures import PrefectFuture, return_val_to_state
from prefect.orion.schemas.responses import SetStateStatus
from prefect.orion.schemas.states import State, StateType
from prefect.utilities.hashing import stable_hash, to_qualified_name


def propose_state(client: OrionClient, task_run_id: UUID, state: State) -> State:
    """
    TODO: Consider rolling this behavior into the `Client` state update method once we
          understand how we want to handle ABORT cases
    """
    response = client.set_task_run_state(
        task_run_id,
        state=state,
    )
    if response.status == SetStateStatus.ACCEPT:
        if response.details.state_details:
            state.state_details = response.details.state_details
        return state

    if response.status == SetStateStatus.ABORT:
        raise RuntimeError("ABORT is not yet handled")

    server_state = response.details.state

    return server_state


class Task:
    """
    Base class representing Prefect worktasks.
    """

    def __init__(
        self,
        name: str = None,
        fn: Callable = None,
        description: str = None,
        tags: Iterable[str] = None,
        retries: int = 0,
        retry_delay_seconds: Union[float, int] = 0,
    ):
        if not fn:
            raise TypeError("__init__() missing 1 required argument: 'fn'")
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn

        self.tags = set(tags if tags else [])

        # the task key is a hash of (name, fn, tags)
        # which is a stable representation of this unit of work.
        # note runtime tags are not part of the task key; they will be
        # recorded as metadata only.
        self.task_key = stable_hash(
            self.name,
            to_qualified_name(self.fn),
            str(sorted(self.tags or [])),
        )

        self.dynamic_key = 0

        # TaskRunPolicy settings
        # TODO: We can instantiate a `TaskRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds

    def _run(
        self,
        task_run_id: UUID,
        flow_run_id: UUID,
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ) -> None:
        from prefect.context import TaskRunContext

        client = OrionClient()

        # Transition from `PENDING` -> `RUNNING`
        state = propose_state(client, task_run_id, State(type=StateType.RUNNING))

        # Only run the task if we enter a `RUNNING` state
        while state.is_running():

            try:
                with TaskRunContext(
                    task_run_id=task_run_id,
                    flow_run_id=flow_run_id,
                    task=self,
                    client=client,
                ):
                    result = self.fn(*call_args, **call_kwargs)
            except Exception as exc:
                terminal_state = State(
                    type=StateType.FAILED,
                    message="Task run encountered an exception.",
                    data=exc,
                )
            else:
                terminal_state = return_val_to_state(result)

            state = propose_state(client, task_run_id, terminal_state)

            if state.is_scheduled():  # Received a retry from the backend
                start_time = pendulum.instance(state.state_details.scheduled_time)
                wait_time = start_time.diff(abs=False).in_seconds() * -1
                print(f"Task is scheduled to run again {start_time.diff_for_humans()}")
                if wait_time > 0:
                    print(f"Sleeping for {wait_time}s...")
                    time.sleep(wait_time)

                state = propose_state(
                    client, task_run_id, State(type=StateType.RUNNING)
                )

        return state

    def __call__(self, *args: Any, **kwargs: Any) -> PrefectFuture:
        from prefect.context import FlowRunContext, TaskRunContext

        flow_run_context = FlowRunContext.get()
        if not flow_run_context:
            raise RuntimeError("Tasks cannot be called outside of a flow.")

        if TaskRunContext.get():
            raise RuntimeError(
                "Tasks cannot be called from within tasks. Did you mean to call this "
                "task in a flow?"
            )

        task_run_id = flow_run_context.client.create_task_run(
            task=self,
            flow_run_id=flow_run_context.flow_run_id,
        )

        flow_run_context.client.set_task_run_state(
            task_run_id, State(type=StateType.PENDING)
        )

        future = flow_run_context.executor.submit(
            task_run_id,
            self._run,
            task_run_id=task_run_id,
            flow_run_id=flow_run_context.flow_run_id,
            call_args=args,
            call_kwargs=kwargs,
        )

        # Increment the dynamic_key so future task calls are distinguishable from this
        # task run
        self.dynamic_key += 1

        return future


def task(_fn: Callable = None, *, name: str = None, **task_init_kwargs: Any):
    # TOOD: See notes on decorator cleanup in `prefect.flows.flow`
    if _fn is None:
        return lambda _fn: Task(fn=_fn, name=name, **task_init_kwargs)
    return Task(fn=_fn, name=name, **task_init_kwargs)
