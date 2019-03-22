import json
import os
from typing import Optional, Any

import prefect
from prefect.client.client import Client
from prefect.utilities.collections import as_nested_dict


class Secret:
    """
    A Secret is a serializable object used to represent a secret key & value.

    Args:
        - name (str): The name of the secret

    The value of the `Secret` is not set upon initialization and instead is set
    either in `prefect.context` or on the server, with behavior dependent on the value
    of the `use_local_secrets` flag in your Prefect configuration file.
    """

    def __init__(self, name: str):
        self.name = name

    def get(self) -> Optional[Any]:
        """
        Retrieve the secret value.

        If not found, returns `None`.

        Returns:
            - Any: the value of the secret; if not found, returns `None`

        Raises:
            - ValueError: if `use_local_secrets=False` and the Client fails to retrieve your secret
        """
        if prefect.config.cloud.use_local_secrets is True:
            secrets = prefect.context.get("secrets", {})
            return secrets.get(self.name)
        else:
            client = Client()
            result = client.graphql(
                """
                query($name: String!) {
                    secretValue(name: $name)
                }
                """,
                name=self.name,
            )  # type: Any
            return as_nested_dict(result.data.secretValue, dict)
