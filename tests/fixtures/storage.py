from multiprocessing import Process
from typing import Any
from uuid import uuid4

import httpx
import pytest
import uvicorn
from fastapi import Body, FastAPI

from prefect.blocks.core import register_block
from prefect.blocks.storage import StorageBlock
from prefect.orion import models
from prefect.orion.schemas.actions import BlockCreate, BlockSpecCreate

app = FastAPI()


STORAGE = {}


@app.get("/{key}")
async def read_key(key) -> str:
    return STORAGE[key]


@app.post("/{key}")
async def write_key(key, value: str = Body(...)):
    STORAGE[key] = value


def run_storage_server():
    uvicorn.run(app, host="0.0.0.0", port=1234)


@pytest.fixture(autouse=True, scope="session")
def run_storage_server():
    proc = Process(target=run_storage_server, args=(), daemon=True)
    proc.start()
    yield
    proc.kill()


@register_block("inmemory-storage-block")
class InMemoryStorageBlock(StorageBlock):

    api_address: str

    async def write(self, data):
        key = str(uuid4())
        async with httpx.AsyncClient() as client:
            await client.post(f"{self.api_address}/{key}", json=data)
        return key

    async def read(self, key):
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.api_address}/{key}")
        return response.json()


@pytest.fixture(autouse=True)
async def set_up_in_memory_storage_block(session):
    block_spec = await models.block_specs.create_block_spec(
        session=session,
        block_spec=BlockSpecCreate(
            name="InMemoryStorageBlock", version="1", type="STORAGE", fields=dict()
        ),
    )

    block = await models.blocks.create_block(
        session=session,
        block=BlockCreate(
            name="InMemoryStorageBlock",
            data=dict(api_address="http://0.0.0.0:1234"),
            block_spec_id=block_spec.id,
        ),
    )

    await models.blocks.set_default_storage_block(session=session, block_id=block.id)
