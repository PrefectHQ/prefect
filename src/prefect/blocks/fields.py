from typing import TYPE_CHECKING, Any, Dict

from pydantic import SecretField
from pydantic.utils import update_not_none
from pydantic.validators import dict_validator

if TYPE_CHECKING:
    from pydantic.typing import CallableGenerator


class SecretDict(SecretField):
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        update_not_none(
            field_schema,
            type="object",
        )

    @classmethod
    def __get_validators__(cls) -> "CallableGenerator":
        yield cls.validate

    @classmethod
    def validate(cls, value: Any) -> "SecretDict":
        if isinstance(value, cls):
            return value
        value = dict_validator(value)
        return cls(value)

    def __init__(self, value: Dict[str, Any]):
        self._secret_value = value

    def __str__(self) -> str:
        return (
            str({key: "**********" for key in self.get_secret_value().keys()})
            if self.get_secret_value()
            else ""
        )

    def __repr__(self) -> str:
        return f"SecretDict('{self}')"

    def get_secret_value(self) -> Dict[str, Any]:
        return self._secret_value

    def dict(self) -> Dict:
        return {key: "**********" for key in self.get_secret_value().keys()}
