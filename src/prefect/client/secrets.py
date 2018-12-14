# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json
import os
from typing import Optional

import prefect
from prefect.client.client import Client


class Secret:
    """
    A Secret is a serializable object used to represent a secret key & value.

    Args:
        - name (str): The name of the secret

    The value of the `Secret` is not set upon initialization and instead is set
    either in `prefect.context` or on the server, with behavior dependent on the value
    of the `use_local_secrets` flag in your Prefect configuration file.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def get(self) -> Optional[str]:
        """
        Retrieve the secret value.

        If not found, returns `None`.

        Raises:
            - ValueError: if `use_local_secrets=False` and the Client fails to retrieve your secret
        """
        if prefect.config.cloud.use_local_secrets is True:
            secrets = prefect.context.get("secrets", {})
            return secrets.get(self.name)
        else:
            client = Client()
            return client.graphql(  # type: ignore
                """
                query($name: String!) {
                    secretValue(name: $name)
                }""",
                name=self.name,
            ).secretValue
