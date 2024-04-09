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


class PrefectBaseModel(BaseModel):
    model_config = ConfigDict()
    __prefect_exclude__: typing.ClassVar[typing.Set[str]] = set()

    def reset(self: "typing.Self") -> "typing.Self":
        """
        Resets the fields of the model to their default values.
        """
        return self.model_construct().model_copy(
            deep=True, update=self.model_dump(exclude=self.__prefect_exclude__)
        )


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
