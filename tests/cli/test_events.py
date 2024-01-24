from prefect.events import Event
from prefect.testing.cli import invoke_and_assert
from prefect.testing.fixtures import Puppeteer, Recorder


async def test_stream_format_json(
    self,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.outgoing_events = [example_event_1, example_event_2]
    invoke_and_assert(command=["events", "stream", "--format", "json"])


async def test_stream_format_text(self):
    invoke_and_assert(command=["events", "stream", "--format", "text"])
