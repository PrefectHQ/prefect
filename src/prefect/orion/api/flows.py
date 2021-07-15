from fastapi import Depends
from prefect.orion.api import schemas, app
from prefect.orion.utilities.server import get_session
from prefect.orion import models
import sqlalchemy as sa


@app.post("/flows/", response_model=schemas.Flow)
def create_flow(flow: schemas.Flow, session: sa.orm.Session = Depends(get_session)):
    return models.flows.create_flow(session=session, name=flow.name)
