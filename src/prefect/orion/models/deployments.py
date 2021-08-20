from uuid import UUID
from typing import List
import sqlalchemy as sa
from sqlalchemy import select, delete

from prefect.orion.models import orm
from prefect.orion import schemas


async def create_deployment(
    session: sa.orm.Session, deployment: schemas.core.Deployment
) -> orm.Deployment:
    """Creates a new deployment

    Args:
        session (sa.orm.Session): a database session
        deployment (schemas.core.Deployment): a deployment model

    Returns:
        orm.Deployment: the newly-created deployment

    Raises:
        sqlalchemy.exc.IntegrityError: if a deployment with the same name already exists

    """
    model = orm.Deployment(**deployment.dict(shallow=True))
    session.add(model)
    await session.flush()
    return model


async def read_deployment(
    session: sa.orm.Session, deployment_id: UUID
) -> orm.Deployment:
    """Reads a deployment by id

    Args:
        session (sa.orm.Session): A database session
        deployment_id (str): a deployment id

    Returns:
        orm.Deployment: the deployment
    """
    return await session.get(orm.Deployment, deployment_id)


async def read_deployments(
    session: sa.orm.Session,
    offset: int = None,
    limit: int = None,
) -> List[orm.Deployment]:
    """Read deployments

    Args:
        session (sa.orm.Session): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[orm.Deployment]: deployments
    """

    query = select(orm.Deployment).order_by(orm.Deployment.id)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_deployment(session: sa.orm.Session, deployment_id: UUID) -> bool:
    """Delete a deployment by id

    Args:
        session (sa.orm.Session): A database session
        deployment_id (str): a deployment id

    Returns:
        bool: whether or not the deployment was deleted
    """
    result = await session.execute(
        delete(orm.Deployment).where(orm.Deployment.id == deployment_id)
    )
    return result.rowcount > 0
