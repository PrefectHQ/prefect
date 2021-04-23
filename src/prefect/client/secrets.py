import warnings
from typing import Any

from prefect.backend.secrets import Secret as Secret_


class Secret(Secret_):
    def __new__(cls, *args: Any, **kwargs: Any) -> "Secret":
        warnings.warn(
            "prefect.client.secrets.Secret has been moved to "
            "`prefect.backend.secret.Secret`, please update your imports",
            stacklevel=2,
        )
        return super().__new__(cls)
