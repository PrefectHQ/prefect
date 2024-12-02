import datetime
import os
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Optional,
    Set,
    Type,
    TypeVar,
)
from uuid import UUID, uuid4

import pendulum
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import Self

if TYPE_CHECKING:
    from pydantic.main import IncEx

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

    _reset_fields: ClassVar[Set[str]] = set()

    model_config = ConfigDict(
        ser_json_timedelta="float",
        extra=(
            "ignore"
            if os.getenv("PREFECT_TEST_MODE", "0").lower() not in ["true", "1"]
            and os.getenv("PREFECT_TESTING_TEST_MODE", "0").lower() not in ["true", "1"]
            else "forbid"
        ),
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
                field: self.model_fields[field].get_default(call_default_factory=True)
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
    ) -> Dict[str, Any]:
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


class IDBaseModel(PrefectBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value.

    The ID is reset on copy() and not included in equality comparisons.
    """

    _reset_fields: ClassVar[Set[str]] = {"id"}
    id: UUID = Field(default_factory=uuid4)


class ORMBaseModel(IDBaseModel):
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
