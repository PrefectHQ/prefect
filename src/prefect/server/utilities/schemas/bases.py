import datetime
from abc import ABC, abstractmethod
from functools import partial
from typing import TYPE_CHECKING, Any, ClassVar, Optional, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict
from typing_extensions import Self

from prefect._internal.uuid7 import uuid7
from prefect.types._datetime import DateTime, human_friendly_diff

if TYPE_CHECKING:
    from pydantic.main import IncEx
    from rich.repr import RichReprResult

T = TypeVar("T")
B = TypeVar("B", bound=BaseModel)


def get_class_fields_only(model: type[BaseModel]) -> set[str]:
    """
    Gets all the field names defined on the model class but not any parent classes.
    Any fields that are on the parent but redefined on the subclass are included.
    """
    # the annotations keys fit all of these criteria without further processing
    return set(model.__annotations__)


class PrefectDescriptorBase(ABC):
    """A base class for descriptor objects used with PrefectBaseModel

    Pydantic needs to be told about any kind of non-standard descriptor
    objects used on a model, in order for these not to be treated as a field
    type instead.

    This base class is registered as an ignored type with PrefectBaseModel
    and any classes that inherit from it will also be ignored. This allows
    such descriptors to be used as properties, methods or other bound
    descriptor use cases.

    """

    @abstractmethod
    def __get__(
        self, __instance: Optional[Any], __owner: Optional[type[Any]] = None
    ) -> Any:
        """Base descriptor access.

        The default implementation returns itself when the instance is None,
        and raises an attribute error when the instance is not not None.

        """
        if __instance is not None:
            raise AttributeError
        return self


class PrefectBaseModel(BaseModel):
    """A base pydantic.BaseModel for all Prefect schemas and pydantic models.

    As the basis for most Prefect schemas, this base model ignores extra
    fields that are passed to it at instantiation. Because adding new fields to
    API payloads is not considered a breaking change, this ensures that any
    Prefect client loading data from a server running a possibly-newer version
    of Prefect will be able to process those new fields gracefully.
    """

    _reset_fields: ClassVar[set[str]] = set()

    model_config: ClassVar[ConfigDict] = ConfigDict(
        ser_json_timedelta="float",
        extra="ignore",
        ignored_types=(PrefectDescriptorBase,),
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

    def __rich_repr__(self) -> "RichReprResult":
        # Display all of the fields in the model if they differ from the default value
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)

            # Simplify the display of some common fields
            if isinstance(value, UUID):
                value = str(value)
            elif isinstance(value, datetime.datetime):
                value = (
                    value.isoformat()
                    if name == "timestamp"
                    else human_friendly_diff(value)
                )

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

    def model_dump_for_orm(
        self,
        *,
        include: Optional["IncEx"] = None,
        exclude: Optional["IncEx"] = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> dict[str, Any]:
        """
        Prefect extension to `BaseModel.model_dump`.  Generate a Python dictionary
        representation of the model suitable for passing to SQLAlchemy model
        constructors, `INSERT` statements, etc.  The critical difference here is that
        this method will return any nested BaseModel objects as `BaseModel` instances,
        rather than serialized Python dictionaries.

        Accepts the standard Pydantic `model_dump` arguments, except for `mode` (which
        is always "python"), `round_trip`, and `warnings`.

        Usage docs: https://docs.pydantic.dev/2.6/concepts/serialization/#modelmodel_dump

        Args:
            include: A list of fields to include in the output.
            exclude: A list of fields to exclude from the output.
            by_alias: Whether to use the field's alias in the dictionary key if defined.
            exclude_unset: Whether to exclude fields that have not been explicitly set.
            exclude_defaults: Whether to exclude fields that are set to their default
                value.
            exclude_none: Whether to exclude fields that have a value of `None`.

        Returns:
            A dictionary representation of the model, suitable for passing
            to SQLAlchemy model constructors, INSERT statements, etc.
        """
        # TODO: this could be optimized by excluding any fields that we know we are
        # going to replace because they are `BaseModel` instances.  This would involve
        # understanding which fields would be included or excluded by model_dump so we
        # could instruct Pydantic to exclude them up front.
        deep = self.model_dump(
            mode="python",
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            context={"for_orm": True},
        )
        for k, v in self:
            if k in deep and isinstance(v, BaseModel):
                deep[k] = v
        return deep


def _ensure_fields_required(field_names: list[str], schema: JsonDict) -> None:
    for field_name in field_names:
        if "required" not in schema:
            schema["required"] = []
        if (
            (required := schema.get("required"))
            and isinstance(required, list)
            and field_name not in required
        ):
            required.append(field_name)


class IDBaseModel(PrefectBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value.

    The ID is reset on copy() and not included in equality comparisons.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        json_schema_extra=partial(_ensure_fields_required, ["id"])
    )

    _reset_fields: ClassVar[set[str]] = {"id"}
    id: UUID = Field(default_factory=uuid4)


class TimeSeriesBaseModel(IDBaseModel):
    """
    A PrefectBaseModel with a time-oriented UUIDv7 ID value.  Used for models that
    operate like timeseries, such as runs, states, and logs.
    """

    id: UUID = Field(default_factory=uuid7)


class ORMBaseModel(IDBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value and created /
    updated timestamps, intended for compatibility with our standard ORM models.

    The ID, created, and updated fields are reset on copy() and not included in
    equality comparisons.
    """

    _reset_fields: ClassVar[set[str]] = {"id", "created", "updated"}

    model_config: ClassVar[ConfigDict] = ConfigDict(
        from_attributes=True,
        json_schema_extra=partial(
            _ensure_fields_required, ["id", "created", "updated"]
        ),
    )

    created: Optional[DateTime] = Field(default=None, repr=False)
    updated: Optional[DateTime] = Field(default=None, repr=False)


class ActionBaseModel(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
