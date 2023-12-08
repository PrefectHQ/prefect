from typing import Any, Optional, Type
from uuid import UUID

import pydantic

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.input.actions import create_flow_run_input, read_flow_run_input
from prefect.utilities.asyncutils import sync_compatible

if HAS_PYDANTIC_V2:
    from prefect._internal.pydantic.v2_schema import create_v2_schema


class RunInput(pydantic.BaseModel):
    class Config:
        extra = "forbid"

    title: str = "Run is asking for input"
    description: Optional[str] = None

    @classmethod
    @sync_compatible
    async def save(
        cls, key: str, key_suffix: str = "schema", flow_run_id: Optional[UUID] = None
    ):
        """
        Save the run input response to the given key.

        Args:
            - key (str): the flow run input key
            - key_suffix (str): the suffix to append to the key, defaults to
                "-schema"
        """

        if HAS_PYDANTIC_V2:
            schema = create_v2_schema(cls.__name__, model_base=cls)
        else:
            schema = cls.schema(by_alias=True)

        key = f"{key}-{key_suffix}"
        return await create_flow_run_input(
            key=key, value=schema, flow_run_id=flow_run_id
        )

    @classmethod
    @sync_compatible
    async def load(
        cls, key: str, key_suffix: str = "response", flow_run_id: Optional[UUID] = None
    ):
        """
        Load the run input response from the given key.

        Args:
            - key (str): the flow run input key
            - key_suffix (str): the suffix to append to the key, defaults to
                "-response"
        """
        key = f"{key}-{key_suffix}"
        value = await read_flow_run_input(key=key, flow_run_id=flow_run_id)
        return cls(**value)

    @classmethod
    def with_initial_data(cls, **kwargs: Any) -> Type["RunInput"]:
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
