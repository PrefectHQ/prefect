from typing import cast
from uuid import UUID

from uuid_extensions import uuid7 as _uuid7  # pyright: ignore[reportMissingTypeStubs]


def uuid7() -> UUID:
    return cast(UUID, _uuid7())


__all__ = ["uuid7"]
