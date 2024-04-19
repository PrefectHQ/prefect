"""
This module contains functions that allow sending type-checked `RunInput` data
to flows at runtime. Flows can send back responses, establishing two-way
channels with senders. These functions are particularly useful for systems that
require ongoing data transfer or need to react to input quickly.
real-time interaction and efficient data handling. It's designed to facilitate
dynamic communication within distributed or microservices-oriented systems,
making it ideal for scenarios requiring continuous data synchronization and
processing. It's particularly useful for systems that require ongoing data
input and output.

The following is an example of two flows. One sends a random number to the
other and waits for a response. The other receives the number, squares it, and
sends the result back. The sender flow then prints the result.

Sender flow:

```python
import random
from uuid import UUID
from prefect import flow, get_run_logger
from prefect.input import RunInput

class NumberData(RunInput):
    number: int


@flow
async def sender_flow(receiver_flow_run_id: UUID):
    logger = get_run_logger()

    the_number = random.randint(1, 100)

    await NumberData(number=the_number).send_to(receiver_flow_run_id)

    receiver = NumberData.receive(flow_run_id=receiver_flow_run_id)
    squared = await receiver.next()

    logger.info(f"{the_number} squared is {squared.number}")
```

Receiver flow:
```python
import random
from uuid import UUID
from prefect import flow, get_run_logger
from prefect.input import RunInput

class NumberData(RunInput):
    number: int


@flow
async def receiver_flow():
    async for data in NumberData.receive():
        squared = data.number ** 2
        data.respond(NumberData(number=squared))
```
"""


from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    Literal,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID, uuid4

import anyio
import pydantic

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.input.actions import (
    create_flow_run_input,
    create_flow_run_input_from_model,
    ensure_flow_run_id,
    filter_flow_run_input,
    read_flow_run_input,
)
from prefect.utilities.asyncutils import sync_compatible

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRunInput
    from prefect.states import State

if HAS_PYDANTIC_V2:
    from prefect._internal.pydantic.v2_schema import create_v2_schema

R = TypeVar("R", bound="RunInput")
T = TypeVar("T")

Keyset = Dict[
    Union[Literal["description"], Literal["response"], Literal["schema"]], str
]


def keyset_from_paused_state(state: "State") -> Keyset:
    """
    Get the keyset for the given Paused state.

    Args:
        - state (State): the state to get the keyset for
    """

    if not state.is_paused():
        raise RuntimeError(f"{state.type.value!r} is unsupported.")

    base_key = f"{state.name.lower()}-{str(state.state_details.pause_key)}"
    return keyset_from_base_key(base_key)


def keyset_from_base_key(base_key: str) -> Keyset:
    """
    Get the keyset for the given base key.

    Args:
        - base_key (str): the base key to get the keyset for

    Returns:
        - Dict[str, str]: the keyset
    """
    return {
        "description": f"{base_key}-description",
        "response": f"{base_key}-response",
        "schema": f"{base_key}-schema",
    }


class RunInputMetadata(pydantic.BaseModel):
    key: str
    sender: Optional[str]
    receiver: UUID


