from typing import List, Optional

from prefect._internal.compatibility.deprecated import deprecated_callable
from prefect.client.schemas.actions import VariableCreate as VariableRequest
from prefect.client.schemas.actions import VariableUpdate as VariableUpdateRequest
from prefect.client.utilities import get_or_create_client
from prefect.utilities.asyncutils import sync_compatible


class Variable(VariableRequest):
    """
    Variables are named, mutable string values, much like environment variables. Variables are scoped to a Prefect server instance or a single workspace in Prefect Cloud.
    https://docs.prefect.io/latest/concepts/variables/

    Arguments:
        name: A string identifying the variable.
        value: A string that is the value of the variable.
        tags: An optional list of strings to associate with the variable.
    """

    @classmethod
    @sync_compatible
    async def set(
        cls,
        name: str,
        value: str,
        tags: Optional[List[str]] = None,
        overwrite: bool = False,
    ) -> Optional[str]:
        """
        Sets a new variable. If one exists with the same name, user must pass `overwrite=True`
        ```
            from prefect.variables import Variable

            @flow
            def my_flow():
                var = Variable.set(name="my_var",value="test_value", tags=["hi", "there"], overwrite=True)
        ```
        or
        ```
            from prefect.variables import Variable

            @flow
            async def my_flow():
                var = await Variable.set(name="my_var",value="test_value", tags=["hi", "there"], overwrite=True)
        ```
        """
        client, _ = get_or_create_client()
        variable = await client.read_variable_by_name(name)
        var_dict = {"name": name, "value": value}
        var_dict["tags"] = tags or []
        if variable:
            if not overwrite:
                raise ValueError(
                    "You are attempting to save a variable with a name that is already in use. If you would like to overwrite the values that are saved, then call .set with `overwrite=True`."
                )
            var = VariableUpdateRequest(**var_dict)
            await client.update_variable(variable=var)
            variable = await client.read_variable_by_name(name)
        else:
            var = VariableRequest(**var_dict)
            variable = await client.create_variable(variable=var)

        return variable if variable else None

    @classmethod
    @sync_compatible
    async def get(cls, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a variable by name. If doesn't exist return the default.
        ```
            from prefect.variables import Variable

            @flow
            def my_flow():
                var = Variable.get("my_var")
        ```
        or
        ```
            from prefect.variables import Variable

            @flow
            async def my_flow():
                var = await Variable.get("my_var")
        ```
        """
        client, _ = get_or_create_client()
        variable = await client.read_variable_by_name(name)
        return variable if variable else default


@deprecated_callable(start_date="Apr 2024")
@sync_compatible
async def get(name: str, default: Optional[str] = None) -> Optional[str]:
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
    variable = await Variable.get(name)
    return variable.value if variable else default
