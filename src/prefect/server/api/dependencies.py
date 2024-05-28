"""
Utilities for injecting FastAPI dependencies.
"""

import logging
from base64 import b64decode
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Header, HTTPException, status
from packaging.version import Version
from starlette.requests import Request

from prefect.server import schemas
from prefect.settings import PREFECT_API_DEFAULT_LIMIT


def provide_request_api_version(x_prefect_api_version: str = Header(None)):
    if not x_prefect_api_version:
        return

    # parse version
    try:
        major, minor, patch = [int(v) for v in x_prefect_api_version.split(".")]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid X-PREFECT-API-VERSION header format.Expected header in format"
                f" 'x.y.z' but received {x_prefect_api_version}"
            ),
        )
    return Version(x_prefect_api_version)


class EnforceMinimumAPIVersion:
    """
    FastAPI Dependency used to check compatibility between the version of the api
    and a given request.

    Looks for the header 'X-PREFECT-API-VERSION' in the request and compares it
    to the api's version. Rejects requests that are lower than the minimum version.
    """

    def __init__(self, minimum_api_version: str, logger: logging.Logger):
        self.minimum_api_version = minimum_api_version
        versions = [int(v) for v in minimum_api_version.split(".")]
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
            await self._notify_of_invalid_value(request_version)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid X-PREFECT-API-VERSION header format."
                    f"Expected header in format 'x.y.z' but received {request_version}"
                ),
            )

        if (major, minor, patch) < (self.api_major, self.api_minor, self.api_patch):
            await self._notify_of_outdated_version(request_version)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The request specified API version {request_version} but this "
                    f"server requires version {self.minimum_api_version} or higher."
                ),
            )

    async def _notify_of_invalid_value(self, request_version: str):
        self.logger.error(
            f"Invalid X-PREFECT-API-VERSION header format: '{request_version}'"
        )

    async def _notify_of_outdated_version(self, request_version: str):
        self.logger.error(
            f"X-PREFECT-API-VERSION header specifies version '{request_version}' "
            f"but minimum allowed version is '{self.minimum_api_version}'"
        )


def LimitBody() -> Depends:
    """
    A `fastapi.Depends` factory for pulling a `limit: int` parameter from the
    request body while determining the default from the current settings.
    """

    def get_limit(
        limit: int = Body(
            None,
            description="Defaults to PREFECT_API_DEFAULT_LIMIT if not provided.",
        ),
    ):
        default_limit = PREFECT_API_DEFAULT_LIMIT.value()
        limit = limit if limit is not None else default_limit
        if not limit >= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid limit: must be greater than or equal to 0.",
            )
        if limit > default_limit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid limit: must be less than or equal to {default_limit}.",
            )
        return limit

    return Depends(get_limit)


def get_created_by(
    prefect_automation_id: Optional[UUID] = Header(None, include_in_schema=False),
    prefect_automation_name: Optional[str] = Header(None, include_in_schema=False),
) -> Optional[schemas.core.CreatedBy]:
    """A dependency that returns the provenance information to use when creating objects
    during this API call."""
    if prefect_automation_id and prefect_automation_name:
        try:
            display_value = b64decode(prefect_automation_name.encode()).decode()
        except Exception:
            display_value = None

        if display_value:
            return schemas.core.CreatedBy(
                id=prefect_automation_id,
                type="AUTOMATION",
                display_value=display_value,
            )

    return None


def get_updated_by(
    prefect_automation_id: Optional[UUID] = Header(None, include_in_schema=False),
    prefect_automation_name: Optional[str] = Header(None, include_in_schema=False),
) -> Optional[schemas.core.UpdatedBy]:
    """A dependency that returns the provenance information to use when updating objects
    during this API call."""
    if prefect_automation_id and prefect_automation_name:
        return schemas.core.UpdatedBy(
            id=prefect_automation_id,
            type="AUTOMATION",
            display_value=prefect_automation_name,
        )

    return None


def is_ephemeral_request(request: Request):
    """
    A dependency that returns whether the request is to an ephemeral server.
    """
    return "ephemeral-prefect" in str(request.base_url)
