"""
Utilities for injecting FastAPI dependencies.

FastAPI runs a sync dependency in a worker thread on every request. API routes
depend on the `a`-prefixed async variants of these helpers, which call the sync
helpers on the event loop.
"""

from __future__ import annotations

import logging
import re
from base64 import b64decode
from typing import Annotated, Any, Optional
from uuid import UUID

from docket import Docket as Docket_
from fastapi import Body, Depends, Header, HTTPException
from packaging.version import Version
from starlette.requests import Request

from prefect._internal.compatibility.starlette import status
from prefect.server import schemas
from prefect.settings import PREFECT_SERVER_API_DEFAULT_LIMIT


def provide_request_api_version(
    x_prefect_api_version: str = Header(None),
) -> Version | None:
    if not x_prefect_api_version:
        return

    # parse version
    try:
        _, _, _ = [int(v) for v in x_prefect_api_version.split(".")]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid X-PREFECT-API-VERSION header format.Expected header in format"
                f" 'x.y.z' but received {x_prefect_api_version}"
            ),
        )
    return Version(x_prefect_api_version)


async def aprovide_request_api_version(
    x_prefect_api_version: str = Header(None),
) -> Version | None:
    """Async variant of `provide_request_api_version` for API routes."""
    return provide_request_api_version(x_prefect_api_version)


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
        self.api_major: int = versions[0]
        self.api_minor: int = versions[1]
        self.api_patch: int = versions[2]
        self.logger = logger

    async def __call__(
        self,
        x_prefect_api_version: str = Header(None),
    ) -> None:
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


def LimitBody() -> Any:
    """
    A `fastapi.Depends` factory for pulling a `limit: int` parameter from the
    request body while determining the default from the current settings.
    """

    async def get_limit(
        limit: int = Body(
            None,
            description="Defaults to PREFECT_SERVER_API_DEFAULT_LIMIT if not provided.",
        ),
    ):
        default_limit = PREFECT_SERVER_API_DEFAULT_LIMIT.value()
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


async def aget_created_by(
    prefect_automation_id: Optional[UUID] = Header(None, include_in_schema=False),
    prefect_automation_name: Optional[str] = Header(None, include_in_schema=False),
) -> Optional[schemas.core.CreatedBy]:
    """Async variant of `get_created_by` for API routes."""
    return get_created_by(prefect_automation_id, prefect_automation_name)


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


async def aget_updated_by(
    prefect_automation_id: Optional[UUID] = Header(None, include_in_schema=False),
    prefect_automation_name: Optional[str] = Header(None, include_in_schema=False),
) -> Optional[schemas.core.UpdatedBy]:
    """Async variant of `get_updated_by` for API routes."""
    return get_updated_by(prefect_automation_id, prefect_automation_name)


def is_ephemeral_request(request: Request) -> bool:
    """
    A dependency that returns whether the request is to an ephemeral server.
    """
    return "ephemeral-prefect" in str(request.base_url)


async def ais_ephemeral_request(request: Request) -> bool:
    """Async variant of `is_ephemeral_request` for API routes."""
    return is_ephemeral_request(request)


PREFECT_CLIENT_USER_AGENT_PATTERN = re.compile(
    r"^prefect/(\d+\.\d+\.\d+(?:[a-z.+0-9]+)?) \(API \S+\)$"
)


def get_prefect_client_version(
    user_agent: Annotated[Optional[str], Header(include_in_schema=False)] = None,
) -> Optional[str]:
    """
    Attempts to parse out the Prefect client version from the User-Agent header.

    The Prefect client sets the User-Agent header like so:
      f"prefect/{prefect.__version__} (API {constants.SERVER_API_VERSION})"
    """
    if not user_agent:
        return None

    if client_version := PREFECT_CLIENT_USER_AGENT_PATTERN.match(user_agent):
        return client_version.group(1)
    return None


async def aget_prefect_client_version(
    user_agent: Annotated[Optional[str], Header(include_in_schema=False)] = None,
) -> Optional[str]:
    """Async variant of `get_prefect_client_version` for API routes."""
    return get_prefect_client_version(user_agent)


def docket(request: Request) -> Docket_:
    return request.app.state.docket


async def adocket(request: Request) -> Docket_:
    """Async variant of `docket` for API routes."""
    return docket(request)


Docket = Annotated[Docket_, Depends(adocket)]
