from abc import ABC, abstractmethod
from typing import NoReturn


class Service(ABC):
    @abstractmethod
    async def start(self) -> NoReturn:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...
