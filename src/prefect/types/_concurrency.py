from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConcurrencyLeaseHolder(BaseModel):
    """Model for validating concurrency lease holder information."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    type: Literal["flow_run", "task_run", "deployment"]
    id: UUID
