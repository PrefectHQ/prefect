from prefect.logging import get_logger
from prefect.server.events.schemas.events import Event, ReceivedEvent
from prefect.server.events.services import event_persister
from prefect.server.services import task_run_recorder
from prefect.server.utilities.messaging.memory import MemoryMessage

logger = get_logger(__name__)


class EventsPipeline:
    @staticmethod
    def events_to_messages(events: list[Event]) -> list[MemoryMessage]:
        messages: list[MemoryMessage] = []
        for event in events:
            received_event = ReceivedEvent(**event.model_dump())
            message = MemoryMessage(
                data=received_event.model_dump_json().encode(),
                attributes={"id": str(event.id), "event": event.event},
            )
            messages.append(message)
        return messages

    async def process_events(self, events: list[Event]) -> None:
        logger.debug(
            f"STLOGGING: EVENTS PIPELINE: Processing {len(events)} events through pipeline"
        )
        for event in events:
            logger.debug(
                f"STLOGGING: EVENTS PIPELINE: Event to process: type='{event.event}', "
                f"id={event.id}, resource_id='{event.resource.get('prefect.resource.id', 'unknown')}'"
            )
        messages = self.events_to_messages(events)
        await self.process_messages(messages)

    async def process_messages(self, messages: list[MemoryMessage]) -> None:
        for message in messages:
            await self.process_message(message)

    async def process_message(self, message: MemoryMessage) -> None:
        """Process a single event message"""
        
        logger.debug(
            f"STLOGGING: EVENTS PIPELINE: Processing message: id={message.attributes.get('id', 'unknown')}, "
            f"event_type='{message.attributes.get('event', 'unknown')}'"
        )

        # TODO: Investigate if we want to include triggers/actions etc.
        async with task_run_recorder.consumer() as handler:
            logger.debug(
                f"STLOGGING: EVENTS PIPELINE: Sending message to task_run_recorder: "
                f"id={message.attributes.get('id', 'unknown')}"
            )
            await handler(message)

        async with event_persister.create_handler(batch_size=1) as handler:
            logger.debug(
                f"STLOGGING: EVENTS PIPELINE: Sending message to event_persister: "
                f"id={message.attributes.get('id', 'unknown')}"
            )
            await handler(message)
