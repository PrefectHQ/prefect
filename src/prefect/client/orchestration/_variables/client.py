from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound

if TYPE_CHECKING:
    from prefect.client.schemas.actions import (
        VariableCreate,
        VariableUpdate,
    )
    from prefect.client.schemas.objects import (
        Variable,
    )


class VariableClient(BaseClient):
    def create_variable(self, variable: "VariableCreate") -> "Variable":
        """
        Creates an variable with the provided configuration.

        Args:
            variable: Desired configuration for the new variable.
        Returns:
            Information about the newly created variable.
        """
        try:
            response = self.request(
                "POST",
                "/variables/",
                json=variable.model_dump(mode="json", exclude_unset=True),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            else:
                raise

        from prefect.client.schemas.objects import Variable

        return Variable.model_validate(response.json())

    def read_variable_by_name(self, name: str) -> "Variable | None":
        """Reads a variable by name. Returns None if no variable is found."""
        try:
            response = self.request(
                "GET", "/variables/name/{name}", path_params={"name": name}
            )
            from prefect.client.schemas.objects import Variable

            return Variable(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            else:
                raise

    def read_variables(self, limit: int | None = None) -> list["Variable"]:
        """Reads all variables."""
        response = self.request("POST", "/variables/filter", json={"limit": limit})
        from prefect.client.schemas.objects import Variable

        return Variable.model_validate_list(response.json())

    def update_variable(self, variable: "VariableUpdate") -> None:
        """
        Updates a variable with the provided configuration.

        Args:
            variable: Desired configuration for the updated variable.
        Returns:
            Information about the updated variable.
        """
        self._client.patch(
            f"/variables/name/{variable.name}",
            json=variable.model_dump(mode="json", exclude_unset=True),
        )
        return None

    def delete_variable_by_name(self, name: str) -> None:
        """Deletes a variable by name."""
        try:
            self.request(
                "DELETE",
                "/variables/name/{name}",
                path_params={"name": name},
            )
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise


class VariableAsyncClient(BaseAsyncClient):
    async def create_variable(self, variable: "VariableCreate") -> "Variable":
        """Creates a variable with the provided configuration."""
        try:
            response = await self.request(
                "POST",
                "/variables/",
                json=variable.model_dump(mode="json", exclude_unset=True),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            else:
                raise

        from prefect.client.schemas.objects import Variable

        return Variable.model_validate(response.json())

    async def read_variable_by_name(self, name: str) -> "Variable | None":
        """Reads a variable by name. Returns None if no variable is found."""
        try:
            response = await self.request(
                "GET",
                "/variables/name/{name}",
                path_params={"name": name},
            )
            from prefect.client.schemas.objects import Variable

            return Variable.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            else:
                raise

    async def read_variables(self, limit: int | None = None) -> list["Variable"]:
        """Reads all variables."""
        response = await self.request(
            "POST", "/variables/filter", json={"limit": limit}
        )
        from prefect.client.schemas.objects import Variable

        return Variable.model_validate_list(response.json())

    async def update_variable(self, variable: "VariableUpdate") -> None:
        """
        Updates a variable with the provided configuration.

        Args:
            variable: Desired configuration for the updated variable.
        Returns:
            Information about the updated variable.
        """
        await self.request(
            "PATCH",
            "/variables/name/{name}",
            path_params={"name": variable.name},
            json=variable.model_dump(mode="json", exclude_unset=True),
        )
        return None

    async def delete_variable_by_name(self, name: str) -> None:
        """Deletes a variable by name."""
        try:
            await self.request(
                "DELETE",
                "/variables/name/{name}",
                path_params={"name": name},
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
