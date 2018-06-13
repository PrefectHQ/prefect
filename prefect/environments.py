from typing import Iterable, Any

from prefect.utilities.json import ObjectAttributesCodec, Serializable


class Secret(Serializable):
    _json_codec = ObjectAttributesCodec

    def __init__(self, name: str) -> None:
        self.name = name
        self._value = None

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, value: Any) -> None:
        self._value = value


class Environment(Serializable):
    """
    Base class for Environments
    """

    _json_codec = ObjectAttributesCodec

    def __init__(self, secrets: Iterable[Secret] = None) -> None:
        self.secrets = secrets or ()


class Container(Environment):
    def __init__(
        self, image: str, name: str = None, secrets: Iterable[Secret] = None
    ) -> None:
        if name is None:
            name = image

        self.image = image
        self.name = name

        super().__init__(secrets=secrets)
