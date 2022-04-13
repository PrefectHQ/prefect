"""
Fixtures that create a small distributed storage API, including a storage block
"""
import subprocess
import sys
import time
from typing import Any, Optional

import anyio
import httpx
import pytest
from fastapi import Body, FastAPI
from fastapi.exceptions import RequestValidationError

from prefect.blocks.storage import KVServerStorageBlock, LocalStorageBlock
from prefect.orion import models
from prefect.orion.api.server import validation_exception_handler
from prefect.orion.schemas.actions import BlockCreate, BlockSpecCreate


@pytest.fixture
async def local_storage_block_id(tmp_path, orion_client):
    # Local storage in a temporary directory that exists for the lifetime of a test
    block = LocalStorageBlock(storage_path=str(tmp_path))
    block_spec = await orion_client.read_block_spec_by_name(
        block._block_spec_name, block._block_spec_version
    )
    block_id = await orion_client.create_block(
        block, block_spec_id=block_spec.id, name="test"
    )
    return block_id


@pytest.fixture
async def local_storage_block(local_storage_block_id, orion_client):
    return await orion_client.read_block(local_storage_block_id)


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
                        if response.status_code == 200:
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
        # Cleanup the process
        try:
            process.terminate()
            await process.aclose()
            process.kill()
        except Exception:
            pass  # May already be terminated


@pytest.fixture
async def set_up_kv_storage(session, run_storage_server):
    """
    Use this fixture to make the distributed storage server the default
    (useful for distributed flow or task runner tests)
    """
    block_spec = await models.block_specs.create_block_spec(
        session=session,
        block_spec=KVServerStorageBlock.to_api_block_spec(),
        override=True,
    )

    block = await models.blocks.create_block(
        session=session,
        block=KVServerStorageBlock(
            api_address="http://127.0.0.1:1234/storage"
        ).to_api_block(name="test-storage-block", block_spec_id=block_spec.id),
    )

    await models.blocks.set_default_storage_block(session=session, block_id=block.id)
    await session.commit()
