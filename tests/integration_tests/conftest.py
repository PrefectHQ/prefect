import pendulum
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from prefect.orion.utilities.database import Base, get_engine, get_session_factory
from prefect import settings
from prefect.orion import models, schemas
import logging
import asyncio
import inspect

import pytest


@pytest.fixture
async def database_session(database_engine):
    OrionSession = get_session_factory(database_engine)
    yield OrionSession()
