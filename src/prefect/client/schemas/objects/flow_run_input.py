from typing import (
    Any,
    Optional,
)
from uuid import UUID

import orjson
from pydantic import (
    Field,
    field_validator,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect._internal.schemas.validators import (
    raise_on_name_alphanumeric_dashes_only,
)


class FlowRunInput(ObjectBaseModel):
    flow_run_id: UUID = Field(description="The flow run ID associated with the input.")
    key: str = Field(description="The key of the input.")
    value: str = Field(description="The value of the input.")
    sender: Optional[str] = Field(default=None, description="The sender of the input.")

    @property
    def decoded_value(self) -> Any:
        """
        Decode the value of the input.

        Returns:
            Any: the decoded value
        """
        return orjson.loads(self.value)

    @field_validator("key", check_fields=False)
    @classmethod
    def validate_name_characters(cls, v):
        raise_on_name_alphanumeric_dashes_only(v)
        return v
