from fastapi import Request
from prefect.orion.utilities.database import Session


def get_session():
    """
    Dependency-injected database session.

    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    with Session.begin() as session:
        yield session
