from pathlib import PosixPath
from uuid import uuid4
from fastapi import status, Request, Response

from prefect.orion.schemas.data import (
    DataDocument,
    get_instance_data_location,
)
from prefect.orion.serializers import lookup_serializer, FileSerializer
from prefect.orion.utilities.server import OrionRouter
from prefect.orion.utilities.asyncio import run_in_threadpool

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
    file_datadoc = await run_in_threadpool(
        DataDocument.encode, encoding=dataloc.scheme, data=data, path=path
    )

    # Return an Orion datadoc to show that it should be resolved by GET /data
    orion_datadoc = DataDocument.encode(encoding="orion", data=file_datadoc)

    return orion_datadoc


@router.post("/retrieve")
async def read_datadoc(orion_datadoc: DataDocument):
    """
    Exchange an orion data document for the data previously persisted
    """
    if orion_datadoc.encoding != "orion":
        raise ValueError(
            f"Invalid encoding: {orion_datadoc.encoding!r}. Only 'orion' data documents can "
            "be retrieved from the Orion API."
        )

    file_datadoc = orion_datadoc.decode()

    # Ensure we are not going to decode something dangerously
    if lookup_serializer(file_datadoc.encoding) != FileSerializer:
        raise ValueError("Bad document encoding")

    # Read from the file system
    data = await run_in_threadpool(file_datadoc.decode)

    return Response(content=data, media_type="application/octet-stream")
