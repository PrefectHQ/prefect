from prefect.events import Event
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL, temporary_settings
from prefect.testing.cli import invoke_and_assert
from prefect.testing.fixtures import Puppeteer, Recorder
from prefect.utilities.asyncutils import run_sync_in_worker_thread


async def test_event_stream(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    with temporary_settings(
        updates={PREFECT_API_KEY: "my-token", PREFECT_API_URL: events_api_url}
    ):
        puppeteer.token = "my-token"
        puppeteer.outgoing_events = [example_event_1, example_event_2]
        run_sync_in_worker_thread(
            invoke_and_assert,
            command=["events", "stream", "--format", "json"],
            expected_line_count=3,
        )
