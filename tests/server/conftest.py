import pytest

from prefect.server.utilities.messaging import create_cache
from prefect.server.utilities.messaging.memory import Topic
from prefect.settings import (
    PREFECT_MESSAGING_BROKER,
    PREFECT_MESSAGING_CACHE,
    temporary_settings,
)

# Use the in-memory implementation of the cache and message broker for server testing


@pytest.fixture(autouse=True)
def events_configuration():
    with temporary_settings(
        {
            PREFECT_MESSAGING_CACHE: "prefect.server.utilities.messaging.memory",
            PREFECT_MESSAGING_BROKER: "prefect.server.utilities.messaging.memory",
        }
    ):
        yield


@pytest.fixture(autouse=True)
def clear_topics(events_configuration: None):
    Topic.clear_all()
    yield
    Topic.clear_all()


@pytest.fixture(autouse=True)
async def reset_recently_seen_messages(events_configuration: None):
    cache = create_cache()
    await cache.clear_recently_seen_messages()
    yield
    await cache.clear_recently_seen_messages()
