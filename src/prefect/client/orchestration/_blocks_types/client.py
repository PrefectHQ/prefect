from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import HTTPStatusError

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound, ProtectedBlockError

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.actions import (
        BlockTypeCreate,
        BlockTypeUpdate,
    )
    from prefect.client.schemas.objects import (
        BlockDocument,
        BlockType,
    )


class BlocksTypeClient(BaseClient):
    def read_block_documents_by_type(
        self,
        block_type_slug: str,
        offset: int | None = None,
        limit: int | None = None,
        include_secrets: bool = True,
    ) -> "list[BlockDocument]":
        """Retrieve block documents by block type slug.

        Args:
            block_type_slug: The block type slug.
            offset: an offset
            limit: the number of blocks to return
            include_secrets: whether to include secret values

        Returns:
            A list of block documents
        """
        response = self.request(
            "GET",
            "/block_types/slug/{slug}/block_documents",
            path_params={"slug": block_type_slug},
            params=dict(
                offset=offset,
                limit=limit,
                include_secrets=include_secrets,
            ),
        )

        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate_list(response.json())

    def create_block_type(self, block_type: "BlockTypeCreate") -> "BlockType":
        """
        Create a block type in the Prefect API.
        """
        try:
            response = self.request(
                "POST",
                "/block_types/",
                json=block_type.model_dump(
                    mode="json", exclude_unset=True, exclude={"id"}
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate(response.json())

    def read_block_type_by_slug(self, slug: str) -> "BlockType":
        """
        Read a block type by its slug.
        """
        try:
            response = self.request(
                "GET",
                "/block_types/slug/{slug}",
                path_params={"slug": slug},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate(response.json())

    def update_block_type(
        self, block_type_id: "UUID", block_type: "BlockTypeUpdate"
    ) -> None:
        """
        Update a block document in the Prefect API.
        """
        from prefect.client.schemas.actions import BlockTypeUpdate

        try:
            self.request(
                "PATCH",
                "/block_types/{id}",
                path_params={"id": block_type_id},
                json=block_type.model_dump(
                    mode="json",
                    exclude_unset=True,
                    include=BlockTypeUpdate.updatable_fields(),
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def delete_block_type(self, block_type_id: "UUID") -> None:
        """
        Delete a block type.
        """
        try:
            self.request(
                "DELETE",
                "/block_types/{id}",
                path_params={"id": block_type_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            elif (
                e.response.status_code == 403
                and e.response.json()["detail"]
                == "protected block types cannot be deleted."
            ):
                raise ProtectedBlockError(
                    "Protected block types cannot be deleted."
                ) from e
            else:
                raise

    def read_block_types(self) -> "list[BlockType]":
        """
        Read all block types
        Raises:
            httpx.RequestError: if the block types were not found

        Returns:
            List of BlockTypes.
        """
        response = self.request("POST", "/block_types/filter", json={})
        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate_list(response.json())

    def read_block_document_by_name(
        self,
        name: str,
        block_type_slug: str,
        include_secrets: bool = True,
    ) -> "BlockDocument":
        """
        Read the block document with the specified name that corresponds to a
        specific block type name.

        Args:
            name: The block document name.
            block_type_slug: The block type slug.
            include_secrets (bool): whether to include secret values
                on the Block, corresponding to Pydantic's `SecretStr` and
                `SecretBytes` fields. These fields are automatically obfuscated
                by Pydantic, but users can additionally choose not to receive
                their values from the API. Note that any business logic on the
                Block may not work if this is `False`.

        Raises:
            httpx.RequestError: if the block document was not found for any reason

        Returns:
            A block document or None.
        """
        try:
            response = self.request(
                "GET",
                "/block_types/slug/{slug}/block_documents/name/{block_document_name}",
                path_params={"slug": block_type_slug, "block_document_name": name},
                params=dict(include_secrets=include_secrets),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate(response.json())


class BlocksTypeAsyncClient(BaseAsyncClient):
    async def read_block_documents_by_type(
        self,
        block_type_slug: str,
        offset: int | None = None,
        limit: int | None = None,
        include_secrets: bool = True,
    ) -> "list[BlockDocument]":
        """Retrieve block documents by block type slug.

        Args:
            block_type_slug: The block type slug.
            offset: an offset
            limit: the number of blocks to return
            include_secrets: whether to include secret values

        Returns:
            A list of block documents
        """
        response = await self.request(
            "GET",
            "/block_types/slug/{slug}/block_documents",
            path_params={"slug": block_type_slug},
            params=dict(
                offset=offset,
                limit=limit,
                include_secrets=include_secrets,
            ),
        )

        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate_list(response.json())

    async def create_block_type(self, block_type: "BlockTypeCreate") -> "BlockType":
        """
        Create a block type in the Prefect API.
        """
        try:
            response = await self.request(
                "POST",
                "/block_types/",
                json=block_type.model_dump(
                    mode="json", exclude_unset=True, exclude={"id"}
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate(response.json())

    async def read_block_type_by_slug(self, slug: str) -> "BlockType":
        """
        Read a block type by its slug.
        """
        try:
            response = await self.request(
                "GET",
                "/block_types/slug/{slug}",
                path_params={"slug": slug},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate(response.json())

    async def update_block_type(
        self, block_type_id: "UUID", block_type: "BlockTypeUpdate"
    ) -> None:
        """
        Update a block document in the Prefect API.
        """
        from prefect.client.schemas.actions import BlockTypeUpdate

        try:
            await self.request(
                "PATCH",
                "/block_types/{id}",
                path_params={"id": block_type_id},
                json=block_type.model_dump(
                    mode="json",
                    exclude_unset=True,
                    include=BlockTypeUpdate.updatable_fields(),
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def delete_block_type(self, block_type_id: "UUID") -> None:
        """
        Delete a block type.
        """
        try:
            await self.request(
                "DELETE",
                "/block_types/{id}",
                path_params={"id": block_type_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            elif (
                e.response.status_code == 403
                and e.response.json()["detail"]
                == "protected block types cannot be deleted."
            ):
                raise ProtectedBlockError(
                    "Protected block types cannot be deleted."
                ) from e
            else:
                raise

    async def read_block_types(self) -> "list[BlockType]":
        """
        Read all block types
        Raises:
            httpx.RequestError: if the block types were not found

        Returns:
            List of BlockTypes.
        """
        response = await self.request("POST", "/block_types/filter", json={})
        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate_list(response.json())

    async def read_block_document_by_name(
        self,
        name: str,
        block_type_slug: str,
        include_secrets: bool = True,
    ) -> "BlockDocument":
        """
        Read the block document with the specified name that corresponds to a
        specific block type name.

        Args:
            name: The block document name.
            block_type_slug: The block type slug.
            include_secrets (bool): whether to include secret values
                on the Block, corresponding to Pydantic's `SecretStr` and
                `SecretBytes` fields. These fields are automatically obfuscated
                by Pydantic, but users can additionally choose not to receive
                their values from the API. Note that any business logic on the
                Block may not work if this is `False`.

        Raises:
            httpx.RequestError: if the block document was not found for any reason

        Returns:
            A block document or None.
        """
        try:
            response = await self.request(
                "GET",
                "/block_types/slug/{slug}/block_documents/name/{block_document_name}",
                path_params={"slug": block_type_slug, "block_document_name": name},
                params=dict(include_secrets=include_secrets),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate(response.json())
