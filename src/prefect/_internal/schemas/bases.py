"""
Utilities for creating and working with Prefect REST API schemas.
"""

import datetime
from typing import Any, ClassVar, Optional, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from rich.repr import RichReprResult
from typing_extensions import Self

from prefect._internal.uuid7 import uuid7
from prefect.types._datetime import (
    DateTime,
    human_friendly_diff,
)
from prefect.utilities.generics import validate_list

T = TypeVar("T")


class PrefectBaseModel(BaseModel):
    """A base pydantic.BaseModel for all Prefect schemas and pydantic models.

    As the basis for most Prefect schemas, this base model usually ignores extra
    fields that are passed to it at instantiation. Because adding new fields to
    API payloads is not considered a breaking change, this ensures that any
    Prefect client loading data from a server running a possibly-newer version
    of Prefect will be able to process those new fields gracefully.
    """

    _reset_fields: ClassVar[set[str]] = set()

    model_config: ClassVar[ConfigDict] = ConfigDict(
        ser_json_timedelta="float",
        defer_build=True,
        extra="ignore",
    )

    def __eq__(self, other: Any) -> bool:
        """Equality operator that ignores the resettable fields of the PrefectBaseModel.

        NOTE: this equality operator will only be applied if the PrefectBaseModel is
        the left-hand operand. This is a limitation of Python.
        """
        copy_dict = self.model_dump(exclude=self._reset_fields)
        if isinstance(other, PrefectBaseModel):
            return copy_dict == other.model_dump(exclude=other._reset_fields)
        if isinstance(other, BaseModel):
            return copy_dict == other.model_dump()
        else:
            return copy_dict == other

    @classmethod
    def model_validate_list(
        cls,
        obj: Any,
        *,
        strict: Optional[bool] = None,
        from_attributes: Optional[bool] = None,
        context: Optional[Any] = None,
    ) -> list[Self]:
        return validate_list(cls, obj)

    def __rich_repr__(self) -> RichReprResult:
        # Display all of the fields in the model if they differ from the default value
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)

            # Simplify the display of some common fields
            if field.annotation == UUID and value:
                value = str(value)
            elif (
                isinstance(field.annotation, datetime.datetime)
                and name == "timestamp"
                and value
            ):
                value = value.isoformat()
            elif isinstance(field.annotation, datetime.datetime) and value:
                value = human_friendly_diff(value)

            yield name, value, field.get_default()

    def reset_fields(self: Self) -> Self:
        """
        Reset the fields of the model that are in the `_reset_fields` set.

        Returns:
            PrefectBaseModel: A new instance of the model with the reset fields.
        """
        return self.model_copy(
            update={
                field: type(self)
                .model_fields[field]
                .get_default(call_default_factory=True)
                for field in self._reset_fields
            }
        )


class IDBaseModel(PrefectBaseModel):
    """
    A PrefectBaseModel with a randomly-generated UUID ID value.

    The ID is reset on copy() and not included in equality comparisons.
    """

    _reset_fields: ClassVar[set[str]] = {"id"}
    id: UUID = Field(default_factory=uuid4)


class TimeSeriesBaseModel(IDBaseModel):
    """
    A PrefectBaseModel with a time-oriented UUIDv7 ID value.  Used for models that
    operate like timeseries, such as runs, states, and logs.
    """

    id: UUID = Field(default_factory=uuid7)


class ObjectBaseModel(IDBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value and created /
    updated timestamps, intended for compatibility with our standard ORM models.

    The ID, created, and updated fields are reset on copy() and not included in
    equality comparisons.
    """

    _reset_fields: ClassVar[set[str]] = {"id", "created", "updated"}
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    created: Optional[DateTime] = Field(default=None, repr=False)
    updated: Optional[DateTime] = Field(default=None, repr=False)


class ActionBaseModel(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
