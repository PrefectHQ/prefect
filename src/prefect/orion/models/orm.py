from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy import JSON, Column, Integer, String
from sqlalchemy.orm import relationship

from prefect.orion.utilities.database import UUID, Base, engine


class Flow(Base):
    name = Column(String, nullable=False, unique=True)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    parameters = Column(JSON, server_default="{}", default=dict, nullable=False)


# TODO: add indexes
