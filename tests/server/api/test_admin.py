from uuid import uuid4

import httpx
from starlette import status

import prefect
from prefect.blocks.system import Secret
from prefect.filesystems import LocalFileSystem


async def test_version(client: httpx.AsyncClient) -> None:
    response = await client.get("/admin/version")
    assert response.status_code == status.HTTP_200_OK
    assert prefect.__version__
    assert response.json() == prefect.__version__


class TestSettings:
    async def test_read_settings(self, client: httpx.AsyncClient) -> None:
        from prefect.settings import Settings, get_current_settings

        response = await client.get("/admin/settings")
        assert response.status_code == status.HTTP_200_OK
        parsed_settings = Settings.model_validate(response.json())
        prefect_settings = get_current_settings()

        assert parsed_settings.model_dump(mode="json") == prefect_settings.model_dump(
            mode="json"
        )


class TestServerDefaultResultStorage:
    async def test_read_server_default_result_storage_when_unset(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/admin/storage")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"default_result_storage_block_id": None}

    async def test_update_and_clear_server_default_result_storage(
        self, client: httpx.AsyncClient, prefect_client
    ) -> None:
        block_document = await LocalFileSystem(basepath="/tmp").asave(
            name=f"result-storage-{uuid4()}",
            client=prefect_client,
        )
        block_document_id = str(block_document)

        update_response = await client.put(
            "/admin/storage",
            json={"default_result_storage_block_id": block_document_id},
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json() == {
            "default_result_storage_block_id": block_document_id
        }

        read_response = await client.get("/admin/storage")
        assert read_response.status_code == status.HTTP_200_OK
        assert read_response.json() == {
            "default_result_storage_block_id": block_document_id
        }

        clear_response = await client.delete("/admin/storage")
        assert clear_response.status_code == status.HTTP_204_NO_CONTENT

        read_cleared_response = await client.get("/admin/storage")
        assert read_cleared_response.status_code == status.HTTP_200_OK
        assert read_cleared_response.json() == {"default_result_storage_block_id": None}

    async def test_update_server_default_result_storage_rejects_missing_block_document(
        self, client: httpx.AsyncClient
    ) -> None:
        block_document_id = str(uuid4())

        response = await client.put(
            "/admin/storage",
            json={"default_result_storage_block_id": block_document_id},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "detail": f"Block document {block_document_id} not found."
        }

    async def test_update_server_default_result_storage_requires_block_document_id(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.put("/admin/storage", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_update_server_default_result_storage_rejects_non_storage_block(
        self, client: httpx.AsyncClient, prefect_client
    ) -> None:
        block_document_id = await Secret(value="super-secret").asave(
            name=f"not-storage-{uuid4()}",
            client=prefect_client,
        )

        response = await client.put(
            "/admin/storage",
            json={"default_result_storage_block_id": str(block_document_id)},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "detail": (
                f"Block document {block_document_id} cannot be used for result storage."
            )
        }