class RunInput(pydantic.BaseModel):
    class Config:
        extra = "forbid"

    _description: Optional[str] = pydantic.PrivateAttr(default=None)
    _metadata: RunInputMetadata = pydantic.PrivateAttr()

    @property
    def metadata(self) -> RunInputMetadata:
        return self._metadata

    @classmethod
    def keyset_from_type(cls) -> Keyset:
        return keyset_from_base_key(cls.__name__.lower())

    @classmethod
    @sync_compatible
    async def save(cls, keyset: Keyset, flow_run_id: Optional[UUID] = None):
        """
        Save the run input response to the given key.

        Args:
            - keyset (Keyset): the keyset to save the input for
            - flow_run_id (UUID, optional): the flow run ID to save the input for
        """

        if HAS_PYDANTIC_V2:
            schema = create_v2_schema(cls.__name__, model_base=cls)
        else:
            schema = cls.schema(by_alias=True)

        await create_flow_run_input(
            key=keyset["schema"], value=schema, flow_run_id=flow_run_id
        )

        description = cls._description if isinstance(cls._description, str) else None
        if description:
            await create_flow_run_input(
                key=keyset["description"],
                value=description,
                flow_run_id=flow_run_id,
            )

    @classmethod
    @sync_compatible
    async def load(cls, keyset: Keyset, flow_run_id: Optional[UUID] = None):
        """
        Load the run input response from the given key.

        Args:
            - keyset (Keyset): the keyset to load the input for
            - flow_run_id (UUID, optional): the flow run ID to load the input for
        """
        flow_run_id = ensure_flow_run_id(flow_run_id)
        value = await read_flow_run_input(keyset["response"], flow_run_id=flow_run_id)
        if value:
            instance = cls(**value)
        else:
            instance = cls()
        instance._metadata = RunInputMetadata(
            key=keyset["response"], sender=None, receiver=flow_run_id
        )
        return instance

    @classmethod
    def load_from_flow_run_input(cls, flow_run_input: "FlowRunInput"):
        """
        Load the run input from a FlowRunInput object.

        Args:
            - flow_run_input (FlowRunInput): the flow run input to load the input for
        """
        instance = cls(**flow_run_input.decoded_value)
        instance._metadata = RunInputMetadata(
            key=flow_run_input.key,
            sender=flow_run_input.sender,
            receiver=flow_run_input.flow_run_id,
        )
        return instance

    @classmethod
    def with_initial_data(
        cls: Type[R], description: Optional[str] = None, **kwargs: Any
    ) -> Type[R]:
        """
        Create a new `RunInput` subclass with the given initial data as field
        defaults.

        Args:
            - description (str, optional): a description to show when resuming
                a flow run that requires input
            - kwargs (Any): the initial data to populate the subclass
        """
        fields = {}
        for key, value in kwargs.items():
            fields[key] = (type(value), value)
        model = pydantic.create_model(cls.__name__, **fields, __base__=cls)

        if description is not None:
            model._description = description

        return model

    @sync_compatible
    async def respond(
        self,
        run_input: "RunInput",
        sender: Optional[str] = None,
        key_prefix: Optional[str] = None,
    ):
        flow_run_id = None
        if self.metadata.sender and self.metadata.sender.startswith("prefect.flow-run"):
            _, _, id = self.metadata.sender.rpartition(".")
            flow_run_id = UUID(id)

        if not flow_run_id:
            raise RuntimeError(
                "Cannot respond to an input that was not sent by a flow run."
            )

        await _send_input(
            flow_run_id=flow_run_id,
            run_input=run_input,
            sender=sender,
            key_prefix=key_prefix,
        )

    @sync_compatible
    async def send_to(
        self,
        flow_run_id: UUID,
        sender: Optional[str] = None,
        key_prefix: Optional[str] = None,
    ):
        await _send_input(
            flow_run_id=flow_run_id,
            run_input=self,
            sender=sender,
            key_prefix=key_prefix,
        )

    @classmethod
    def receive(
        cls,
        timeout: Optional[float] = 3600,
        poll_interval: float = 10,
        raise_timeout_error: bool = False,
        exclude_keys: Optional[Set[str]] = None,
        key_prefix: Optional[str] = None,
        flow_run_id: Optional[UUID] = None,
    ):
        if key_prefix is None:
            key_prefix = f"{cls.__name__.lower()}-auto"

        return GetInputHandler(
            run_input_cls=cls,
            key_prefix=key_prefix,
            timeout=timeout,
            poll_interval=poll_interval,
            raise_timeout_error=raise_timeout_error,
            exclude_keys=exclude_keys,
            flow_run_id=flow_run_id,
        )

    @classmethod
    def subclass_from_base_model_type(
        cls, model_cls: Type[pydantic.BaseModel]
    ) -> Type["RunInput"]:
        """
        Create a new `RunInput` subclass from the given `pydantic.BaseModel`
        subclass.

        Args:
            - model_cls (pydantic.BaseModel subclass): the class from which
                to create the new `RunInput` subclass
        """
        return type(f"{model_cls.__name__}RunInput", (RunInput, model_cls), {})  # type: ignore


