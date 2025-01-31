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
from prefect import flow
from prefect.logging import get_run_logger
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
from prefect import flow
from prefect.logging import get_run_logger
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

from __future__ import annotations

import inspect
from inspect import isclass
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Coroutine,
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
from pydantic import ConfigDict
from typing_extensions import Self

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

from prefect._internal.pydantic.v2_schema import create_v2_schema, is_v2_model

R = TypeVar("R", bound="RunInput")
T = TypeVar("T", bound="object")

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

    state_name = state.name or ""
    base_key = f"{state_name.lower()}-{str(state.state_details.pause_key)}"
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
    sender: Optional[str] = None
    receiver: UUID


class BaseRunInput(pydantic.BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

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

        if is_v2_model(cls):
            schema = create_v2_schema(cls.__name__, model_base=cls)
        else:
            schema = cls.model_json_schema(by_alias=True)

        coro = create_flow_run_input(
            key=keyset["schema"], value=schema, flow_run_id=flow_run_id
        )
        if TYPE_CHECKING:
            assert inspect.iscoroutine(coro)
        await coro

        description = cls._description if isinstance(cls._description, str) else None
        if description:
            coro = create_flow_run_input(
                key=keyset["description"],
                value=description,
                flow_run_id=flow_run_id,
            )
            if TYPE_CHECKING:
                assert inspect.iscoroutine(coro)
            await coro

    @classmethod
    @sync_compatible
    async def load(cls, keyset: Keyset, flow_run_id: Optional[UUID] = None) -> Self:
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
    def load_from_flow_run_input(cls, flow_run_input: "FlowRunInput") -> Self:
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
        fields: Dict[str, Any] = {}
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


class RunInput(BaseRunInput):
    @classmethod
    def receive(
        cls,
        timeout: Optional[float] = 3600,
        poll_interval: float = 10,
        raise_timeout_error: bool = False,
        exclude_keys: Optional[Set[str]] = None,
        key_prefix: Optional[str] = None,
        flow_run_id: Optional[UUID] = None,
    ) -> GetInputHandler[Self]:
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


class AutomaticRunInput(BaseRunInput, Generic[T]):
    value: T

    @classmethod
    @sync_compatible
    async def load(cls, keyset: Keyset, flow_run_id: Optional[UUID] = None) -> Self:
        """
        Load the run input response from the given key.

        Args:
            - keyset (Keyset): the keyset to load the input for
            - flow_run_id (UUID, optional): the flow run ID to load the input for
        """
        instance_coro = super().load(keyset, flow_run_id=flow_run_id)
        if TYPE_CHECKING:
            assert inspect.iscoroutine(instance_coro)
        instance = await instance_coro
        return instance.value

    @classmethod
    def subclass_from_type(cls, _type: Type[T]) -> Type["AutomaticRunInput[T]"]:
        """
        Create a new `AutomaticRunInput` subclass from the given type.

        This method uses the type's name as a key prefix to identify related
        flow run inputs. This helps in ensuring that values saved under a type
        (like List[int]) are retrievable under the generic type name (like "list").
        """
        fields: Dict[str, Any] = {"value": (_type, ...)}

        # Explanation for using getattr for type name extraction:
        # - "__name__": This is the usual attribute for getting the name of
        #   most types.
        # - "_name": Used as a fallback, some type annotations in Python 3.9
        #   and earlier might only have this attribute instead of __name__.
        # - If neither is available, defaults to an empty string to prevent
        #   errors, but typically we should find at least one valid name
        #   attribute. This will match all automatic inputs sent to the flow
        #   run, rather than a specific type.
        #
        # This approach ensures compatibility across Python versions and
        # handles various edge cases in type annotations.

        type_prefix: str = getattr(
            _type, "__name__", getattr(_type, "_name", "")
        ).lower()

        class_name = f"{type_prefix}AutomaticRunInput"

        # Creating a new Pydantic model class dynamically with the name based
        # on the type prefix.
        new_cls: Type["AutomaticRunInput[T]"] = pydantic.create_model(
            class_name, **fields, __base__=AutomaticRunInput
        )
        return new_cls

    @classmethod
    def receive(
        cls,
        timeout: Optional[float] = 3600,
        poll_interval: float = 10,
        raise_timeout_error: bool = False,
        exclude_keys: Optional[Set[str]] = None,
        key_prefix: Optional[str] = None,
        flow_run_id: Optional[UUID] = None,
        with_metadata: bool = False,
    ) -> GetAutomaticInputHandler[T]:
        key_prefix = key_prefix or f"{cls.__name__.lower()}-auto"

        return GetAutomaticInputHandler(
            run_input_cls=cls,
            key_prefix=key_prefix,
            timeout=timeout,
            poll_interval=poll_interval,
            raise_timeout_error=raise_timeout_error,
            exclude_keys=exclude_keys,
            flow_run_id=flow_run_id,
            with_metadata=with_metadata,
        )


def run_input_subclass_from_type(
    _type: Union[Type[R], Type[T], pydantic.BaseModel],
) -> Union[Type[AutomaticRunInput[T]], Type[R]]:
    """
    Create a new `RunInput` subclass from the given type.
    """
    if isclass(_type):
        if issubclass(_type, RunInput):
            return cast(Type[R], _type)
        elif issubclass(_type, pydantic.BaseModel):
            return cast(Type[R], RunInput.subclass_from_base_model_type(_type))

    # Could be something like a typing._GenericAlias or any other type that
    # isn't a `RunInput` subclass or `pydantic.BaseModel` subclass. Try passing
    # it to AutomaticRunInput to see if we can create a model from it.
    return cast(
        Type[AutomaticRunInput[T]],
        AutomaticRunInput.subclass_from_type(cast(Type[T], _type)),
    )


class GetInputHandler(Generic[R]):
    def __init__(
        self,
        run_input_cls: Type[R],
        key_prefix: str,
        timeout: float | None = 3600,
        poll_interval: float = 10,
        raise_timeout_error: bool = False,
        exclude_keys: Optional[Set[str]] = None,
        flow_run_id: Optional[UUID] = None,
    ):
        self.run_input_cls: Type[R] = run_input_cls
        self.key_prefix: str = key_prefix
        self.timeout: float | None = timeout
        self.poll_interval: float = poll_interval
        self.exclude_keys: set[str] = set()
        self.raise_timeout_error: bool = raise_timeout_error
        self.flow_run_id: UUID = ensure_flow_run_id(flow_run_id)

        if exclude_keys is not None:
            self.exclude_keys.update(exclude_keys)

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> R:
        try:
            return cast(R, self.next())
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopIteration

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> R:
        try:
            coro = self.next()
            if TYPE_CHECKING:
                assert inspect.iscoroutine(coro)
            return await coro
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopAsyncIteration

    async def filter_for_inputs(self) -> list["FlowRunInput"]:
        flow_run_inputs_coro = filter_flow_run_input(
            key_prefix=self.key_prefix,
            limit=1,
            exclude_keys=self.exclude_keys,
            flow_run_id=self.flow_run_id,
        )
        if TYPE_CHECKING:
            assert inspect.iscoroutine(flow_run_inputs_coro)

        flow_run_inputs = await flow_run_inputs_coro

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


class GetAutomaticInputHandler(Generic[T]):
    def __init__(
        self,
        run_input_cls: Type[AutomaticRunInput[T]],
        key_prefix: str,
        timeout: float | None = 3600,
        poll_interval: float = 10,
        raise_timeout_error: bool = False,
        exclude_keys: Optional[Set[str]] = None,
        flow_run_id: Optional[UUID] = None,
        with_metadata: bool = False,
    ):
        self.run_input_cls: Type[AutomaticRunInput[T]] = run_input_cls
        self.key_prefix: str = key_prefix
        self.timeout: float | None = timeout
        self.poll_interval: float = poll_interval
        self.exclude_keys: set[str] = set()
        self.raise_timeout_error: bool = raise_timeout_error
        self.flow_run_id: UUID = ensure_flow_run_id(flow_run_id)
        self.with_metadata = with_metadata

        if exclude_keys is not None:
            self.exclude_keys.update(exclude_keys)

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> T | AutomaticRunInput[T]:
        try:
            not_coro = self.next()
            if TYPE_CHECKING:
                assert not isinstance(not_coro, Coroutine)
            return not_coro
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopIteration

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Union[T, AutomaticRunInput[T]]:
        try:
            coro = self.next()
            if TYPE_CHECKING:
                assert inspect.iscoroutine(coro)
            return cast(Union[T, AutomaticRunInput[T]], await coro)
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopAsyncIteration

    async def filter_for_inputs(self) -> list["FlowRunInput"]:
        flow_run_inputs_coro = filter_flow_run_input(
            key_prefix=self.key_prefix,
            limit=1,
            exclude_keys=self.exclude_keys,
            flow_run_id=self.flow_run_id,
        )
        if TYPE_CHECKING:
            assert inspect.iscoroutine(flow_run_inputs_coro)

        flow_run_inputs = await flow_run_inputs_coro

        if flow_run_inputs:
            self.exclude_keys.add(*[i.key for i in flow_run_inputs])

        return flow_run_inputs

    @sync_compatible
    async def next(self) -> Union[T, AutomaticRunInput[T]]:
        flow_run_inputs = await self.filter_for_inputs()
        if flow_run_inputs:
            return self.to_instance(flow_run_inputs[0])

        with anyio.fail_after(self.timeout):
            while True:
                await anyio.sleep(self.poll_interval)
                flow_run_inputs = await self.filter_for_inputs()
                if flow_run_inputs:
                    return self.to_instance(flow_run_inputs[0])

    def to_instance(
        self, flow_run_input: "FlowRunInput"
    ) -> Union[T, AutomaticRunInput[T]]:
        run_input = self.run_input_cls.load_from_flow_run_input(flow_run_input)

        if self.with_metadata:
            return run_input
        return run_input.value


async def _send_input(
    flow_run_id: UUID,
    run_input: RunInput | pydantic.BaseModel,
    sender: Optional[str] = None,
    key_prefix: Optional[str] = None,
):
    _run_input: Union[RunInput, AutomaticRunInput[Any]]
    if isinstance(run_input, RunInput):
        _run_input = run_input
    else:
        input_cls: Type[AutomaticRunInput[Any]] = run_input_subclass_from_type(
            type(run_input)
        )
        _run_input = input_cls(value=run_input)

    if key_prefix is None:
        key_prefix = f"{_run_input.__class__.__name__.lower()}-auto"

    key = f"{key_prefix}-{uuid4()}"

    coro = create_flow_run_input_from_model(
        key=key, flow_run_id=flow_run_id, model_instance=_run_input, sender=sender
    )
    if TYPE_CHECKING:
        assert inspect.iscoroutine(coro)

    await coro


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
def receive_input(  # type: ignore[overload-overlap]
    input_type: Union[Type[R], pydantic.BaseModel],
    timeout: Optional[float] = 3600,
    poll_interval: float = 10,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[Set[str]] = None,
    key_prefix: Optional[str] = None,
    flow_run_id: Optional[UUID] = None,
    with_metadata: bool = False,
) -> GetInputHandler[R]: ...


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
) -> GetAutomaticInputHandler[T]: ...


def receive_input(
    input_type: Union[Type[R], Type[T], pydantic.BaseModel],
    timeout: Optional[float] = 3600,
    poll_interval: float = 10,
    raise_timeout_error: bool = False,
    exclude_keys: Optional[Set[str]] = None,
    key_prefix: Optional[str] = None,
    flow_run_id: Optional[UUID] = None,
    with_metadata: bool = False,
) -> Union[GetAutomaticInputHandler[T], GetInputHandler[R]]:
    # The typing in this module is a bit complex, and at this point `mypy`
    # thinks that `run_input_subclass_from_type` accepts a `Type[Never]` but
    # the signature is the same as here:
    #   Union[Type[R], Type[T], pydantic.BaseModel],
    # Seems like a possible mypy bug, so we'll ignore the type check here.
    input_cls: Union[Type[AutomaticRunInput[T]], Type[R]] = (
        run_input_subclass_from_type(input_type)
    )  # type: ignore[arg-type]

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
