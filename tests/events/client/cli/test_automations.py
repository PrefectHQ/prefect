from datetime import timedelta
from typing import Generator, List
from unittest import mock
from uuid import UUID, uuid4

import orjson
import pytest
import yaml

from prefect.events.actions import CancelFlowRun, DoNothing, PauseAutomation
from prefect.events.schemas.automations import (
    Automation,
    EventTrigger,
    MetricTrigger,
    MetricTriggerOperator,
    MetricTriggerQuery,
    Posture,
    PrefectMetric,
)
from prefect.settings import PREFECT_EXPERIMENTAL_EVENTS, temporary_settings
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True, scope="module")
def enable_events():
    with temporary_settings({PREFECT_EXPERIMENTAL_EVENTS: True}):
        yield


@pytest.fixture
def read_automations() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.read_automations", autospec=True
    ) as m:
        yield m


def test_listing_automations_empty(read_automations: mock.AsyncMock):
    read_automations.return_value = []
    invoke_and_assert(
        ["automations", "ls"],
        expected_code=0,
        expected_output_contains="Automations",
    )


@pytest.fixture
def various_automations(read_automations: mock.AsyncMock) -> List[Automation]:
    automations = [
        Automation(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            name="My First Reactive",
            description="This one reacts to things!",
            trigger=EventTrigger(
                posture=Posture.Reactive, expect={"event.one", "event.two"}, threshold=1
            ),
            actions=[DoNothing()],
        ),
        Automation(
            id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            name="My Other Reactive Automation",
            description="This one also reacts to things!",
            trigger=EventTrigger(
                posture=Posture.Reactive,
                expect={"event.three", "event.four"},
                threshold=2,
            ),
            actions=[CancelFlowRun()],
        ),
        Automation(
            id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            name="A Proactive one",
            trigger=EventTrigger(
                posture=Posture.Proactive,
                expect={"event.five"},
                threshold=2,
                within=timedelta(minutes=5),
            ),
            actions=[CancelFlowRun()],
        ),
        Automation(
            id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            name="A Metric one",
            trigger=MetricTrigger(
                metric=MetricTriggerQuery(
                    name=PrefectMetric.successes,
                    operator=MetricTriggerOperator.LT,
                    threshold=0.78,
                )
            ),
            actions=[CancelFlowRun()],
            actions_on_trigger=[DoNothing()],
            actions_on_resolve=[PauseAutomation(automation_id=uuid4())],
        ),
    ]
    read_automations.return_value = automations
    return automations


def test_listing_various_automations(various_automations: List[Automation]):
    invoke_and_assert(
        ["automations", "ls"],
        expected_code=0,
        expected_output_contains=[
            # first reactive
            "My First Reactive",
            "aaaaaaaa-aaaa-",
            "This one reacts",
            "Reactive:",
            "event.one",
            "event.two",
            "Do nothing",
            # second reactive
            "My Other Reactive",
            "bbbbbbbb-bbbb-",
            "This one also reacts",
            "Reactive:",
            "event.three",
            "event.four",
            "Cancel flow run",
            # third proactive
            "A Proactive one",
            "cccccccc-cccc-",
            "Proactive:",
            "event.five",
            "within 0:05:00",
            # fourth metric
            "A Metric one",
            "successes <",
            "0.78 for 0:05:00",
            "(trigger) Cancel",
            "(trigger) Do nothing",
            "(resolve) Cancel",
            "(resolve) Pause",
        ],
    )


@pytest.fixture
def read_automation() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.read_automation", autospec=True
    ) as m:
        yield m


def test_inspecting_by_id(
    read_automation: mock.AsyncMock, various_automations: List[Automation]
):
    read_automation.return_value = various_automations[1]

    invoke_and_assert(
        ["automations", "inspect", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
        expected_code=0,
        expected_output_contains=[
            "Automation(",
            "My Other Reactive Automation",
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "EventTrigger(",
        ],
    )

    read_automation.assert_awaited_once_with(
        mock.ANY, UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    )


def test_inspecting_by_name(various_automations: List[Automation]):
    invoke_and_assert(
        ["automations", "inspect", "My First Reactive"],
        expected_code=0,
        expected_output_contains=[
            "Automation(",
            "My First Reactive",
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "EventTrigger(",
        ],
    )


def test_inspecting_not_found(various_automations: List[Automation]):
    invoke_and_assert(
        ["automations", "inspect", "What is this?"],
        expected_code=1,
        expected_output_contains=["Automation 'What is this?' not found"],
    )


def test_inspecting_in_json(various_automations: List[Automation]):
    result = invoke_and_assert(
        ["automations", "inspect", "My First Reactive", "--json"], expected_code=0
    )
    loaded = orjson.loads(result.output)
    assert loaded["name"] == "My First Reactive"
    assert loaded["id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_inspecting_in_yaml(various_automations: List[Automation]):
    result = invoke_and_assert(
        ["automations", "inspect", "My First Reactive", "--yaml"], expected_code=0
    )
    loaded = yaml.safe_load(result.output)
    assert loaded["name"] == "My First Reactive"
    assert loaded["id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def pause_automation() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.pause_automation", autospec=True
    ) as m:
        yield m


def test_pausing_by_name(
    pause_automation: mock.AsyncMock, various_automations: List[Automation]
):
    invoke_and_assert(
        ["automations", "pause", "My First Reactive"],
        expected_code=0,
        expected_output_contains=["Paused automation 'My First Reactive'"],
    )

    pause_automation.assert_awaited_once_with(
        mock.ANY, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )


def test_pausing_not_found(
    pause_automation: mock.AsyncMock, various_automations: List[Automation]
):
    invoke_and_assert(
        ["automations", "pause", "Wha?"],
        expected_code=1,
        expected_output_contains=["Automation 'Wha?' not found"],
    )

    pause_automation.assert_not_awaited()


@pytest.fixture
def resume_automation() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.resume_automation", autospec=True
    ) as m:
        yield m


def test_resuming_by_name(
    resume_automation: mock.AsyncMock, various_automations: List[Automation]
):
    invoke_and_assert(
        ["automations", "resume", "My First Reactive"],
        expected_code=0,
        expected_output_contains=["Resumed automation 'My First Reactive'"],
    )

    resume_automation.assert_awaited_once_with(
        mock.ANY, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )


def test_resuming_not_found(
    resume_automation: mock.AsyncMock, various_automations: List[Automation]
):
    invoke_and_assert(
        ["automations", "resume", "Wha?"],
        expected_code=1,
        expected_output_contains=["Automation 'Wha?' not found"],
    )

    resume_automation.assert_not_awaited()


@pytest.fixture
def delete_automation() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.delete_automation", autospec=True
    ) as m:
        yield m


def test_deleting_by_name(
    delete_automation: mock.AsyncMock, various_automations: List[Automation]
):
    invoke_and_assert(
        ["automations", "delete", "My First Reactive"],
        expected_code=0,
        expected_output_contains=["Deleted automation 'My First Reactive'"],
    )

    delete_automation.assert_awaited_once_with(
        mock.ANY, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )


def test_deleting_not_found_is_a_noop(
    delete_automation: mock.AsyncMock, various_automations: List[Automation]
):
    invoke_and_assert(
        ["automations", "delete", "Who dis?"],
        expected_code=0,
        expected_output_contains=["Automation 'Who dis?' not found"],
    )

    delete_automation.assert_not_called()
