from uuid import UUID
import sqlalchemy as sa
from fastapi import Depends, HTTPException, Path, Body, Response, status

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/data", tags=["Data Documents"])


@router.post("/")
async def create_data_document(
    datadoc: schemas.actions.DataDocumentCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.data.DataDocument:
    """
    Create a data document
    """
    nested = await session.begin_nested()
    # TODO: Determine how to handle failure? What failure cases are there?
    datadoc = await models.data.create_data_document(session=session, datadoc=datadoc)
    response.status_code = status.HTTP_201_CREATED
    return datadoc


@router.get("/{id}")
async def read_data_document(
    datadoc_id: UUID = Path(..., description="The data document id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.data.DataDocument:
    """
    Get a data document by id
    """
    data = await models.data.read_data_document(session=session, datadoc_id=datadoc_id)
    if not data:
        raise HTTPException(status_code=404, detail="Data document not found")
    return data
