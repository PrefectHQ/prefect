"""
Utilities for creating and working with Prefect REST API schemas.
"""

import datetime
import os
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional, Set, TypeVar
from uuid import UUID, uuid4

import pendulum
from pydantic import BaseModel, ConfigDict, Field
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import Self

from prefect.utilities.pydantic import default_secret_encoder

if TYPE_CHECKING:
    from pydantic.main import IncEx

T = TypeVar("T")


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

    _reset_fields: ClassVar[Set[str]] = set()

    model_config = ConfigDict(
        extra=(
            "ignore"
            if os.getenv("PREFECT_TEST_MODE", "0").lower() not in ["true", "1"]
            else "forbid"
        )
    )

    def __eq__(self, other: Any) -> bool:
        """Equaltiy operator that ignores the resettable fields of the PrefectBaseModel.

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

    def reset_fields(self: Self) -> Self:
        """
        Reset the fields of the model that are in the `_reset_fields` set.

        Returns:
            PrefectBaseModel: A new instance of the model with the reset fields.
        """
        return self.model_copy(
            update={
                field: self.model_fields[field].get_default()
                for field in self._reset_fields
            }
        )

    def model_dump_with_secrets(
        self,
        *,
        unmask_secrets: bool = True,
        include: "IncEx" = None,
        exclude: "IncEx" = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> Dict[str, Any]:
        """
        Prefect extension to `BaseModel.model_dump`.  Generate a Python dictionary
        representation of the model, calling `.get_secret_value()` on any fields that
        have that method defined.

        `unmask_secrets` is left as an escape for when the caller of this method wants to override
        the default behavior of including secrets in the output (as currently enabled in the client).

        Accepts the standard Pydantic `model_dump` arguments, except for `mode` (which
        is always "json"), `round_trip`, and `warnings` (the latter two are not supported).

        Usage docs: https://docs.pydantic.dev/2.6/concepts/serialization/#modelmodel_dump

        Args:
            unmask_secrets: Whether to include secrets in the output.
            include: A list of fields to include in the output.
            exclude: A list of fields to exclude from the output.
            by_alias: Whether to use the field's alias in the dictionary key if defined.
            exclude_unset: Whether to exclude fields that have not been explicitly set.
            exclude_defaults: Whether to exclude fields that are set to their default
                value.
            exclude_none: Whether to exclude fields that have a value of `None`.
        """
        if not unmask_secrets:
            return self.model_dump(
                mode="json",
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            )

        return {
            field_name: default_secret_encoder(field_value)
            for field_name, field_value in self.model_dump(
                mode="python",
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            ).items()
        }


class IDBaseModel(PrefectBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value.

    The ID is reset on copy() and not included in equality comparisons.
    """

    _reset_fields: ClassVar[Set[str]] = {"id"}
    id: UUID = Field(default_factory=uuid4)


class ObjectBaseModel(IDBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value and created /
    updated timestamps, intended for compatibility with our standard ORM models.

    The ID, created, and updated fields are reset on copy() and not included in
    equality comparisons.
    """

    _reset_fields: ClassVar[Set[str]] = {"id", "created", "updated"}
    model_config = ConfigDict(from_attributes=True)

    created: Optional[DateTime] = Field(default=None, repr=False)
    updated: Optional[DateTime] = Field(default=None, repr=False)


class ActionBaseModel(PrefectBaseModel):
    model_config: ConfigDict = ConfigDict(extra="forbid")
