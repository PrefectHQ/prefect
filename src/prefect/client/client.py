import warnings
from typing import Any

from prefect.backend.client import Client as Client_


class Client(Client_):
    def __new__(cls, *args: Any, **kwargs: Any) -> "Client":
        warnings.warn(
            "prefect.client.client.Client has been moved to "
            "`prefect.backend.client.Client`, please update your imports",
            stacklevel=2,
        )
        return super().__new__(cls)
