from contextlib import contextmanager
from typing import List

import sqlalchemy as sa
import xxhash
from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    func,
    insert,
    literal,
    select,
    update,
)
from sqlalchemy.orm import relationship

from prefect.orion.utilities.database import UUID, Base, engine


class Flow(Base):
    name = Column(String, nullable=False, unique=True)
    metadata = Column(JSON, server_default="{}", nullable=False)
    tags = Column(JSON, server_default="[]", nullable=False)
    parameters = Column(JSON, server_default="{}", nullable=False)


# TODO: add indexes
