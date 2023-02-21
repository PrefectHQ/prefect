from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import select

from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import actions, filters, sorting
from prefect.server.schemas.core import Artifact


@inject_db
async def create_artifact(
    session: sa.orm.Session, artifact: Artifact, db: PrefectDBInterface, key: str = None
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
    db: PrefectDBInterface,
):
    """
    Reads an artifact by id.
    """

    query = sa.select(db.Artifact).where(db.Artifact.id == artifact_id)

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def _apply_artifact_filters(
    query,
    db: PrefectDBInterface,
    flow_run_filter: filters.FlowRunFilter = None,
    task_run_filter: filters.TaskRunFilter = None,
    artifact_filter: filters.ArtifactFilter = None,
):
    """Applies filters to an artifact query as a combination of EXISTS subqueries."""
    if artifact_filter:
        query = query.where(artifact_filter.as_sql_filter(db))

    if flow_run_filter:
        exists_clause = select(db.FlowRun).where(
            db.Artifact.flow_run_id == db.FlowRun.id
        )

        exists_clause = exists_clause.where(flow_run_filter.as_sql_filter(db))

        query = query.where(exists_clause.exists())

    if task_run_filter:
        exists_clause = select(db.TaskRun).where(
            db.Artifact.task_run_id == db.TaskRun.id
        )
        exists_clause = exists_clause.where(task_run_filter.as_sql_filter(db))

        query = query.where(exists_clause.exists())

    return query


@inject_db
async def read_artifacts(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    offset: int = None,
    limit: int = None,
    artifact_filter: filters.ArtifactFilter = None,
    flow_run_filter: filters.FlowRunFilter = None,
    task_run_filter: filters.TaskRunFilter = None,
    sort: sorting.ArtifactSort = sorting.ArtifactSort.ID_DESC,
):
    """
    Reads artifacts.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit
        artifact_filter: Only select artifacts matching this filter
        flow_run_filter: Only select artifacts whose flow runs matching this filter
        task_run_filter: Only select artifacts whose task runs matching this filter
    """

    query = sa.select(db.Artifact).order_by(sort.as_sql_sort(db))

    query = await _apply_artifact_filters(
        query,
        db=db,
        artifact_filter=artifact_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
    )

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_artifact(
    session: sa.orm.Session,
    artifact_id: UUID,
    artifact: actions.ArtifactUpdate,
    db: PrefectDBInterface,
) -> bool:
    """
    Updates an artifact by id.

    Args:
        session: A database session
        artifact_id (UUID): The artifact id to update
        artifact: An artifact model

    Returns:
        bool: True if the update was successful, False otherwise
    """
    update_data = artifact.dict(shallow=True, exclude_unset=True)

    update_stmt = (
        sa.update(db.Artifact)
        .where(db.Artifact.id == artifact_id)
        .values(**update_data)
    )

    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def delete_artifact(
    session: sa.orm.Session,
    artifact_id: UUID,
    db: PrefectDBInterface,
) -> bool:
    """
    Deletes an artifact by id.

    Args:
        session: A database session
        artifact_id (UUID): The artifact id to delete

    Returns:
        bool: True if the delete was successful, False otherwise
    """
    delete_stmt = sa.delete(db.Artifact).where(db.Artifact.id == artifact_id)

    result = await session.execute(delete_stmt)
    return result.rowcount > 0
