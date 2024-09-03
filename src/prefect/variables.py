from typing import List, Optional

from pydantic import BaseModel, Field

from prefect._internal.compatibility.migration import getattr_migration
from prefect.client.schemas.actions import VariableCreate, VariableUpdate
from prefect.client.utilities import get_or_create_client
from prefect.exceptions import ObjectNotFound
from prefect.types import MAX_VARIABLE_NAME_LENGTH, StrictVariableValue
from prefect.utilities.asyncutils import sync_compatible


class Variable(BaseModel):
    """
    Variables are named, mutable JSON values that can be shared across tasks and flows.

    Arguments:
        name: A string identifying the variable.
        value: A string that is the value of the variable.
        tags: An optional list of strings to associate with the variable.
    """

    name: str = Field(
        default=...,
        description="The name of the variable",
        examples=["my_variable"],
        max_length=MAX_VARIABLE_NAME_LENGTH,
    )
    value: StrictVariableValue = Field(
        default=...,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: Optional[List[str]] = Field(default=None)

    @classmethod
    @sync_compatible
    async def set(
        cls,
        name: str,
        value: StrictVariableValue,
        tags: Optional[List[str]] = None,
        overwrite: bool = False,
    ) -> "Variable":
        """
        Sets a new variable. If one exists with the same name, must pass `overwrite=True`

        Returns the newly set variable object.

        Args:
            - name: The name of the variable to set.
            - value: The value of the variable to set.
            - tags: An optional list of strings to associate with the variable.
            - overwrite: Whether to overwrite the variable if it already exists.

        Example:
            Set a new variable and overwrite it if it already exists.

            ```
            from prefect.variables import Variable

            @flow
            def my_flow():
                Variable.set(name="my_var",value="test_value", tags=["hi", "there"], overwrite=True)
            ```
        """
        client, _ = get_or_create_client()
        variable_exists = await client.read_variable_by_name(name)
        var_dict = {"name": name, "value": value, "tags": tags or []}

        if variable_exists:
            if not overwrite:
                raise ValueError(
                    f"Variable {name!r} already exists. Use `overwrite=True` to update it."
                )
            await client.update_variable(variable=VariableUpdate(**var_dict))
            variable = await client.read_variable_by_name(name)
            var_dict = {
                "name": variable.name,
                "value": variable.value,
                "tags": variable.tags or [],
            }
        else:
            await client.create_variable(variable=VariableCreate(**var_dict))

        return cls(**var_dict)

    @classmethod
    @sync_compatible
    async def get(
        cls,
        name: str,
        default: StrictVariableValue = None,
    ) -> StrictVariableValue:
        """
        Get a variable's value by name.

        If the variable does not exist, return the default value.

        Args:
            - name: The name of the variable value to get.
            - default: The default value to return if the variable does not exist.

        Example:
            Get a variable's value by name.
            ```python
            from prefect import flow
            from prefect.variables import Variable

            @flow
            def my_flow():
                var = Variable.get("my_var")
            ```
        """
        client, _ = get_or_create_client()
        variable = await client.read_variable_by_name(name)

        return variable.value if variable else default

    @classmethod
    @sync_compatible
    async def unset(cls, name: str) -> bool:
        """
        Unset a variable by name.

        Args:
            - name: The name of the variable to unset.

        Returns `True` if the variable was deleted, `False` if the variable did not exist.

        Example:
            Unset a variable by name.
            ```python
            from prefect import flow
            from prefect.variables import Variable

            @flow
            def my_flow():
                Variable.unset("my_var")
            ```
        """
        client, _ = get_or_create_client()
        try:
            await client.delete_variable_by_name(name=name)
            return True
        except ObjectNotFound:
            return False


__getattr__ = getattr_migration(__name__)
