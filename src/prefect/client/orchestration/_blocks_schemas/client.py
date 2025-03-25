from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import HTTPStatusError

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.actions import BlockSchemaCreate
    from prefect.client.schemas.objects import BlockSchema


class BlocksSchemaClient(BaseClient):
    def create_block_schema(self, block_schema: "BlockSchemaCreate") -> "BlockSchema":
        """
        Create a block schema in the Prefect API.
        """
        try:
            response = self.request(
                "POST",
                "/block_schemas/",
                json=block_schema.model_dump(
                    mode="json",
                    exclude_unset=True,
                    exclude={"id", "block_type", "checksum"},
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate(response.json())

    def read_block_schema_by_checksum(
        self, checksum: str, version: str | None = None
    ) -> "BlockSchema":
        """
        Look up a block schema checksum
        """
        try:
            response = self.request(
                "GET",
                "/block_schemas/checksum/{checksum}",
                path_params={"checksum": checksum},
                **({"params": {"version": version}} if version else {}),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate(response.json())

    def read_block_schemas(self) -> "list[BlockSchema]":
        """
        Read all block schemas
        Raises:
            httpx.RequestError: if a valid block schema was not found

        Returns:
            A BlockSchema.
        """
        response = self.request("POST", "/block_schemas/filter", json={})
        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate_list(response.json())

    def get_most_recent_block_schema_for_block_type(
        self,
        block_type_id: "UUID",
    ) -> "BlockSchema | None":
        """
        Fetches the most recent block schema for a specified block type ID.

        Args:
            block_type_id: The ID of the block type.

        Raises:
            httpx.RequestError: If the request fails for any reason.

        Returns:
            The most recent block schema or None.
        """
        try:
            response = self.request(
                "POST",
                "/block_schemas/filter",
                json={
                    "block_schemas": {"block_type_id": {"any_": [str(block_type_id)]}},
                    "limit": 1,
                },
            )
        except HTTPStatusError:
            raise
        from prefect.client.schemas.objects import BlockSchema

        return next(iter(BlockSchema.model_validate_list(response.json())), None)


class BlocksSchemaAsyncClient(BaseAsyncClient):
    async def create_block_schema(
        self, block_schema: "BlockSchemaCreate"
    ) -> "BlockSchema":
        """
        Create a block schema in the Prefect API.
        """
        try:
            response = await self.request(
                "POST",
                "/block_schemas/",
                json=block_schema.model_dump(
                    mode="json",
                    exclude_unset=True,
                    exclude={"id", "block_type", "checksum"},
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate(response.json())

    async def read_block_schema_by_checksum(
        self, checksum: str, version: str | None = None
    ) -> "BlockSchema":
        """
        Look up a block schema checksum
        """
        try:
            response = await self.request(
                "GET",
                "/block_schemas/checksum/{checksum}",
                path_params={"checksum": checksum},
                **({"params": {"version": version}} if version else {}),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate(response.json())

    async def read_block_schemas(self) -> "list[BlockSchema]":
        """
        Read all block schemas
        Raises:
            httpx.RequestError: if a valid block schema was not found

        Returns:
            A BlockSchema.
        """
        response = await self.request("POST", "/block_schemas/filter", json={})
        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate_list(response.json())

    async def get_most_recent_block_schema_for_block_type(
        self,
        block_type_id: "UUID",
    ) -> "BlockSchema | None":
        """
        Fetches the most recent block schema for a specified block type ID.

        Args:
            block_type_id: The ID of the block type.

        Raises:
            httpx.RequestError: If the request fails for any reason.

        Returns:
            The most recent block schema or None.
        """
        try:
            response = await self.request(
                "POST",
                "/block_schemas/filter",
                json={
                    "block_schemas": {"block_type_id": {"any_": [str(block_type_id)]}},
                    "limit": 1,
                },
            )
        except HTTPStatusError:
            raise
        from prefect.client.schemas.objects import BlockSchema

        return next(iter(BlockSchema.model_validate_list(response.json())), None)
