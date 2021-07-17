import sqlalchemy as sa
from fastapi import Depends

from prefect.orion import models
from prefect.orion.api import schemas
from prefect.orion.utilities.server import get_session, OrionRouter

router = OrionRouter(prefix="/flows", tags=["flows"])


@router.post("/")
async def create_flow(
    flow: schemas.Flow, session: sa.orm.Session = Depends(get_session)
) -> schemas.Flow:
    return await models.flows.create_flow(session=session, name=flow.name)
