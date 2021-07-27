import inspect
from dataclasses import dataclass
from functools import update_wrapper
from typing import Any, Callable, Dict, Iterable, Tuple
from uuid import UUID

from pydantic import validate_arguments, BaseModel

from prefect import _context
from prefect.client import OrionClient
from prefect.futures import PrefectFuture
from prefect.orion.utilities.functions import parameter_schema
from prefect.utilities import file_hash
from prefect.orion.schemas.core import StateType, State


class Flow:
    """
    Base class representing Prefect workflows.
    """

    # no docstring until we have a standard and the classes
    # are more polished
    def __init__(
        self,
        name: str = None,
        fn: Callable = None,
        version: str = None,
        executor=None,
        description: str = None,
        tags: Iterable[str] = None,
    ):
        if not fn:
            raise TypeError("__init__() missing 1 required argument: 'fn'")
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn

        # Version defaults to a hash of the function's file
        flow_file = fn.__globals__.get("__file__")  # type: ignore
        self.version = version or (file_hash(flow_file) if flow_file else None)
        self.executor = executor

        self.tags = set(tags if tags else [])

        self.parameters = parameter_schema(self.fn)

    def _run(
        self,
        client: OrionClient,
        flow_run_id: str,
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        """
        TODO: Note that pydantic will now coerce parameter types into the correct type
              even if the user wants failure on inexact type matches. We may want to
              implement a strict runtime typecheck with a configuration flag
        TODO: `validate_arguments` can throw an error while wrapping `fn` if the
              signature is not pydantic-compatible. We'll want to confirm that it will
              work at Flow.__init__ so we can raise errors to users immediately
        TODO: Implement state orchestation logic using return values from the API
        """

        client.set_flow_run_state(flow_run_id, State(type=StateType.RUNNING))

        try:
            result = validate_arguments(self.fn)(*call_args, **call_kwargs)
        except Exception as exc:
            result = exc
            state_type = StateType.FAILED
            message = "Flow run encountered a user exception."
        else:
            state_type = StateType.COMPLETED
            message = "Flow run completed."

        state = State(type=state_type, message=message)
        client.set_flow_run_state(flow_run_id, state=state)

        return PrefectFuture(
            run_id=flow_run_id, result=result, is_exception=state.is_failed()
        )

    def __call__(self, *args: Any, **kwargs: Any) -> PrefectFuture:
        # Generate dict of passed parameters
        parameters = inspect.signature(self.fn).bind_partial(*args, **kwargs).arguments

        client = OrionClient()
        flow_run_id = client.create_flow_run(
            self,
            parameters=parameters,
        )
        with FlowRunContext(flow_run_id=flow_run_id, flow=self, client=client):
            client.set_flow_run_state(flow_run_id, State(type=StateType.PENDING))
            future = self._run(client, flow_run_id, call_args=args, call_kwargs=kwargs)

        return future


def flow(_fn: Callable = None, *, name: str = None, **flow_init_kwargs: Any):
    # TOOD: Using `**flow_init_kwargs` here hides possible settings from the user
    #       and it may be worth enumerating possible arguments explicitly for user
    #       friendlyness
    # TODO: For mypy type checks, @overload will have to be used to clarify return
    #       types for @flow and @flow(...)
    #       https://mypy.readthedocs.io/en/stable/generics.html?highlight=decorator#decorator-factories
    if _fn is None:
        return lambda _fn: Flow(fn=_fn, name=name, **flow_init_kwargs)
    return Flow(fn=_fn, name=name, **flow_init_kwargs)


class FlowRunContext(BaseModel):
    flow: Flow
    flow_run_id: UUID
    client: OrionClient

    class Config:
        allow_mutation = False
        arbitrary_types_allowed = True
        extra = "forbid"

    def __enter__(self):
        # We've frozen the rest of the data on the class but we'd like to still store
        # this token for resetting on context exit
        object.__setattr__(self, "__token", _context.flow_run.set(self))

    def __exit__(self, *_):
        _context.flow_run.reset(getattr(self, "__token"))
