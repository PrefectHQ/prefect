"""
Utilities for injecting FastAPI dependencies.
"""
import logging

from fastapi import Depends, Header, HTTPException, status

from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.server import response_scoped_dependency


@response_scoped_dependency
async def get_session(db: OrionDBInterface = Depends(provide_database_interface)):
    """
    Dependency-injected database session.

    The context manager will automatically handle commits, rollbacks, and closing the
    connection.

    A `response_scoped_dependency` is used to ensure this session is closed before the
    response is returned to a client.
    """
    session = await db.session()
    async with session:
        async with session.begin():
            yield session


class CheckVersionCompatibility:
    """
    FastAPI Dependency used to check compatibility between the version of the api
    and a given request.

    Looks for the header 'X-PREFECT-API-VERSION' in the request and compares it
    to the api's version.
    """

    def __init__(self, api_version: str, logger: logging.Logger):
        self.api_version = api_version
        versions = [int(v) for v in api_version.split(".")]
        self.api_major = versions[0]
        self.api_minor = versions[1]
        self.api_patch = versions[2]

        self.logger = logger

    async def __call__(
        self,
        x_prefect_api_version: str = Header(None),
    ):
        request_version = x_prefect_api_version

        # if no version header, assume latest and continue
        if not request_version:
            return

        # parse version
        try:
            major, minor, patch = [int(v) for v in request_version.split(".")]
        except ValueError:
            self.logger.error(
                f"Invalid X-PREFECT-API-VERSION header format: '{request_version}'"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid X-PREFECT-API-VERSION header format."
                    f"Expected header in format 'x.y.z' but received {request_version}"
                ),
            )

        if (major, minor) != (self.api_major, self.api_minor) or (
            patch > self.api_patch
        ):
            self.logger.error(
                f"Received incompatible X-PREFECT-API-VERSION header: '{request_version}'"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Request specified API version {request_version} but this server"
                    f" only supports version {self.api_version} and below."
                ),
            )
