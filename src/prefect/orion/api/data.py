"""
Routes for interacting with the Orion Data API.
"""
from pathlib import PosixPath
from uuid import uuid4

import fsspec
from fastapi import Request, Response, status

from prefect.orion.schemas.data import get_instance_data_location
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.orion.utilities.server import OrionRouter
from prefect.utilities.compat import asyncio_to_thread

router = OrionRouter(prefix="/data", tags=["Data Documents"])


class PersistencePath(PrefectBaseModel):
    path: str


@router.post("/persist", status_code=status.HTTP_201_CREATED)
async def persist_data(request: Request) -> PersistencePath:
    """
    Persist data as a file and return a reference to the file location.
    """
    data = await request.body()

    # Get the configured data location
    dataloc = get_instance_data_location()

    # Generate a path to write the data
    path = PosixPath(dataloc.base_path).joinpath(uuid4().hex).absolute()
    path = f"{dataloc.scheme}://{path}"

    # Write the data to the path and create a file system document
    await asyncio_to_thread(write_blob, blob=data, path=path)

    return PersistencePath(path=path)


@router.post("/retrieve")
async def read_data(path: PersistencePath):
    """
    Read data at the provided file location.
    """
    # Read data from the file system
    data = await asyncio_to_thread(read_blob, path.path)

    return Response(content=data, media_type="application/octet-stream")


def write_blob(blob: bytes, path: PersistencePath) -> bool:
    """Write a blob to a file path."""
    with fsspec.open(path, mode="wb") as fp:
        fp.write(blob)
    return True


def read_blob(path: str) -> bytes:
    """Read a blob from a file path."""
    with fsspec.open(path, mode="rb") as fp:
        blob = fp.read()
    return blob
