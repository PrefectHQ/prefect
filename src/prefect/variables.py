from typing import Any, Dict, List, Optional, Union

from prefect.client.schemas.actions import VariableCreate as VariableRequest
from prefect.client.schemas.actions import VariableUpdate as VariableUpdateRequest
from prefect.client.schemas.objects import Variable as VariableResponse
from prefect.client.utilities import get_or_create_client
from prefect.exceptions import ObjectNotFound
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
        value: Union[str, int, float, bool, None, List[Any], Dict[str, Any]],
        tags: Optional[List[str]] = None,
        overwrite: bool = False,
    ):
        """
        Sets a new variable. If one exists with the same name, user must pass `overwrite=True`
        Returns `True` if the variable was created or updated

        ```
            from prefect.variables import Variable

            @flow
            def my_flow():
                Variable.set(name="my_var",value="test_value", tags=["hi", "there"], overwrite=True)
        ```
        or
        ```
            from prefect.variables import Variable

            @flow
            async def my_flow():
                await Variable.set(name="my_var",value="test_value", tags=["hi", "there"], overwrite=True)
        ```
        """
        client, _ = get_or_create_client()
        variable = await client.read_variable_by_name(name)
        var_dict = {"name": name, "value": value, "tags": tags or []}
        if variable:
            if not overwrite:
                raise ValueError(
                    "You are attempting to set a variable with a name that is already in use. "
                    "If you would like to overwrite it, pass `overwrite=True`."
                )
            await client.update_variable(variable=VariableUpdateRequest(**var_dict))
        else:
            await client.create_variable(variable=VariableRequest(**var_dict))

    @classmethod
    @sync_compatible
    async def get(
        cls,
        name: str,
        default: Union[str, int, float, bool, None, List[Any], Dict[str, Any]] = None,
        as_object: bool = False,
    ) -> Union[
        str, int, float, bool, None, List[Any], Dict[str, Any], VariableResponse
    ]:
        """
        Get a variable's value by name.

        If the variable does not exist, return the default value.

        If `as_object=True`, return the full variable object. `default` is ignored in this case.

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
        if as_object:
            return variable

        return variable.value if variable else default

    @classmethod
    @sync_compatible
    async def unset(cls, name: str) -> bool:
        """
        Unset a variable by name.

        ```
            from prefect.variables import Variable

            @flow
            def my_flow():
                Variable.unset("my_var")
        ```
        or
        ```
            from prefect.variables import Variable

            @flow
            async def my_flow():
                await Variable.unset("my_var")
        ```
        """
        client, _ = get_or_create_client()
        try:
            await client.delete_variable_by_name(name=name)
            return True
        except ObjectNotFound:
            return False