class AutomaticRunInput(RunInput, Generic[T]):
    value: T

    @classmethod
    @sync_compatible
    async def load(cls, keyset: Keyset, flow_run_id: Optional[UUID] = None) -> T:
        """
        Load the run input response from the given key.

        Args:
            - keyset (Keyset): the keyset to load the input for
            - flow_run_id (UUID, optional): the flow run ID to load the input for
        """
        instance = await super().load(keyset, flow_run_id=flow_run_id)
        return instance.value

    @classmethod
    def subclass_from_type(cls, _type: Type[T]) -> Type["AutomaticRunInput[T]"]:
        """
        Create a new `AutomaticRunInput` subclass from the given type.
        """
        fields = {"value": (_type, ...)}

        # Sending a value to a flow run that relies on an AutomaticRunInput will
        # produce a key prefix that includes the type name. For example, if the
        # value is a list, the key will include "list" as the type. If the user
        # then tries to receive the value with a type annotation like List[int],
        # we need to find the key we saved with "list" as the type (not
        # "List[int]"). Calling __name__.lower() on a type annotation like
        # List[int] produces the string "list", which is what we need.
        if hasattr(_type, "__name__"):
            type_prefix = _type.__name__.lower()
        elif hasattr(_type, "_name"):
            # On Python 3.9 and earlier, type annotation values don't have a
            # __name__ attribute, but they do have a _name.
            type_prefix = _type._name.lower()
        else:
            # If we can't identify a type name that we can use as a key
            # prefix that will match an input, we'll have to use
            # "AutomaticRunInput" as the generic name. This will match all
            # automatic inputs sent to the flow run, rather than a specific
            # type.
            type_prefix = ""
        class_name = f"{type_prefix}AutomaticRunInput"

        new_cls: Type["AutomaticRunInput"] = pydantic.create_model(
            class_name, **fields, __base__=AutomaticRunInput
        )
        return new_cls

    @classmethod
    def receive(cls, *args, **kwargs):
        if kwargs.get("key_prefix") is None:
            kwargs["key_prefix"] = f"{cls.__name__.lower()}-auto"

        return GetAutomaticInputHandler(run_input_cls=cls, *args, **kwargs)


def run_input_subclass_from_type(
    _type: Union[Type[R], Type[T], pydantic.BaseModel],
) -> Union[Type[AutomaticRunInput[T]], Type[R]]:
    """
    Create a new `RunInput` subclass from the given type.
    """
    try:
        if issubclass(_type, RunInput):
            return cast(Type[R], _type)
        elif issubclass(_type, pydantic.BaseModel):
            return cast(Type[R], RunInput.subclass_from_base_model_type(_type))
    except TypeError:
        pass

    # Could be something like a typing._GenericAlias or any other type that
    # isn't a `RunInput` subclass or `pydantic.BaseModel` subclass. Try passing
    # it to AutomaticRunInput to see if we can create a model from it.
    return cast(Type[AutomaticRunInput[T]], AutomaticRunInput.subclass_from_type(_type))


class GetInputHandler(Generic[R]):
    def __init__(
        self,
        run_input_cls: Type[R],
        key_prefix: str,
        timeout: Optional[float] = 3600,
        poll_interval: float = 10,
        raise_timeout_error: bool = False,
        exclude_keys: Optional[Set[str]] = None,
        flow_run_id: Optional[UUID] = None,
    ):
        self.run_input_cls = run_input_cls
        self.key_prefix = key_prefix
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.exclude_keys = set()
        self.raise_timeout_error = raise_timeout_error
        self.flow_run_id = ensure_flow_run_id(flow_run_id)

        if exclude_keys is not None:
            self.exclude_keys.update(exclude_keys)

    def __iter__(self):
        return self

    def __next__(self) -> R:
        try:
            return self.next()
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopIteration

    def __aiter__(self):
        return self

    async def __anext__(self) -> R:
        try:
            return await self.next()
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopAsyncIteration

    async def filter_for_inputs(self):
        flow_run_inputs = await filter_flow_run_input(
            key_prefix=self.key_prefix,
            limit=1,
            exclude_keys=self.exclude_keys,
            flow_run_id=self.flow_run_id,
        )

        if flow_run_inputs:
            self.exclude_keys.add(*[i.key for i in flow_run_inputs])

        return flow_run_inputs

    def to_instance(self, flow_run_input: "FlowRunInput") -> R:
        return self.run_input_cls.load_from_flow_run_input(flow_run_input)

    @sync_compatible
    async def next(self) -> R:
        flow_run_inputs = await self.filter_for_inputs()
        if flow_run_inputs:
            return self.to_instance(flow_run_inputs[0])

        with anyio.fail_after(self.timeout):
            while True:
                await anyio.sleep(self.poll_interval)
                flow_run_inputs = await self.filter_for_inputs()
                if flow_run_inputs:
                    return self.to_instance(flow_run_inputs[0])


