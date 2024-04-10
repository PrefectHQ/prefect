import typing

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
    from rich.repr import Result


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
