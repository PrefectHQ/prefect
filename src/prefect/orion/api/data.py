from pathlib import PosixPath
from uuid import uuid4
from fastapi import status, Request, Response
from typing import Any

from prefect.orion.schemas.data import (
    OrionDataDocument,
    FileSystemDataDocument,
    get_instance_data_location,
)
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/data", tags=["Data Documents"])


@router.post("/persist", status_code=status.HTTP_201_CREATED)
async def create_datadoc(request: Request) -> OrionDataDocument:
    """
    Exchange data for an orion data document
    """
    data = await request.body()

    # Get the configured data location
    dataloc = get_instance_data_location()

    # Generate a path to write the data
    path = PosixPath(dataloc.base_path).joinpath(uuid4().hex).absolute()
    path = f"{dataloc.scheme}://{path}"

    # Write the data to the path and create a file system document
    fs_datadoc = FileSystemDataDocument.create(data, encoding=dataloc.scheme, path=path)

    # Return an Orion datadoc to show that it should be resolved by GET /data
    orion_datadoc = OrionDataDocument.create(fs_datadoc)

    return orion_datadoc


@router.post("/retrieve")
async def read_datadoc(datadoc: OrionDataDocument):
    """
    Exchange an orion data document for the data previously persisted
    """
    if datadoc.encoding != "orion":
        raise ValueError(
            f"Invalid encoding: {datadoc.encoding!r}. Only 'orion' data documents can "
            "be retrieved from the Orion API."
        )

    fs_datadoc = datadoc.read()

    # Read from the file system
    data = fs_datadoc.read()

    return Response(content=data, media_type="application/octet-stream")
