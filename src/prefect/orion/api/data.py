from pathlib import PosixPath
from uuid import uuid4
from fastapi import Response, status

from prefect.orion.schemas.data import (
    OrionDataDocument,
    FileSystemDataDocument,
    get_instance_data_location,
    Base64String,
)
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/data", tags=["Data Documents"])


@router.post("/persist", status_code=status.HTTP_201_CREATED)
async def create_datadoc(
    data: Base64String,
) -> OrionDataDocument:
    """
    Exchange data for an orion data document
    """
    data_bytes = data.to_bytes()

    # Get the configured data location
    dataloc = get_instance_data_location()

    # Generate a path to write the data
    path = PosixPath(dataloc.base_path).joinpath(uuid4().hex).absolute()
    path = f"{dataloc.scheme}://{path}"

    # Write the data to the path and create a file system document
    fs_datadoc = FileSystemDataDocument.create(
        (path, data_bytes), encoding=dataloc.scheme
    )

    # Return an Orion datadoc to show that it should be resolved by GET /data
    orion_datadoc = OrionDataDocument.create(fs_datadoc)

    return orion_datadoc


@router.post("/retrieve")
async def read_datadoc(datadoc: OrionDataDocument) -> Base64String:
    """
    Exchange an orion data document for the data previously persisted
    """
    if datadoc.encoding != "orion":
        raise ValueError(
            f"Invalid encoding: {datadoc.encoding!r}. Only 'orion' data documents can "
            "be retrieved from the Orion API."
        )

    fs_datadoc = datadoc.read()
    # Unpack the path, bytes tuple returned by `FileSystemDataDocument`
    _, data_bytes = fs_datadoc.read()

    return Base64String.from_bytes(data_bytes)
