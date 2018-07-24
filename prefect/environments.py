from typing import Any, Iterable

from prefect.utilities.json import ObjectAttributesCodec, Serializable


class Secret(Serializable):
    _json_codec = ObjectAttributesCodec

    def __init__(self, name: str) -> None:
        self.name = name
        self._value = None

    @property
    def value(self) -> Any:
        """Get the secret's value"""
        return self._value

    @value.setter
    def value(self, value: Any) -> None:
        """Set the secret's value"""
        self._value = value


class Environment(Serializable):
    """
    Base class for Environments
    """

    _json_codec = ObjectAttributesCodec

    def __init__(self, secrets: Iterable[Secret] = None) -> None:
        self.secrets = secrets or []

    def build(self) -> None:
        """Build the environment"""
        raise NotImplementedError()


class Container(Environment):
    """
    Container class used to represent a Docker container
    """

    def __init__(
        self,
        image: str,
        name: str = None,
        python_dependencies: list = None,
        secrets: Iterable[Secret] = None,
    ) -> None:
        if name is None:
            name = image

        self.image = image
        self.name = name

        self._python_dependencies = python_dependencies

        super().__init__(secrets=secrets)

    def build(self) -> str:
        """Build the Docker container"""
        return "bleh"

    @property
    def python_dependencies(self) -> list:
        """Get the specified Python dependencies"""
        return self._python_dependencies