from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import select

from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import actions, filters, sorting
from prefect.server.schemas.core import Artifact


@inject_db
async def _insert_into_artifact_collection(
    session: sa.orm.Session,
    key: str,
    artifact_id: UUID,
    db: PrefectDBInterface,
    now: pendulum.DateTime = None,
):
    """
    Inserts a new artifact into the artifact_collection table or updates it.
    """
    upsert_new_latest_id = (
        (await db.insert(db.ArtifactCollection))
        .values(
            key=key,
            latest_id=artifact_id,
            created=now,
            updated=now,
        )
        .on_conflict_do_update(
            index_elements=db.artifact_collection_unique_upsert_columns,
            set_=dict(
                latest_id=artifact_id,
                updated=now,
            ),
        )
    )

    await session.execute(upsert_new_latest_id)

    query = (
        sa.select(db.ArtifactCollection)
        .where(
            sa.and_(
                db.ArtifactCollection.key == key,
                db.ArtifactCollection.latest_id == artifact_id,
            )
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)

    model = result.scalar()

    if model is not None:
        if model.latest_id != artifact_id:
            raise ValueError(
                f"Artifact {artifact_id} was not inserted into the artifact collection"
                " table."
            )

    return model


@inject_db
async def _insert_into_artifact(
    session: sa.orm.Session,
    artifact: Artifact,
    db: PrefectDBInterface,
    now: pendulum.DateTime = None,
) -> Artifact:
    """
    Inserts a new artifact into the artifact table.
    """
    artifact_id = artifact.id
    insert_stmt = (await db.insert(db.Artifact)).values(
        created=now,
        updated=now,
        **artifact.dict(exclude={"created", "updated"}, shallow=True),
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
async def create_artifact(
    session: sa.orm.Session,
    artifact: Artifact,
    db: PrefectDBInterface,
):
    now = pendulum.now("UTC")

    if artifact.key is not None:
        await _insert_into_artifact_collection(
            session=session, key=artifact.key, now=now, db=db, artifact_id=artifact.id
        )

    result = await _insert_into_artifact(
        session=session,
        now=now,
        db=db,
        artifact=artifact,
    )

    return result


@inject_db
async def read_latest_artifact(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    key: str,
):
    """
    Reads the latest artifact by key.
    Args:
        session: A database session
        key: The artifact key
    Returns:
        Artifact: The latest artifact
    """
    latest_id_query = (
        sa.select(db.ArtifactCollection.latest_id)
        .where(db.ArtifactCollection.key == key)
        .limit(1)
    )
    latest_id = await session.execute(latest_id_query)
    latest_id_scalar = latest_id.scalar()

    latest_artifact_query = sa.select(db.Artifact).where(
        db.Artifact.id == latest_id_scalar
    )
    result = await session.execute(latest_artifact_query)

    return result.scalar()


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

    The ArtifactCollection table is used to track the latest version of an artifact
    by key. If we are deleting the latest version of an artifact from the Artifact
    table, we need to first update the latest version referenced in ArtifactCollection
    so that it points to the next latest version of the artifact.

    Example:
    If we have the following artifacts in Artifact:
    - key: "foo", id: 1, created: 2020-01-01
    - key: "foo", id: 2, created: 2020-01-02
    - key: "foo", id: 3, created: 2020-01-03

    the ArtifactCollection table has the following entry:
    - key: "foo", latest_id: 3

    If we delete the artifact with id 3, we need to update the latest version of the
    artifact with key "foo" to be the artifact with id 2.

    Args:
        session: A database session
        artifact_id (UUID): The artifact id to delete

    Returns:
        bool: True if the delete was successful, False otherwise
    """
    artifact = await session.get(db.Artifact, artifact_id)
    if artifact is None:
        return False

    is_latest_version = (
        await session.execute(
            sa.select(db.ArtifactCollection)
            .where(db.ArtifactCollection.key == artifact.key)
            .where(db.ArtifactCollection.latest_id == artifact_id)
        )
    ).scalar_one_or_none() is not None

    if is_latest_version:
        next_latest_version = (
            await session.execute(
                sa.select(db.Artifact)
                .where(db.Artifact.key == artifact.key)
                .where(db.Artifact.id != artifact_id)
                .order_by(db.Artifact.created.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if next_latest_version is not None:
            set_next_latest_version = (
                sa.update(db.ArtifactCollection)
                .where(db.ArtifactCollection.key == artifact.key)
                .values(latest_id=next_latest_version.id)
            )
            await session.execute(set_next_latest_version)

        else:
            await session.execute(
                sa.delete(db.ArtifactCollection)
                .where(db.ArtifactCollection.key == artifact.key)
                .where(db.ArtifactCollection.latest_id == artifact_id)
            )

    delete_stmt = sa.delete(db.Artifact).where(db.Artifact.id == artifact_id)

    result = await session.execute(delete_stmt)
    return result.rowcount > 0
