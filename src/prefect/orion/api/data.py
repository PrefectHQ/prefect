from pathlib import PosixPath
from uuid import uuid4
from fastapi import Response, status

from prefect.orion.data import (
    get_instance_data_location,
    resolve_orion_datadoc,
    write_blob,
)
from prefect.orion.schemas.data import DataDocument
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/data", tags=["Data Documents"])


@router.post("/put")
async def create_orion_datadoc(
    datadoc: DataDocument,
    response: Response,
) -> DataDocument:
    """
    Exchange a data document for an Orion data document
    """
    # Retrieve the configured data location
    dataloc = get_instance_data_location()

    # Generate a path to write the data
    path = str(PosixPath(dataloc.base_path).joinpath(uuid4().hex).absolute())

    # Write the datadoc as a blob to `path`
    await write_blob(datadoc.json().encode(), dataloc.scheme, path)

    # Generate a new datadoc with the location
    loc_datadoc = DataDocument(encoding=dataloc.scheme, blob=path.encode())

    # Return an Orion datadoc to show that it should be resolved by GET /data
    orion_datadoc = DataDocument(encoding="orion", blob=loc_datadoc.json().encode())

    response.status_code = status.HTTP_201_CREATED
    return orion_datadoc


@router.post("/get")
async def get_user_datadoc(datadoc: DataDocument) -> DataDocument:
    """
    Resolve a data document that Orion is responsible for into the original data
    document provided by the user
    """
    if datadoc.encoding != "orion":
        raise ValueError(
            f"Invalid encoding: {datadoc.encoding!r}. Only 'orion' data documents can "
            "be retrieved from the Orion API."
        )

    return await resolve_orion_datadoc(datadoc)
