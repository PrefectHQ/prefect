"""
::: warning Secret Tasks are preferred
While this Secrets API is fully supported, using a [Prefect Secret Task](../tasks/secrets) is
typically preferred for better reuse of Secret values and visibility into the secrets used
within Tasks / Flows.
:::

A Secret is a serializable object used to represent a secret key & value.

The value of the `Secret` is not set upon initialization and instead is set
either in `prefect.context` or on the server, with behavior dependent on the value
of the `use_local_secrets` flag in your Prefect configuration file.

To set a Secret in Prefect Cloud, you can use `prefect.Client.set_secret`, or set it directly
via GraphQL:

```graphql
mutation {
  set_secret(input: { name: "KEY", value: "VALUE" }) {
    success
  }
}
```

To set a _local_ Secret, either place the value in your user configuration file (located at
`~/.prefect/config.toml`):

```
[context.secrets]
MY_KEY = "MY_VALUE"
```

or directly in context:

```python
import prefect

prefect.context.setdefault("secrets", {}) # to make sure context has a secrets attribute
prefect.context.secrets["MY_KEY"] = "MY_VALUE"
```

or specify the secret via environment variable:

```bash
export PREFECT__CONTEXT__SECRETS__MY_KEY="MY_VALUE"
```

::: tip Default secrets
Special default secret names can be used to authenticate to third-party systems in a
installation-wide way. Read more about this in our [Secrets concept
documentation](/core/concepts/secrets.md#default-secrets).
:::

::: tip
When settings secrets via `.toml` config files, you can use the [TOML
Keys](https://github.com/toml-lang/toml#keys) docs for data structure specifications. Running
`prefect` commands with invalid `.toml` config files will lead to tracebacks that contain
references to: `..../toml/decoder.py`.
:::

"""

import json
from typing import Any, Optional

import prefect
from prefect.client.client import Client
from prefect.utilities.exceptions import ClientError


class Secret:
    """
    A Secret is a serializable object used to represent a secret key & value.

    Args:
        - name (str): The name of the secret

    The value of the `Secret` is not set upon initialization and instead is set
    either in `prefect.context` or on the server, with behavior dependent on the value
    of the `use_local_secrets` flag in your Prefect configuration file.

    If using local secrets, `Secret.get()` will attempt to call `json.loads` on the
    value pulled from context.  For this reason it is recommended to store local secrets as
    JSON documents to avoid ambiguous behavior (e.g., `"42"` being parsed as `42`).
    """

    def __init__(self, name: str):
        self.name = name

    @property
    def client(self) -> Client:
        if not hasattr(self, "_client"):
            self._client = Client()
        return self._client

    def exists(self) -> bool:
        """
        Determine if the secret exists.

        Returns:
            - bool: a boolean specifying whether the Secret is accessible or not
        """
        secrets = prefect.context.get("secrets", {})
        if self.name in secrets:
            return True
        elif prefect.context.config.cloud.use_local_secrets is False:
            cloud_secrets = self.client.graphql("query{secret_names}").data.secret_names
            if self.name in cloud_secrets:
                return True
        return False

    def get(self) -> Optional[Any]:
        """
        Retrieve the secret value.  If not found, returns `None`.

        If using local secrets, `Secret.get()` will attempt to call `json.loads` on the
        value pulled from context.  For this reason it is recommended to store local secrets as
        JSON documents to avoid ambiguous behavior.

        Returns:
            - Any: the value of the secret; if not found, raises an error

        Raises:
            - ValueError: if `.get()` is called within a Flow building context, or if
                `use_local_secrets=True` and your Secret doesn't exist
            - KeyError: if `use_local_secrets=False` and the Client fails to retrieve your secret
            - ClientError: if the client experiences an unexpected error communicating with the
                backend
        """
        if isinstance(prefect.context.get("flow"), prefect.core.flow.Flow):
            raise ValueError(
                "Secrets should only be retrieved during a Flow run, not while building a Flow."
            )

        secrets = prefect.context.get("secrets", {})
        try:
            value = secrets[self.name]
        except KeyError:
            if prefect.context.config.cloud.use_local_secrets is False:
                try:
                    result = self.client.graphql(
                        """
                        query($name: String!) {
                            secret_value(name: $name)
                        }
                        """,
                        variables=dict(name=self.name),
                    )
                except ClientError as exc:
                    if "No value found for the requested key" in str(exc):
                        raise KeyError(
                            f"The secret {self.name} was not found.  Please ensure that it "
                            f"was set correctly in your tenant: https://docs.prefect.io/"
                            f"orchestration/concepts/secrets.html"
                        ) from exc
                    else:
                        raise exc
                # the result object is a Box, so we recursively restore builtin
                # dict/list classes
                result_dict = result.to_dict()
                value = result_dict["data"]["secret_value"]
            else:
                raise ValueError(
                    'Local Secret "{}" was not found.'.format(self.name)
                ) from None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
