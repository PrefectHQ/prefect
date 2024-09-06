from typing import Iterable

from prefect.logging import get_logger
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.messaging import Publisher, create_publisher
from prefect.settings import PREFECT_EVENTS_MAXIMUM_SIZE_BYTES

logger = get_logger(__name__)


async def publish(events: Iterable[ReceivedEvent]):
    """Send the given events as a batch via the default publisher"""
    async with create_event_publisher() as publisher:
        for event in events:
            await publisher.publish_event(event)


class EventPublisher(Publisher):
    _publisher: Publisher

    def __init__(self, publisher: Publisher = None):
        self._publisher = publisher

    async def __aenter__(self):
        await self._publisher.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self._publisher.__aexit__(*args)

    async def publish_data(self, data: bytes, attributes: dict):
        await self._publisher.publish_data(data, attributes)

    async def publish_event(self, event: ReceivedEvent):
        """
        Publishes the given events

        Args:
            event: the event to publish
        """
        encoded = event.model_dump_json().encode()
        if len(encoded) > PREFECT_EVENTS_MAXIMUM_SIZE_BYTES.value():
            logger.warning(
                "Refusing to publish event of size %s",
                extra={
                    "event_id": str(event.id),
                    "event": event.event[:100],
                    "length": len(encoded),
                },
            )
            return

        logger.debug(
            "Publishing event: %s with id: %s for resource: %s",
            event.event,
            event.id,
            event.resource.get("prefect.resource.id"),
        )
        await self.publish_data(
            encoded,
            {
                "id": str(event.id),
                "event": event.event,
            },
        )


def create_event_publisher() -> EventPublisher:
    publisher = create_publisher(topic="events", deduplicate_by="id")
    return EventPublisher(publisher=publisher)


def create_actions_publisher() -> Publisher:
    return create_publisher(topic="actions", deduplicate_by=None)
