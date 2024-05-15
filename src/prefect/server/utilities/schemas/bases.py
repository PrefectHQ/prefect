import datetime
import os
from typing import Any, Optional, Set, Type, TypeVar
from uuid import UUID, uuid4

import pendulum
from pydantic import BaseModel, ConfigDict, Field

from prefect.server.utilities.schemas.fields import DateTime

T = TypeVar("T")
B = TypeVar("B", bound=BaseModel)


def get_class_fields_only(model: Type[BaseModel]) -> set:
    """
    Gets all the field names defined on the model class but not any parent classes.
    Any fields that are on the parent but redefined on the subclass are included.
    """
    subclass_class_fields = set(model.__annotations__.keys())
    parent_class_fields = set()

    for base in model.__class__.__bases__:
        if issubclass(base, BaseModel):
            parent_class_fields.update(base.__annotations__.keys())

    return (subclass_class_fields - parent_class_fields) | (
        subclass_class_fields & parent_class_fields
    )


class PrefectBaseModel(BaseModel):
    """A base pydantic.BaseModel for all Prefect schemas and pydantic models.

    As the basis for most Prefect schemas, this base model usually ignores extra
    fields that are passed to it at instantiation. Because adding new fields to
    API payloads is not considered a breaking change, this ensures that any
    Prefect client loading data from a server running a possibly-newer version
    of Prefect will be able to process those new fields gracefully. However,
    when PREFECT_TEST_MODE is on, extra fields are forbidden in order to catch
    subtle unintentional testing errors.
    """

    model_config: ConfigDict = ConfigDict(
        extra=(
            "ignore" if os.getenv("PREFECT_TEST_MODE", "0").lower() != "1" else "forbid"
        )
    )

    def _reset_fields(self) -> Set[str]:
        """A set of field names that are reset when the PrefectBaseModel is copied.
        These fields are also disregarded for equality comparisons.
        """
        return set()

    def __eq__(self, other: Any) -> bool:
        """Equaltiy operator that ignores the resettable fields of the PrefectBaseModel.

        NOTE: this equality operator will only be applied if the PrefectBaseModel is
        the left-hand operand. This is a limitation of Python.
        """
        copy_dict = self.model_dump(exclude=self._reset_fields())
        if isinstance(other, PrefectBaseModel):
            return copy_dict == other.model_dump(exclude=other._reset_fields())
        if isinstance(other, BaseModel):
            return copy_dict == other.model_dump()
        else:
            return copy_dict == other

    def __rich_repr__(self):
        # Display all of the fields in the model if they differ from the default value
        for name, field in self.model_fields.items():
            value = getattr(self, name)

            # Simplify the display of some common fields
            if field.annotation == UUID and value:
                value = str(value)
            elif (
                isinstance(field.annotation, datetime.datetime)
                and name == "timestamp"
                and value
            ):
                value = pendulum.instance(value).isoformat()
            elif isinstance(field.annotation, datetime.datetime) and value:
                value = pendulum.instance(value).diff_for_humans()

            yield name, value, field.get_default()


class IDBaseModel(PrefectBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value.

    The ID is reset on copy() and not included in equality comparisons.
    """

    id: UUID = Field(default_factory=uuid4)

    def _reset_fields(self) -> Set[str]:
        return super()._reset_fields().union({"id"})


class ORMBaseModel(IDBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value and created /
    updated timestamps, intended for compatibility with our standard ORM models.

    The ID, created, and updated fields are reset on copy() and not included in
    equality comparisons.
    """

    model_config = ConfigDict(from_attributes=True)

    created: Optional[DateTime] = Field(default=None, repr=False)
    updated: Optional[DateTime] = Field(default=None, repr=False)

    def _reset_fields(self) -> Set[str]:
        return super()._reset_fields().union({"created", "updated"})


class ActionBaseModel(PrefectBaseModel):
    model_config: ConfigDict = ConfigDict(extra="forbid")
