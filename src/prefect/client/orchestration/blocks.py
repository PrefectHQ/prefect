from typing import TYPE_CHECKING, Optional, Union

from httpx import HTTPStatusError

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.client.orchestration.routes import arequest, request
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound, ProtectedBlockError

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.actions import (
        BlockDocumentCreate,
        BlockDocumentUpdate,
        BlockSchemaCreate,
        BlockTypeCreate,
        BlockTypeUpdate,
    )
    from prefect.client.schemas.objects import BlockDocument, BlockSchema, BlockType


class BlockTypeClient(BaseClient):
    def create_block_type(self, block_type: "BlockTypeCreate") -> "BlockType":
        """Create a block type in the Prefect API."""
        try:
            response = request(
                self._client,
                "POST",
                "/block_types/",
                json=block_type.model_dump(
                    mode="json", exclude_unset=True, exclude={"id"}
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate(response.json())

    def read_block_type_by_slug(self, slug: str) -> "BlockType":
        """Read a block type by its slug."""
        try:
            response = request(
                self._client,
                "GET",
                "/block_types/slug/{slug}",
                path_params={"slug": slug},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate(response.json())

    def read_block_types(self) -> list["BlockType"]:
        """Read all block types."""
        response = request(
            self._client,
            "POST",
            "/block_types/filter",
            json={},
        )
        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate_list(response.json())

    def update_block_type(
        self, block_type_id: "UUID", block_type: "BlockTypeUpdate"
    ) -> None:
        """Update a block type."""
        try:
            request(
                self._client,
                "PATCH",
                "/block_types/{block_type_id}",
                path_params={"block_type_id": block_type_id},
                json=block_type.model_dump(
                    mode="json",
                    exclude_unset=True,
                    include=BlockTypeUpdate.updatable_fields(),
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

    def delete_block_type(self, block_type_id: "UUID") -> None:
        """Delete a block type."""
        try:
            request(
                self._client,
                "DELETE",
                "/block_types/{block_type_id}",
                path_params={"block_type_id": block_type_id},
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
            raise

    def read_block_documents_by_type(
        self,
        block_type_slug: str,
        *,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include_secrets: bool = True,
    ) -> list["BlockDocument"]:
        """Read block documents by block type slug."""
        response = request(
            self._client,
            "GET",
            "/block_types/slug/{block_type_slug}/block_documents",
            path_params={"block_type_slug": block_type_slug},
            params={
                "offset": offset,
                "limit": limit,
                "include_secrets": include_secrets,
            },
        )
        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate_list(response.json())


class BlockTypeAsyncClient(BaseAsyncClient):
    async def create_block_type(self, block_type: "BlockTypeCreate") -> "BlockType":
        """Create a block type in the Prefect API."""
        try:
            response = await arequest(
                self._client,
                "POST",
                "/block_types/",
                json=block_type.model_dump(
                    mode="json", exclude_unset=True, exclude={"id"}
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate(response.json())

    async def read_block_type_by_slug(self, slug: str) -> "BlockType":
        """Read a block type by its slug."""
        try:
            response = await arequest(
                self._client,
                "GET",
                "/block_types/slug/{slug}",
                path_params={"slug": slug},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate(response.json())

    async def read_block_types(self) -> list["BlockType"]:
        """Read all block types."""
        response = await arequest(
            self._client,
            "POST",
            "/block_types/filter",
            json={},
        )
        from prefect.client.schemas.objects import BlockType

        return BlockType.model_validate_list(response.json())

    async def update_block_type(
        self, block_type_id: "UUID", block_type: "BlockTypeUpdate"
    ) -> None:
        """Update a block type."""
        try:
            await arequest(
                self._client,
                "PATCH",
                "/block_types/{block_type_id}",
                path_params={"block_type_id": block_type_id},
                json=block_type.model_dump(
                    mode="json",
                    exclude_unset=True,
                    include=BlockTypeUpdate.updatable_fields(),
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

    async def delete_block_type(self, block_type_id: "UUID") -> None:
        """Delete a block type."""
        try:
            await arequest(
                self._client,
                "DELETE",
                "/block_types/{block_type_id}",
                path_params={"block_type_id": block_type_id},
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
            raise

    async def read_block_documents_by_type(
        self,
        block_type_slug: str,
        *,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include_secrets: bool = True,
    ) -> list["BlockDocument"]:
        """Read block documents by block type slug."""
        response = await arequest(
            self._client,
            "GET",
            "/block_types/slug/{block_type_slug}/block_documents",
            path_params={"block_type_slug": block_type_slug},
            params={
                "offset": offset,
                "limit": limit,
                "include_secrets": include_secrets,
            },
        )
        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate_list(response.json())


class BlockSchemaClient(BaseClient):
    def create_block_schema(self, block_schema: "BlockSchemaCreate") -> "BlockSchema":
        """Create a block schema in the Prefect API."""
        try:
            response = request(
                self._client,
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
            raise

        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate(response.json())

    def read_block_schemas(self) -> list["BlockSchema"]:
        """Read all block schemas."""
        response = request(
            self._client,
            "POST",
            "/block_schemas/filter",
            json={},
        )
        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate_list(response.json())

    def read_block_schema_by_checksum(
        self, checksum: str, version: Optional[str] = None
    ) -> "BlockSchema":
        """Read a block schema by its checksum."""
        try:
            url = "/block_schemas/checksum/{checksum}"
            if version:
                url += "?version={version}"

            response = request(
                self._client,
                "GET",
                url,
                path_params={
                    "checksum": checksum,
                    "version": version,
                },
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate(response.json())

    def get_most_recent_block_schema_for_block_type(
        self, block_type_id: "UUID"
    ) -> Optional["BlockSchema"]:
        """Get the most recent block schema for a block type."""
        response = request(
            self._client,
            "POST",
            "/block_schemas/filter",
            json={
                "block_schemas": {"block_type_id": {"any_": [str(block_type_id)]}},
                "limit": 1,
            },
        )

        from prefect.client.schemas.objects import BlockSchema

        results = BlockSchema.model_validate_list(response.json())
        return results[0] if results else None


class BlockSchemaAsyncClient(BaseAsyncClient):
    async def create_block_schema(
        self, block_schema: "BlockSchemaCreate"
    ) -> "BlockSchema":
        """Create a block schema in the Prefect API."""
        try:
            response = await arequest(
                self._client,
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
            raise

        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate(response.json())

    async def read_block_schemas(self) -> list["BlockSchema"]:
        """Read all block schemas."""
        response = await arequest(
            self._client,
            "POST",
            "/block_schemas/filter",
            json={},
        )
        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate_list(response.json())

    async def read_block_schema_by_checksum(
        self, checksum: str, version: Optional[str] = None
    ) -> "BlockSchema":
        """Read a block schema by its checksum."""
        try:
            url = "/block_schemas/checksum/{checksum}"
            if version:
                url += "?version={version}"

            response = await arequest(
                self._client,
                "GET",
                url,
                path_params={
                    "checksum": checksum,
                    "version": version,
                },
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockSchema

        return BlockSchema.model_validate(response.json())

    async def get_most_recent_block_schema_for_block_type(
        self, block_type_id: "UUID"
    ) -> Optional["BlockSchema"]:
        """Get the most recent block schema for a block type."""
        response = await arequest(
            self._client,
            "POST",
            "/block_schemas/filter",
            json={
                "block_schemas": {"block_type_id": {"any_": [str(block_type_id)]}},
                "limit": 1,
            },
        )

        from prefect.client.schemas.objects import BlockSchema

        results = BlockSchema.model_validate_list(response.json())
        return results[0] if results else None


class BlockDocumentClient(BaseClient):
    def create_block_document(
        self,
        block_document: "Union[BlockDocument, BlockDocumentCreate]",
        include_secrets: bool = True,
    ) -> "BlockDocument":
        """Create a block document in the Prefect API."""
        try:
            response = request(
                self._client,
                "POST",
                "/block_documents/",
                json=block_document.model_dump(
                    mode="json",
                    exclude_unset=True,
                    exclude={"id", "block_schema", "block_type"},
                    context={"include_secrets": include_secrets},
                    serialize_as_any=True,
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate(response.json())

    def read_block_document(
        self, block_document_id: "UUID", include_secrets: bool = True
    ) -> "BlockDocument":
        """Read a block document by ID."""
        try:
            response = request(
                self._client,
                "GET",
                "/block_documents/{block_document_id}",
                path_params={"block_document_id": block_document_id},
                params={"include_secrets": include_secrets},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate(response.json())

    def read_block_documents(
        self,
        block_schema_type: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include_secrets: bool = True,
    ) -> list["BlockDocument"]:
        """Read multiple block documents with filtering."""
        response = request(
            self._client,
            "POST",
            "/block_documents/filter",
            json={
                "block_schema_type": block_schema_type,
                "offset": offset,
                "limit": limit,
                "include_secrets": include_secrets,
            },
        )
        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate_list(response.json())

    def read_block_document_by_name(
        self,
        name: str,
        block_type_slug: str,
        include_secrets: bool = True,
    ) -> "BlockDocument":
        """Read a block document by name and type slug."""
        try:
            response = request(
                self._client,
                "GET",
                "/block_types/slug/{block_type_slug}/block_documents/name/{name}",
                path_params={
                    "block_type_slug": block_type_slug,
                    "name": name,
                },
                params={"include_secrets": include_secrets},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate(response.json())

    def update_block_document(
        self, block_document_id: "UUID", block_document: "BlockDocumentUpdate"
    ) -> None:
        """Update a block document."""
        try:
            request(
                self._client,
                "PATCH",
                "/block_documents/{block_document_id}",
                path_params={"block_document_id": block_document_id},
                json=block_document.model_dump(
                    mode="json",
                    exclude_unset=True,
                    include={"data", "merge_existing_data", "block_schema_id"},
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

    def delete_block_document(self, block_document_id: "UUID") -> None:
        """Delete a block document."""
        try:
            request(
                self._client,
                "DELETE",
                "/block_documents/{block_document_id}",
                path_params={"block_document_id": block_document_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise


class BlockDocumentAsyncClient(BaseAsyncClient):
    async def create_block_document(
        self,
        block_document: "Union[BlockDocument, BlockDocumentCreate]",
        include_secrets: bool = True,
    ) -> "BlockDocument":
        """Create a block document in the Prefect API."""
        try:
            response = await arequest(
                self._client,
                "POST",
                "/block_documents/",
                json=block_document.model_dump(
                    mode="json",
                    exclude_unset=True,
                    exclude={"id", "block_schema", "block_type"},
                    context={"include_secrets": include_secrets},
                    serialize_as_any=True,
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate(response.json())

    async def read_block_document(
        self, block_document_id: "UUID", include_secrets: bool = True
    ) -> "BlockDocument":
        """Read a block document by ID."""
        try:
            response = await arequest(
                self._client,
                "GET",
                "/block_documents/{block_document_id}",
                path_params={"block_document_id": block_document_id},
                params={"include_secrets": include_secrets},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate(response.json())

    async def read_block_documents(
        self,
        block_schema_type: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include_secrets: bool = True,
    ) -> list["BlockDocument"]:
        """Read multiple block documents with filtering."""
        response = await arequest(
            self._client,
            "POST",
            "/block_documents/filter",
            json={
                "block_schema_type": block_schema_type,
                "offset": offset,
                "limit": limit,
                "include_secrets": include_secrets,
            },
        )
        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate_list(response.json())

    async def read_block_document_by_name(
        self,
        name: str,
        block_type_slug: str,
        include_secrets: bool = True,
    ) -> "BlockDocument":
        """Read a block document by name and type slug."""
        try:
            response = await arequest(
                self._client,
                "GET",
                "/block_types/slug/{block_type_slug}/block_documents/name/{name}",
                path_params={
                    "block_type_slug": block_type_slug,
                    "name": name,
                },
                params={"include_secrets": include_secrets},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

        from prefect.client.schemas.objects import BlockDocument

        return BlockDocument.model_validate(response.json())

    async def update_block_document(
        self, block_document_id: "UUID", block_document: "BlockDocumentUpdate"
    ) -> None:
        """Update a block document."""
        try:
            await arequest(
                self._client,
                "PATCH",
                "/block_documents/{block_document_id}",
                path_params={"block_document_id": block_document_id},
                json=block_document.model_dump(
                    mode="json",
                    exclude_unset=True,
                    include={"data", "merge_existing_data", "block_schema_id"},
                ),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise

    async def delete_block_document(self, block_document_id: "UUID") -> None:
        """Delete a block document."""
        try:
            await arequest(
                self._client,
                "DELETE",
                "/block_documents/{block_document_id}",
                path_params={"block_document_id": block_document_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            raise
