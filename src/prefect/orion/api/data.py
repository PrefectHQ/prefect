"""
Routes for interacting with the Orion Data API.
"""
from pathlib import PosixPath
from uuid import uuid4

import fsspec
from fastapi import Request, Response, status, HTTPException

from prefect.orion.schemas.data import get_instance_data_location
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.orion.utilities.server import OrionRouter
from prefect.utilities.compat import asyncio_to_thread

router = OrionRouter(prefix="/data", tags=["Data Documents"])


class PersistenceID(PrefectBaseModel):
    id: str


@router.post("/persist", status_code=status.HTTP_201_CREATED)
async def persist_data(request: Request) -> PersistenceID:
    """
    Persist data as a file and return a reference to the file location.
    """
    data = await request.body()

    # Get the configured data location
    dataloc = get_instance_data_location()

    # Generate a path to write the data
    identifier = uuid4().hex
    path = PosixPath(dataloc.base_path).joinpath(identifier).absolute()
    path = f"{dataloc.scheme}://{path}"

    # Write the data to the path and create a file system document
    await asyncio_to_thread(write_blob, blob=data, path=path)

    return PersistenceID(id=identifier)


@router.post("/retrieve")
async def read_data(identifier: PersistenceID):
    """
    Read data at the provided file location.
    """
    identifier = identifier.id
    if len(PosixPath(identifier).parts) > 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid file identifier"
        )

    # Read data from the file system
    dataloc = get_instance_data_location()
    path = PosixPath(dataloc.base_path).joinpath(identifier).absolute()
    data = await asyncio_to_thread(read_blob, path)

    return Response(content=data, media_type="application/octet-stream")


def write_blob(blob: bytes, path: PosixPath) -> bool:
    """Write a blob to a file path."""
    with fsspec.open(path, mode="wb") as fp:
        fp.write(blob)
    return True


def read_blob(path: str) -> bytes:
    """Read a blob from a file path."""
    with fsspec.open(path, mode="rb") as fp:
        blob = fp.read()
    return blob
