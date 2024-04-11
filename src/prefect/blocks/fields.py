import json
from typing import Any, Callable, Dict, Generator, Generic, TypeVar

from pydantic_core import SchemaValidator

SecretType = TypeVar("SecretType")


class _SecretBase(Generic[SecretType]):
    def __init__(self, secret_value: SecretType) -> None:
        self._secret_value: SecretType = secret_value

    def get_secret_value(self) -> SecretType:
        """Get the secret value.

        Returns:
            The secret value.
        """
        return self._secret_value

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, self.__class__)
            and self.get_secret_value() == other.get_secret_value()
        )

    def __hash__(self) -> int:
        return hash(self.get_secret_value())

    def __str__(self) -> str:
        return str(self._display())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._display()!r})"

    def _display(self) -> str | bytes:
        raise NotImplementedError


class SecretDict(_SecretBase[Dict[str, Any]], Dict[str, Any]):
    def __init__(self, secret_value: Dict[str, Any]) -> None:
        self._secret_value = secret_value
        self.update(**secret_value)

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(type="object")

    @classmethod
    def __get_validators__(cls) -> Generator[Callable[..., Any], None, None]:
        yield cls.validate

    @classmethod
    def validate(cls, value: Any) -> "SecretDict":
        value = SchemaValidator({"type": "dict"}).validate_python(value)
        return cls(value)

    def get_secret_value(self) -> Dict[str, Any]:
        return self._secret_value

    def _display(self) -> str | bytes:
        return (
            json.dumps({key: "**********" for key in self.get_secret_value().keys()})
            if self.get_secret_value()
            else ""
        )
