"""
Routes for interacting with the Orion Data API.
"""

from pathlib import PosixPath
from uuid import uuid4

from fastapi import Request, Response, status

from prefect.orion.schemas.data import DataDocument, get_instance_data_location
from prefect.orion.serializers import FileSerializer, OrionSerializer
from prefect.orion.utilities.server import OrionRouter
from prefect.utilities.compat import asyncio_to_thread

router = OrionRouter(prefix="/data", tags=["Data Documents"])


@router.post("/persist", status_code=status.HTTP_201_CREATED)
async def create_datadoc(request: Request) -> DataDocument:
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
    file_datadoc = await asyncio_to_thread(
        DataDocument.encode, encoding=dataloc.scheme, data=data, path=path
    )

    return file_datadoc


@router.post("/retrieve")
async def read_datadoc(file_datadoc: DataDocument):
    """
    Exchange an orion data document for the data previously persisted
    """
    # Read data from the file system; once again do not use the dispatcher
    data = await asyncio_to_thread(FileSerializer.loads, file_datadoc.blob)

    return Response(content=data, media_type="application/octet-stream")
