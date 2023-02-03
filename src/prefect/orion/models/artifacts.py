from uuid import UUID

import pendulum
import sqlalchemy as sa

from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.schemas.core import Artifact


@inject_db
async def create_artifact(
    session: sa.orm.Session, artifact: Artifact, db: OrionDBInterface, key: str = None
):
    now = pendulum.now("UTC")
    artifact_id = artifact.id
    insert_stmt = (await db.insert(db.Artifact)).values(
        created=now,
        updated=now,
        **artifact.dict(exclude={"created", "updated"}, shallow=True)
    )
    await session.execute(insert_stmt)

    query = (
        sa.select(db.Artifact)
        .where(db.Artifact.id == artifact_id)
        .limit(1)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    model = result.scalar()

    return model


@inject_db
async def read_artifact(
    session: sa.orm.Session,
    artifact_id: UUID,
    db: OrionDBInterface,
):
    """
    Reads an artifact by id.
    """

    query = sa.select(db.Artifact).where(db.Artifact.id == artifact_id)

    result = await session.execute(query)
    return result.scalar()
