from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, Type, TypeVar, Union
from uuid import UUID

import pydantic

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.input.actions import create_flow_run_input, read_flow_run_input
from prefect.utilities.asyncutils import sync_compatible

if TYPE_CHECKING:
    from prefect.states import State


if HAS_PYDANTIC_V2:
    from prefect._internal.pydantic.v2_schema import create_v2_schema


T = TypeVar("T", bound="RunInput")
KeysetNames = Union[Literal["response"], Literal["schema"]]
Keyset = Dict[KeysetNames, str]


def keyset_from_paused_state(state: "State") -> Keyset:
    """
    Get the keyset for the given Paused state.

    Args:
        - state (State): the state to get the keyset for
    """

    if not state.is_paused():
        raise RuntimeError(f"{state.type.value!r} is unsupported.")

    return keyset_from_base_key(
        f"{state.name.lower()}-{str(state.state_details.pause_key)}"
    )


def keyset_from_base_key(base_key: str) -> Keyset:
    """
    Get the keyset for the given base key.

    Args:
        - base_key (str): the base key to get the keyset for

    Returns:
        - Dict[str, str]: the keyset
    """
    return {
        "response": f"{base_key}-response",
        "schema": f"{base_key}-schema",
    }


class RunInput(pydantic.BaseModel):
    class Config:
        extra = "forbid"

    title: str = "Run is asking for input"
    description: Optional[str] = None

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

    @classmethod
    @sync_compatible
    async def load(cls, keyset: Keyset, flow_run_id: Optional[UUID] = None):
        """
        Load the run input response from the given key.

        Args:
            - keyset (Keyset): the keyset to load the input for
            - flow_run_id (UUID, optional): the flow run ID to load the input for
        """
        value = await read_flow_run_input(keyset["response"], flow_run_id=flow_run_id)
        return cls(**value)

    @classmethod
    def with_initial_data(cls: Type[T], **kwargs: Any) -> Type[T]:
        """
        Create a new `RunInput` subclass with the given initial data as field
        defaults.

        Args:
            - kwargs (Any): the initial data
        """
        fields = {}
        for key, value in kwargs.items():
            fields[key] = (type(value), value)
        return pydantic.create_model(cls.__name__, **fields, __base__=cls)
