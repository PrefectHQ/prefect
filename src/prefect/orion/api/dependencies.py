from prefect.orion.utilities.database import OrionAsyncSession
from pydantic import BaseModel, conint


async def get_session():
    """
    Dependency-injected database session.

    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    async with OrionAsyncSession.begin() as session:
        yield session


class Pagination(BaseModel):
    # max limit is 200
    limit: conint(ge=0, le=200) = 200
    offset: conint(ge=0) = 0
