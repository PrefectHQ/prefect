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

from prefect.orion import models
from prefect.orion.api.server import validation_exception_handler
from prefect.orion.schemas.actions import BlockCreate, BlockSpecCreate

app = FastAPI(exception_handlers={RequestValidationError: validation_exception_handler})

STORAGE = {}


@app.get("/storage/{key}")
async def read_key(key: str):
    result = STORAGE.get(key)
    return result


@app.post("/storage/{key}")
async def write_key(key, value: Optional[Any] = Body(None)):
    STORAGE[key] = value


@app.get("/debug")
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
            "tests.fixtures.storage:app",
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
        block_spec=BlockSpecCreate(
            name="kv-server-storage-block", version="1.0", type="STORAGE", fields=dict()
        ),
    )

    block = await models.blocks.create_block(
        session=session,
        block=BlockCreate(
            name="test-storage-block",
            data=dict(api_address="http://127.0.0.1:1234/storage"),
            block_spec_id=block_spec.id,
        ),
    )

    await models.blocks.set_default_storage_block(session=session, block_id=block.id)
    await session.commit()
