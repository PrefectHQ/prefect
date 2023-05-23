from typing import Optional

from prefect.client.orchestration import PrefectClient
from prefect.client.utilities import inject_client
from prefect.utilities.asyncutils import sync_compatible


@sync_compatible
async def get(name: str, default: str = None) -> Optional[str]:
    """
    Get a variable by name. If doesn't exist return the default.
    ```
        from prefect import variables

        @flow
        def my_flow():
            var = variables.get("my_var")
    ```
    or
    ```
        from prefect import variables

        @flow
        async def my_flow():
            var = await variables.get("my_var")
    ```
    """
    variable = await _get_variable_by_name(name)
    return variable.value if variable else default


@inject_client
async def _get_variable_by_name(
    name: str,
    client: PrefectClient,
):
    variable = await client.read_variable_by_name(name)
    return variable