class GetAutomaticInputHandler(GetInputHandler, Generic[T]):
    def __init__(self, *args, **kwargs):
        self.with_metadata = kwargs.pop("with_metadata", False)
        super().__init__(*args, **kwargs)

    def __next__(self) -> T:
        return cast(T, super().__next__())

    async def __anext__(self) -> T:
        return cast(T, await super().__anext__())

    @sync_compatible
    async def next(self) -> T:
        return cast(T, await super().next())

    def to_instance(self, flow_run_input: "FlowRunInput") -> T:
        run_input = self.run_input_cls.load_from_flow_run_input(flow_run_input)

        if self.with_metadata:
            return run_input
        return run_input.value


async def _send_input(
    flow_run_id: UUID,
    run_input: Any,
    sender: Optional[str] = None,
    key_prefix: Optional[str] = None,
):
    if isinstance(run_input, RunInput):
        _run_input = run_input
    else:
        input_cls = run_input_subclass_from_type(type(run_input))
        _run_input = input_cls(value=run_input)

    if key_prefix is None:
        key_prefix = f"{_run_input.__class__.__name__.lower()}-auto"

    key = f"{key_prefix}-{uuid4()}"

    await create_flow_run_input_from_model(
        key=key, flow_run_id=flow_run_id, model_instance=_run_input, sender=sender
    )


@sync_compatible
async def send_input(
    run_input: Any,
    flow_run_id: UUID,
    sender: Optional[str] = None,
    key_prefix: Optional[str] = None,
):
    await _send_input(
        flow_run_id=flow_run_id,
        run_input=run_input,
        sender=sender,
        key_prefix=key_prefix,
    )


@overload
def receive_input(
    input_type: Type[R],
    timeout: Optional[float] = 3600,
    poll_interval: float = 10,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[Set[str]] = None,
    key_prefix: Optional[str] = None,
    flow_run_id: Optional[UUID] = None,
    with_metadata: bool = False,
) -> GetInputHandler[R]:
    ...


@overload
def receive_input(
    input_type: Type[T],
    timeout: Optional[float] = 3600,
    poll_interval: float = 10,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[Set[str]] = None,
    key_prefix: Optional[str] = None,
    flow_run_id: Optional[UUID] = None,
    with_metadata: bool = False,
) -> GetAutomaticInputHandler[T]:
    ...


def receive_input(
    input_type: Union[Type[R], Type[T]],
    timeout: Optional[float] = 3600,
    poll_interval: float = 10,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[Set[str]] = None,
    key_prefix: Optional[str] = None,
    flow_run_id: Optional[UUID] = None,
    with_metadata: bool = False,
) -> Union[GetAutomaticInputHandler[T], GetInputHandler[R]]:
    input_cls = run_input_subclass_from_type(input_type)

    if issubclass(input_cls, AutomaticRunInput):
        return input_cls.receive(
            timeout=timeout,
            poll_interval=poll_interval,
            raise_timeout_error=raise_timeout_error,
            exclude_keys=exclude_keys,
            key_prefix=key_prefix,
            flow_run_id=flow_run_id,
            with_metadata=with_metadata,
        )
    else:
        return input_cls.receive(
            timeout=timeout,
            poll_interval=poll_interval,
            raise_timeout_error=raise_timeout_error,
            exclude_keys=exclude_keys,
            key_prefix=key_prefix,
            flow_run_id=flow_run_id,
        )
