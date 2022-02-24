"""
A small distributed storage API
"""
import subprocess
import sys
import time
from typing import Any, Optional

import pytest
from fastapi import Body, FastAPI
from fastapi.exceptions import RequestValidationError

from prefect.orion.api.server import validation_exception_handler

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
    # ensure the server has time to start
    time.sleep(0.5)
    try:
        yield
    finally:
        process.terminate()
        process.kill()
