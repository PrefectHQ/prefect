"""Schemas for _internal_ use within the Prefect server, but that would not be
appropriate for use on the API itself."""

from typing import Optional

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field

from prefect.server.schemas import actions, statuses


class InternalWorkPoolUpdate(actions.WorkPoolUpdate):
    status: Optional[statuses.WorkPoolStatus] = Field(default=None)
