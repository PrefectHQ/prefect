import subprocess
import sys

import pytest
from fastapi import Body, FastAPI
from fastapi.exceptions import RequestValidationError

from prefect.orion import models
from prefect.orion.api.server import validation_exception_handler
from prefect.orion.schemas.actions import BlockCreate, BlockSpecCreate

app = FastAPI(exception_handlers={RequestValidationError: validation_exception_handler})


STORAGE = {}


@app.get("/{key}")
async def read_key(key: str) -> str:
    return STORAGE[key]


@app.post("/{key}")
async def write_key(key, value: str = Body(...)):
    STORAGE[key] = value


@pytest.fixture(autouse=True, scope="session")
def run_storage_server():
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
        yield
    finally:
        process.terminate()
        process.kill()


@pytest.fixture(autouse=True)
async def set_up_in_memory_storage_block(session):
    block_spec = await models.block_specs.create_block_spec(
        session=session,
        block_spec=BlockSpecCreate(
            name="kv-storage-block", version="1", type="STORAGE", fields=dict()
        ),
    )

    block = await models.blocks.create_block(
        session=session,
        block=BlockCreate(
            name="kv-storage-block",
            data=dict(api_address="http://127.0.0.1:1234"),
            block_spec_id=block_spec.id,
        ),
    )

    await models.blocks.set_default_storage_block(session=session, block_id=block.id)
