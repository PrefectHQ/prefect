from pydantic import conint

from prefect.orion.utilities.database import get_session_factory
from prefect.orion.utilities.schemas import PrefectBaseModel


async def get_session():
    """
    Dependency-injected database session.

    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            yield session


class Pagination(PrefectBaseModel):
    # max limit is 200
    limit: conint(ge=0, le=200) = 200
    offset: conint(ge=0) = 0
