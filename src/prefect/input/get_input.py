from typing import (
    TYPE_CHECKING,
    Generic,
    Literal,
    Optional,
    Type,
    TypeVar,
    Union,
    overload,
)
from uuid import UUID, uuid4

import anyio
import orjson
import pydantic

from prefect.context import FlowRunContext
from prefect.input.actions import (
    create_flow_run_input,
    filter_flow_run_input,
)
from prefect.input.run_input import RunInput
from prefect.utilities.asyncutils import sync_compatible

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRunInput


T = TypeVar("T", bound="RunInput")


@sync_compatible
async def send_input(
    input: "RunInput", flow_run_id: UUID, sender: Optional[Union[str, UUID]] = None
):
    """
    Send `input` to the given flow run.

    Args:
        - input (RunInput): the input to send
        - flow_run_id (UUID): the flow run ID to send the input to
        - sender (Optional[Union[str, UUID]]): the sender of the input,
          defaults to the current flow run ID if one exists.
    """

    if sender is None:
        context = FlowRunContext.get()
        if context is not None and context.flow_run is not None:
            sender = context.flow_run.id

    keyset = input.__class__.keyset_from_type()
    key = f"{keyset['response']}-{uuid4()}"

    wrapper = InputWrapper(value=input, key=key, sender=str(sender))

    await create_flow_run_input(
        key=key, value=orjson.loads(wrapper.json()), flow_run_id=flow_run_id
    )


class GetInput(Generic[T]):
    def __init__(
        self,
        run_input_cls: Type[T],
        timeout: Optional[float] = 3600,
        poll_interval: float = 10,
        raise_timeout_error: bool = False,
        exclude_keys: Optional[set[str]] = None,
    ):
        self.run_input_cls = run_input_cls
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.exclude_keys = set()
        self.raise_timeout_error = raise_timeout_error

        if exclude_keys is not None:
            self.exclude_keys.update(exclude_keys)

        self.keyset = self.run_input_cls.keyset_from_type()

    def __iter__(self):
        return self

    def __next__(self) -> "InputWrapper[T]":
        try:
            return self.next()
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopIteration

    def __aiter__(self):
        return self

    async def __anext__(self) -> "InputWrapper[T]":
        try:
            return await self.next()
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopAsyncIteration

    async def filter_for_inputs(self):
        flow_run_inputs = await filter_flow_run_input(
            key_prefix=self.keyset["response"],
            limit=1,
            exclude_keys=self.exclude_keys,
        )

        if flow_run_inputs:
            self.exclude_keys.add(*[i.key for i in flow_run_inputs])

        return flow_run_inputs

    def to_input_wrapper(self, flow_run_input: "FlowRunInput") -> "InputWrapper[T]":
        decoded = flow_run_input.decoded_value
        value = decoded.pop("value")
        return InputWrapper(value=self.run_input_cls(**value), **decoded)

    @sync_compatible
    async def next(self) -> "InputWrapper[T]":
        flow_run_inputs = await self.filter_for_inputs()
        if flow_run_inputs:
            return self.to_input_wrapper(flow_run_inputs[0])

        with anyio.fail_after(self.timeout):
            while True:
                await anyio.sleep(self.poll_interval)
                flow_run_inputs = await self.filter_for_inputs()
                if flow_run_inputs:
                    return self.to_input_wrapper(flow_run_inputs[0])


class GetInputUnwrapped(GetInput[T]):
    def __next__(self) -> T:
        try:
            return self.next()
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopIteration

    def __aiter__(self):
        return self

    async def __anext__(self) -> T:
        try:
            return await self.next()
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopAsyncIteration

    @sync_compatible
    async def next(self) -> T:
        wrapper = await super().next()
        return wrapper.unwrap()


@overload
def get_input(
    run_input_cls: Type[T],
    wrapped: Literal[True],
    timeout: Optional[float] = 3600.0,
    poll_interval: float = 10.0,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[set[str]] = None,
) -> GetInput[T]:
    ...


@overload
def get_input(
    run_input_cls: Type[T],
    wrapped: Literal[False],
    timeout: Optional[float] = 3600.0,
    poll_interval: float = 10.0,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[set[str]] = None,
) -> GetInputUnwrapped[T]:
    ...


@overload
def get_input(
    run_input_cls: Type[T],
    wrapped: bool = False,
    timeout: Optional[float] = 3600.0,
    poll_interval: float = 10.0,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[set[str]] = None,
) -> GetInputUnwrapped[T]:
    ...


def get_input(
    run_input_cls: Type[T],
    wrapped: bool = False,
    timeout: Optional[float] = 3600.0,
    poll_interval: float = 10.0,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[set[str]] = None,
):
    """
    Get input for the given run input class.

    Args:
        run_input_cls (Type[T]): the run input class to get input for
        wrapped (bool, optional): whether or not to return the input wrapped in
            an `InputWrapper`, defaults to `False`
        timeout (float, optional): the timeout in seconds to wait for input,
            defaults to 3600
        poll_interval (float, optional): the interval in seconds to poll for
            input, defaults to 10
        raise_timeout_error (bool, optional): when used as a generator whether
            or not to raise a `TimeoutError` if the timeout is reached,
            defaults to `False`
        exclude_keys (Optional[set[str]], optional): keys to exclude from the
            input
    """

    kwargs = {
        "run_input_cls": run_input_cls,
        "timeout": timeout,
        "poll_interval": poll_interval,
        "raise_timeout_error": raise_timeout_error,
        "exclude_keys": exclude_keys,
    }

    if wrapped:
        return GetInput(**kwargs)
    else:
        return GetInputUnwrapped(**kwargs)


class InputWrapper(Generic[T], pydantic.BaseModel):
    value: T
    key: str
    sender: Optional[str] = None

    def unwrap(self) -> T:
        return self.value


InputWrapper.update_forward_refs()
