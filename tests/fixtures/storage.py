"""
Fixtures that create a small distributed storage API, including a storage block
"""
import subprocess
import sys
from typing import Any, Optional

import anyio
import httpx
import pytest
from fastapi import Body, FastAPI, status
from fastapi.exceptions import RequestValidationError

from prefect.blocks.storage import KVServerStorageBlock, LocalStorageBlock
from prefect.orion import models
from prefect.orion.api.server import validation_exception_handler


@pytest.fixture
async def local_storage_block_document_id(tmp_path, orion_client):
    # Local storage in a temporary directory that exists for the lifetime of a test
    block = LocalStorageBlock(storage_path=str(tmp_path))
    block_schema = await orion_client.read_block_schema_by_name(
        block._block_schema_name, block._block_schema_version
    )
    block_document_id = await orion_client.create_block(
        block, block_schema_id=block_schema.id, name="test"
    )
    return block_document_id


@pytest.fixture
async def local_storage_block(local_storage_block_document_id, orion_client):
    return await orion_client.read_block(local_storage_block_document_id)


# Key-value storage API ----------------------------------------------------------------

kv_api_app = FastAPI(
    exception_handlers={RequestValidationError: validation_exception_handler}
)

STORAGE = {}


@kv_api_app.get("/storage/{key}")
async def read_key(key: str):
    result = STORAGE.get(key)
    return result


@kv_api_app.post("/storage/{key}")
async def write_key(key, value: Optional[Any] = Body(None)):
    STORAGE[key] = value


@kv_api_app.get("/debug")
async def read_all():
    return STORAGE


@pytest.fixture(scope="session")
async def run_storage_server():
    """
    Run the simple storage API in a subprocess
    """
    process = subprocess.Popen(
        [
            "uvicorn",
            "tests.fixtures.storage:kv_api_app",
            "--host",
            "0.0.0.0",  # required for access across networked docker containers in CI
            "--port",
            "1234",
        ],
        stdout=sys.stdout,
        stderr=subprocess.STDOUT,
    )
    try:
        # Wait for the server to be ready
        async with httpx.AsyncClient() as client:
            response = None
            with anyio.move_on_after(10):
                while True:
                    try:
                        response = await client.get("http://127.0.0.1:1234/debug")
                    except httpx.ConnectError:
                        pass
                    else:
                        if response.status_code == status.HTTP_200_OK:
                            break
                    await anyio.sleep(0.1)
            if response:
                response.raise_for_status()
            if not response:
                raise RuntimeError(
                    "Timed out while attempting to connect to hosted test Orion."
                )

        # Yield to the consuming tests
        yield

    finally:
        while process.returncode is None:
            # Terminate the process
            process.terminate()
            # Ensure any remaining communication occurs — otherwise the process can be left
            # running
            process.communicate()
            # Poll for a return code
            process.poll()


@pytest.fixture
async def set_up_kv_storage(session, run_storage_server):
    """
    Use this fixture to make the distributed storage server the default
    (useful for distributed flow or task runner tests)
    """
    block_schema = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=KVServerStorageBlock.to_block_schema(),
        override=True,
    )

    block_document = await models.block_documents.create_block_document(
        session=session,
        block_document=KVServerStorageBlock(
            api_address="http://127.0.0.1:1234/storage"
        ).to_block_document(name="test-storage-block", block_schema_id=block_schema.id),
    )

    await models.block_documents.set_default_storage_block_document(
        session=session, block_document_id=block_document.id
    )
    await session.commit()
