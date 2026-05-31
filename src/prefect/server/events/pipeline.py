from prefect.server.events import triggers
from prefect.server.events.ordering import EventArrivedEarly
from prefect.server.events.schemas.events import Event, ReceivedEvent
from prefect.server.events.services import event_persister
from prefect.server.services import task_run_recorder
from prefect.server.utilities.messaging.memory import MemoryMessage


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
        await triggers.reconcile_automations()
        messages = self.events_to_messages(events)
        await self.process_messages(messages)

    async def process_messages(self, messages: list[MemoryMessage]) -> None:
        for message in messages:
            await self.process_message(message)

    async def process_message(self, message: MemoryMessage) -> None:
        """Process a single event message"""

        async with task_run_recorder.consumer(
            write_batch_size=1, flush_every=1
        ) as handler:
            await handler(message)

        async with event_persister.create_handler(batch_size=1) as handler:
            await handler(message)

        if message.attributes.get("event") == "prefect.log.write":
            return

        event = ReceivedEvent.model_validate_json(message.data)
        try:
            await triggers.reactive_evaluation(event)
        except EventArrivedEarly:
            pass
