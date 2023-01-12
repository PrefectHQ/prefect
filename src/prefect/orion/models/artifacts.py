import sqlalchemy as sa

from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.schemas.core import Artifact


@inject_db
async def create_artifact(
    session: sa.orm.Session, artifact: Artifact, db: OrionDBInterface, key: str = None
):
    artifact_payload = {"artifact_data": data}
    if key:
        artifact_payload["key"] = key

    artifact_id = artifact.id

    insert_stmt = (await db.insert(db.Artifact)).values(
        **artifact.dict(shallow=True, exclude_unset=True)
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
