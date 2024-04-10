import typing
from uuid import uuid4

from prefect._internal.pydantic._compat import (
    BaseModel,
    ConfigDict,
    Field,
    FieldInfo,
    PrivateAttr,
    SecretStr,
    ValidationError,
    field_validator,
)

if typing.TYPE_CHECKING:
    from uuid import UUID

    from rich.repr import Result

    from prefect._internal.schemas.fields import DateTimeTZ


class PrefectBaseModel(BaseModel):
    model_config = ConfigDict(
        revalidate_instances="never",
    )

    __prefect_exclude__: typing.ClassVar[typing.Set[str]] = set()

    def reset(self: "typing.Self") -> "typing.Self":
        """
        Resets the fields of the model to their default values.
        """
        return self.model_construct().model_copy(
            deep=True, update=self.model_dump(exclude=self.__prefect_exclude__)
        )

    def reveal_secrets(self: "typing.Self") -> "typing.Self":
        return self.model_copy(
            deep=True,
            update={
                field_name: getattr(self, field_name).get_secret_value()
                for field_name, field in self.model_dump().items()
                if hasattr(field, "get_secret_value")
            },
        )

    def __rich_repr__(self: "typing.Self") -> "Result":
        for name, value in self.model_dump(mode="json").items():
            yield name, value


class IDBaseModel(PrefectBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value.

    The ID is reset on copy() and not included in equality comparisons.
    """

    __prefect_exclude__: typing.ClassVar[typing.Set[str]] = {"id"}

    id: "UUID" = Field(default_factory=uuid4)


class ObjectBaseModel(IDBaseModel):
    """
    A PrefectBaseModel with an auto-generated UUID ID value and created /
    updated timestamps, intended for compatibility with our standard ORM models.

    The ID, created, and updated fields are reset on copy() and not included in
    equality comparisons.
    """

    model_config = ConfigDict(from_attributes=True)

    __prefect_exclude__: typing.ClassVar[typing.Set[str]] = {"created", "updated", "id"}

    class Config:
        orm_mode = True

    created: typing.Optional["DateTimeTZ"] = Field(default=None, repr=False)
    updated: typing.Optional["DateTimeTZ"] = Field(default=None, repr=False)


class ActionBaseModel(PrefectBaseModel):
    model_config = ConfigDict(extra="forbid")


__all__ = [
    "BaseModel",
    "PrefectBaseModel",
    "Field",
    "FieldInfo",
    "PrivateAttr",
    "SecretStr",
    "field_validator",
    "ConfigDict",
    "ValidationError",
]
