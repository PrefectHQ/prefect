from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import schemas
from prefect.orion.data import get_instance_data_location, write_datadoc_blob
from prefect.orion.models import orm


async def create_data_document(
    session: sa.orm.Session, datadoc: schemas.actions.DataDocumentCreate
) -> orm.DataDocument:
    """Creates a new data document

    Args:
        session (sa.orm.Session): a database session
        datadoc (schemas.actions.DataDocumentCreate): a data document model

    Returns:
        orm.DataDocument: the newly-created data document
    """
    # Retrieve the data location
    dataloc = get_instance_data_location()

    # Generate a path to store the data at
    datadoc = schemas.data.DataDocument(**datadoc.dict(shallow=True), id=uuid4())
    datadoc.name = datadoc.name or datadoc.id.hex
    datadoc.path = f"{dataloc.base_path}/{datadoc.name}"

    # If not storing the data in the database, write to the external location and
    # drop the blob from the database object
    if dataloc.scheme != "db":
        # TODO: Submit this write to a background worker so we can return before
        #       waiting for the data to be written
        await write_datadoc_blob(datadoc, dataloc)
        datadoc.blob = None

    # Insert
    model = orm.DataDocument(**datadoc.dict(shallow=True))
    session.add(model)
    await session.flush()

    return model


async def read_data_document(
    session: sa.orm.Session, datadoc_id: UUID
) -> orm.DataDocument:
    """Read a data document by id

    Args:
        session (sa.orm.Session): a database session
        datadoc_id (str): the data document id

    Returns:
        orm.DataDocument: the data document
    """
    model = await session.get(orm.DataDocument, datadoc_id)
    return model
