from typing import Optional, Sequence, TypeVar, Union
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import actions, filters, sorting
from prefect.server.schemas.core import Artifact

T = TypeVar("T", bound=tuple)


@db_injector
async def _insert_into_artifact_collection(
    db: PrefectDBInterface,
    session: AsyncSession,
    artifact: Artifact,
    now: Optional[pendulum.DateTime] = None,
) -> orm_models.ArtifactCollection:
    """
    Inserts a new artifact into the artifact_collection table or updates it.
    """
    insert_values = artifact.model_dump_for_orm(
        exclude_unset=True, exclude={"id", "updated", "created"}
    )
    upsert_new_latest_id = (
        db.insert(orm_models.ArtifactCollection)
        .values(latest_id=artifact.id, updated=now, created=now, **insert_values)
        .on_conflict_do_update(
            index_elements=db.artifact_collection_unique_upsert_columns,
            set_=dict(
                latest_id=artifact.id,
                updated=now,
                **insert_values,
            ),
        )
    )

    await session.execute(upsert_new_latest_id)

    query = (
        sa.select(orm_models.ArtifactCollection)
        .where(
            sa.and_(
                orm_models.ArtifactCollection.key == artifact.key,
            )
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)

    model = result.scalar()

    if model is not None:
        if model.latest_id != artifact.id:
            raise ValueError(
                f"Artifact {artifact.id} was not inserted into the artifact collection"
                " table."
            )
    if model is None:
        raise ValueError(
            f"Artifact {artifact.id} was not inserted into the artifact collection"
            " table."
        )

    return model


@db_injector
async def _insert_into_artifact(
    db: PrefectDBInterface,
    session: AsyncSession,
    artifact: Artifact,
    now: Optional[pendulum.DateTime] = None,
) -> orm_models.Artifact:
    """
    Inserts a new artifact into the artifact table.
    """
    artifact_id = artifact.id
    insert_stmt = db.insert(orm_models.Artifact).values(
        created=now,
        updated=now,
        **artifact.model_dump_for_orm(exclude={"created", "updated"}),
    )
    await session.execute(insert_stmt)

    query = (
        sa.select(orm_models.Artifact)
        .where(orm_models.Artifact.id == artifact_id)
        .limit(1)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar_one()


async def create_artifact(
    session: AsyncSession,
    artifact: Artifact,
) -> orm_models.Artifact:
    now = pendulum.now("UTC")

    if artifact.key is not None:
        await _insert_into_artifact_collection(
            session=session, now=now, artifact=artifact
        )

    result = await _insert_into_artifact(
        session=session,
        now=now,
        artifact=artifact,
    )

    return result


async def read_latest_artifact(
    session: AsyncSession,
    key: str,
) -> Union[orm_models.ArtifactCollection, None]:
    """
    Reads the latest artifact by key.
    Args:
        session: A database session
        key: The artifact key
    Returns:
        Artifact: The latest artifact
    """
    latest_artifact_query = sa.select(orm_models.ArtifactCollection).where(
        orm_models.ArtifactCollection.key == key
    )
    result = await session.execute(latest_artifact_query)
    return result.scalar()


async def read_artifact(
    session: AsyncSession,
    artifact_id: UUID,
) -> Union[orm_models.Artifact, None]:
    """
    Reads an artifact by id.
    """

    query = sa.select(orm_models.Artifact).where(orm_models.Artifact.id == artifact_id)

    result = await session.execute(query)
    return result.scalar()


async def _apply_artifact_filters(
    query: Select[T],
    flow_run_filter: Optional[filters.FlowRunFilter] = None,
    task_run_filter: Optional[filters.TaskRunFilter] = None,
    artifact_filter: Optional[filters.ArtifactFilter] = None,
    deployment_filter: Optional[filters.DeploymentFilter] = None,
    flow_filter: Optional[filters.FlowFilter] = None,
) -> Select[T]:
    """Applies filters to an artifact query as a combination of EXISTS subqueries."""
    if artifact_filter:
        query = query.where(artifact_filter.as_sql_filter())

    if flow_filter or flow_run_filter or deployment_filter:
        flow_run_exists_clause = select(orm_models.FlowRun).where(
            orm_models.Artifact.flow_run_id == orm_models.FlowRun.id
        )
        if flow_run_filter:
            flow_run_exists_clause = flow_run_exists_clause.where(
                flow_run_filter.as_sql_filter()
            )

        if flow_filter:
            flow_run_exists_clause = flow_run_exists_clause.join(
                orm_models.Flow,
                orm_models.Flow.id == orm_models.FlowRun.flow_id,
            ).where(flow_filter.as_sql_filter())

        if deployment_filter:
            flow_run_exists_clause = flow_run_exists_clause.join(
                orm_models.Deployment,
                orm_models.Deployment.id == orm_models.FlowRun.deployment_id,
            ).where(deployment_filter.as_sql_filter())

        query = query.where(flow_run_exists_clause.exists())

    if task_run_filter:
        task_run_exists_clause = select(orm_models.TaskRun).where(
            orm_models.Artifact.task_run_id == orm_models.TaskRun.id
        )
        task_run_exists_clause = task_run_exists_clause.where(
            task_run_filter.as_sql_filter()
        )

        query = query.where(task_run_exists_clause.exists())

    return query


async def _apply_artifact_collection_filters(
    query: Select[T],
    flow_run_filter: Optional[filters.FlowRunFilter] = None,
    task_run_filter: Optional[filters.TaskRunFilter] = None,
    artifact_filter: Optional[filters.ArtifactCollectionFilter] = None,
    deployment_filter: Optional[filters.DeploymentFilter] = None,
    flow_filter: Optional[filters.FlowFilter] = None,
) -> Select[T]:
    """Applies filters to an artifact collection query as a combination of EXISTS subqueries."""
    if artifact_filter:
        query = query.where(artifact_filter.as_sql_filter())

    if flow_filter or flow_run_filter or deployment_filter:
        flow_run_exists_clause = select(orm_models.FlowRun).where(
            orm_models.ArtifactCollection.flow_run_id == orm_models.FlowRun.id
        )
        if flow_run_filter:
            flow_run_exists_clause = flow_run_exists_clause.where(
                flow_run_filter.as_sql_filter()
            )

        if flow_filter:
            flow_run_exists_clause = flow_run_exists_clause.join(
                orm_models.Flow,
                orm_models.Flow.id == orm_models.FlowRun.flow_id,
            ).where(flow_filter.as_sql_filter())

        if deployment_filter:
            flow_run_exists_clause = flow_run_exists_clause.join(
                orm_models.Deployment,
                orm_models.Deployment.id == orm_models.FlowRun.deployment_id,
            ).where(deployment_filter.as_sql_filter())

        query = query.where(flow_run_exists_clause.exists())

    if task_run_filter:
        task_run_exists_clause = select(orm_models.TaskRun).where(
            orm_models.ArtifactCollection.task_run_id == orm_models.TaskRun.id
        )
        task_run_exists_clause = task_run_exists_clause.where(
            task_run_filter.as_sql_filter()
        )

        query = query.where(task_run_exists_clause.exists())

    return query


async def read_artifacts(
    session: AsyncSession,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    artifact_filter: Optional[filters.ArtifactFilter] = None,
    flow_run_filter: Optional[filters.FlowRunFilter] = None,
    task_run_filter: Optional[filters.TaskRunFilter] = None,
    deployment_filter: Optional[filters.DeploymentFilter] = None,
    flow_filter: Optional[filters.FlowFilter] = None,
    sort: sorting.ArtifactSort = sorting.ArtifactSort.ID_DESC,
) -> Sequence[orm_models.Artifact]:
    """
    Reads artifacts.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit
        artifact_filter: Only select artifacts matching this filter
        flow_run_filter: Only select artifacts whose flow runs matching this filter
        task_run_filter: Only select artifacts whose task runs matching this filter
        deployment_filter: Only select artifacts whose flow runs belong to deployments matching this filter
        flow_filter: Only select artifacts whose flow runs belong to flows matching this filter
        work_pool_filter: Only select artifacts whose flow runs belong to work pools matching this filter
    """
    query = sa.select(orm_models.Artifact).order_by(sort.as_sql_sort())

    query = await _apply_artifact_filters(
        query,
        artifact_filter=artifact_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        flow_filter=flow_filter,
    )

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def read_latest_artifacts(
    session: AsyncSession,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    artifact_filter: Optional[filters.ArtifactCollectionFilter] = None,
    flow_run_filter: Optional[filters.FlowRunFilter] = None,
    task_run_filter: Optional[filters.TaskRunFilter] = None,
    deployment_filter: Optional[filters.DeploymentFilter] = None,
    flow_filter: Optional[filters.FlowFilter] = None,
    sort: sorting.ArtifactCollectionSort = sorting.ArtifactCollectionSort.ID_DESC,
) -> Sequence[orm_models.ArtifactCollection]:
    """
    Reads artifacts.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit
        artifact_filter: Only select artifacts matching this filter
        flow_run_filter: Only select artifacts whose flow runs matching this filter
        task_run_filter: Only select artifacts whose task runs matching this filter
        deployment_filter: Only select artifacts whose flow runs belong to deployments matching this filter
        flow_filter: Only select artifacts whose flow runs belong to flows matching this filter
        work_pool_filter: Only select artifacts whose flow runs belong to work pools matching this filter
    """
    query = sa.select(orm_models.ArtifactCollection).order_by(sort.as_sql_sort())
    query = await _apply_artifact_collection_filters(
        query,
        artifact_filter=artifact_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        flow_filter=flow_filter,
    )

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def count_artifacts(
    session: AsyncSession,
    artifact_filter: Optional[filters.ArtifactFilter] = None,
    flow_run_filter: Optional[filters.FlowRunFilter] = None,
    task_run_filter: Optional[filters.TaskRunFilter] = None,
    deployment_filter: Optional[filters.DeploymentFilter] = None,
    flow_filter: Optional[filters.FlowFilter] = None,
) -> int:
    """
    Counts artifacts.
    Args:
        session: A database session
        artifact_filter: Only select artifacts matching this filter
        flow_run_filter: Only select artifacts whose flow runs matching this filter
        task_run_filter: Only select artifacts whose task runs matching this filter
    """
    query = sa.select(sa.func.count(orm_models.Artifact.id))

    query = await _apply_artifact_filters(
        query,
        artifact_filter=artifact_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        flow_filter=flow_filter,
    )

    result = await session.execute(query)
    return result.scalar_one()


async def count_latest_artifacts(
    session: AsyncSession,
    artifact_filter: Optional[filters.ArtifactCollectionFilter] = None,
    flow_run_filter: Optional[filters.FlowRunFilter] = None,
    task_run_filter: Optional[filters.TaskRunFilter] = None,
    deployment_filter: Optional[filters.DeploymentFilter] = None,
    flow_filter: Optional[filters.FlowFilter] = None,
) -> int:
    """
    Counts artifacts.
    Args:
        session: A database session
        artifact_filter: Only select artifacts matching this filter
        flow_run_filter: Only select artifacts whose flow runs matching this filter
        task_run_filter: Only select artifacts whose task runs matching this filter
    """
    query = sa.select(sa.func.count(orm_models.ArtifactCollection.id))

    query = await _apply_artifact_collection_filters(
        query,
        artifact_filter=artifact_filter,
        flow_run_filter=flow_run_filter,
        task_run_filter=task_run_filter,
        deployment_filter=deployment_filter,
        flow_filter=flow_filter,
    )

    result = await session.execute(query)
    return result.scalar_one()


async def update_artifact(
    session: AsyncSession,
    artifact_id: UUID,
    artifact: actions.ArtifactUpdate,
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
    update_artifact_data = artifact.model_dump_for_orm(exclude_unset=True)

    update_artifact_stmt = (
        sa.update(orm_models.Artifact)
        .where(orm_models.Artifact.id == artifact_id)
        .values(**update_artifact_data)
    )

    artifact_result = await session.execute(update_artifact_stmt)

    update_artifact_collection_data = artifact.model_dump_for_orm(exclude_unset=True)
    update_artifact_collection_stmt = (
        sa.update(orm_models.ArtifactCollection)
        .where(orm_models.ArtifactCollection.latest_id == artifact_id)
        .values(**update_artifact_collection_data)
    )
    collection_result = await session.execute(update_artifact_collection_stmt)

    return artifact_result.rowcount + collection_result.rowcount > 0


async def delete_artifact(
    session: AsyncSession,
    artifact_id: UUID,
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
    artifact = await session.get(orm_models.Artifact, artifact_id)
    if artifact is None:
        return False

    is_latest_version = (
        await session.execute(
            sa.select(orm_models.ArtifactCollection)
            .where(orm_models.ArtifactCollection.key == artifact.key)
            .where(orm_models.ArtifactCollection.latest_id == artifact_id)
        )
    ).scalar_one_or_none() is not None

    if is_latest_version:
        next_latest_version = (
            await session.execute(
                sa.select(orm_models.Artifact)
                .where(orm_models.Artifact.key == artifact.key)
                .where(orm_models.Artifact.id != artifact_id)
                .order_by(orm_models.Artifact.created.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if next_latest_version is not None:
            set_next_latest_version = (
                sa.update(orm_models.ArtifactCollection)
                .where(orm_models.ArtifactCollection.key == artifact.key)
                .values(
                    latest_id=next_latest_version.id,
                    data=next_latest_version.data,
                    description=next_latest_version.description,
                    type=next_latest_version.type,
                    created=next_latest_version.created,
                    updated=next_latest_version.updated,
                    flow_run_id=next_latest_version.flow_run_id,
                    task_run_id=next_latest_version.task_run_id,
                    metadata_=next_latest_version.metadata_,
                )
            )
            await session.execute(set_next_latest_version)

        else:
            await session.execute(
                sa.delete(orm_models.ArtifactCollection)
                .where(orm_models.ArtifactCollection.key == artifact.key)
                .where(orm_models.ArtifactCollection.latest_id == artifact_id)
            )

    delete_stmt = sa.delete(orm_models.Artifact).where(
        orm_models.Artifact.id == artifact_id
    )

    result = await session.execute(delete_stmt)
    return result.rowcount > 0
