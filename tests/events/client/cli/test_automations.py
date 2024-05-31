import sys
from datetime import timedelta
from typing import Generator, List
from unittest import mock
from uuid import UUID, uuid4

import orjson
import pytest
import yaml
from typer import Exit

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
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.events.cli.automations.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar():
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


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
        Automation(
            id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
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
        ["automations", "inspect", "--id", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
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


def test_inspecting_by_id_not_found(
    various_automations: List[Automation],
):
    invoke_and_assert(
        ["automations", "inspect", "--id", "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"],
        expected_code=1,
        expected_output_contains=[
            "Automation with id 'zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz' not found"
        ],
    )


def test_inspecting_by_name(
    various_automations: List[Automation], read_automations_by_name: mock.AsyncMock
):
    read_automations_by_name.return_value = [various_automations[0]]
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


def test_inspecting_by_name_not_found(
    various_automations: List[Automation], read_automations_by_name: mock.AsyncMock
):
    read_automations_by_name.return_value = None
    invoke_and_assert(
        ["automations", "inspect", "What is this?"],
        expected_code=1,
        expected_output_contains=["Automation 'What is this?' not found"],
    )


def test_inspecting_by_name_in_json(
    various_automations: List[Automation], read_automations_by_name: mock.AsyncMock
):
    read_automations_by_name.return_value = [various_automations[0]]
    result = invoke_and_assert(
        ["automations", "inspect", "My First Reactive", "--json"], expected_code=0
    )
    loaded = orjson.loads(result.output)
    assert loaded[0]["name"] == "My First Reactive"
    assert loaded[0]["id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_inspecting_by_id_in_json(
    various_automations: List[Automation], read_automation: mock.AsyncMock
):
    read_automation.return_value = various_automations[1]
    result = invoke_and_assert(
        [
            "automations",
            "inspect",
            "--id",
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "--json",
        ],
        expected_code=0,
    )
    loaded = orjson.loads(result.output)
    assert loaded["name"] == "My Other Reactive Automation"
    assert loaded["id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_inspecting_by_name_in_yaml(
    various_automations: List[Automation], read_automations_by_name: mock.AsyncMock
):
    read_automations_by_name.return_value = [various_automations[0]]
    result = invoke_and_assert(
        ["automations", "inspect", "My First Reactive", "--yaml"], expected_code=0
    )
    loaded = yaml.safe_load(result.output)
    assert loaded[0]["name"] == "My First Reactive"
    assert loaded[0]["id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_inspecting_by_id_in_yaml(
    various_automations: List[Automation], read_automation: mock.AsyncMock
):
    read_automation.return_value = various_automations[1]
    result = invoke_and_assert(
        [
            "automations",
            "inspect",
            "--id",
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "--yaml",
        ],
        expected_code=0,
    )
    loaded = yaml.safe_load(result.output)
    assert loaded["name"] == "My Other Reactive Automation"
    assert loaded["id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture
def pause_automation() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.pause_automation", autospec=True
    ) as m:
        yield m


def test_pausing_by_name(
    pause_automation: mock.AsyncMock,
    various_automations: List[Automation],
    read_automations_by_name: mock.AsyncMock,
):
    read_automations_by_name.return_value = [various_automations[0]]
    invoke_and_assert(
        ["automations", "pause", "My First Reactive"],
        expected_code=0,
        expected_output_contains=[
            "Paused automation(s) with name 'My First Reactive' and id(s) 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"
        ],
    )

    pause_automation.assert_awaited_once_with(
        mock.ANY, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )


def test_pausing_by_name_not_found(
    pause_automation: mock.AsyncMock,
    various_automations: List[Automation],
    read_automations_by_name: mock.AsyncMock,
):
    read_automations_by_name.return_value = None
    invoke_and_assert(
        ["automations", "pause", "Wha?"],
        expected_code=1,
        expected_output_contains=["Automation with name 'Wha?' not found"],
    )

    pause_automation.assert_not_awaited()


def test_pausing_by_id(
    pause_automation: mock.AsyncMock,
    various_automations: List[Automation],
    read_automation: mock.AsyncMock,
):
    read_automation.return_value = various_automations[0]
    invoke_and_assert(
        ["automations", "pause", "--id", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
        expected_code=0,
        expected_output_contains=[
            "Paused automation with id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"
        ],
    )

    pause_automation.assert_awaited_once_with(
        mock.ANY, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )


def test_pausing_by_id_not_found(
    pause_automation: mock.AsyncMock,
    read_automation: mock.AsyncMock,
):
    read_automation.return_value = None
    invoke_and_assert(
        ["automations", "pause", "--id", "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"],
        expected_code=1,
        expected_output_contains=[
            "Automation with id 'zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz' not found"
        ],
    )

    pause_automation.assert_not_awaited()


@pytest.fixture
def resume_automation() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.resume_automation", autospec=True
    ) as m:
        yield m


def test_resuming_by_name(
    resume_automation: mock.AsyncMock,
    various_automations: List[Automation],
    read_automations_by_name: mock.AsyncMock,
):
    read_automations_by_name.return_value = [various_automations[0]]
    invoke_and_assert(
        ["automations", "resume", "My First Reactive"],
        expected_code=0,
        expected_output_contains=[
            "Resumed automation(s) with name 'My First Reactive' and id(s) 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"
        ],
    )

    resume_automation.assert_awaited_once_with(
        mock.ANY, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )


def test_resuming_by_name_not_found(
    resume_automation: mock.AsyncMock,
    various_automations: List[Automation],
    read_automations_by_name: mock.AsyncMock,
):
    read_automations_by_name.return_value = None
    invoke_and_assert(
        ["automations", "resume", "Wha?"],
        expected_code=1,
        expected_output_contains=["Automation with name 'Wha?' not found"],
    )

    resume_automation.assert_not_awaited()


def test_resuming_by_id(
    resume_automation: mock.AsyncMock,
    various_automations: List[Automation],
    read_automation: mock.AsyncMock,
):
    read_automation.return_value = various_automations[0]
    invoke_and_assert(
        ["automations", "resume", "--id", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
        expected_code=0,
        expected_output_contains=[
            "Resumed automation with id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"
        ],
    )

    resume_automation.assert_awaited_once_with(
        mock.ANY, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )


def test_resuming_by_id_not_found(
    resume_automation: mock.AsyncMock, read_automation: mock.AsyncMock
):
    read_automation.return_value = None
    invoke_and_assert(
        ["automations", "resume", "--id", "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"],
        expected_code=1,
        expected_output_contains=[
            "Automation with id 'zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz' not found"
        ],
    )

    resume_automation.assert_not_awaited()


@pytest.fixture
def delete_automation() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.delete_automation", autospec=True
    ) as m:
        yield m


@pytest.fixture
def read_automations_by_name() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.read_automations_by_name",
        autospec=True,
    ) as mock_read:
        yield mock_read


def test_deleting_by_name(
    delete_automation: mock.AsyncMock,
    read_automations_by_name: mock.AsyncMock,
    various_automations: List[Automation],
):
    read_automations_by_name.return_value = [various_automations[0]]
    invoke_and_assert(
        ["automations", "delete", "My First Reactive"],
        prompts_and_responses=[
            (
                "Are you sure you want to delete automation with name 'My First Reactive'?",
                "y",
            )
        ],
        expected_code=0,
        expected_output_contains=["Deleted automation with name 'My First Reactive'"],
    )

    delete_automation.assert_awaited_once_with(
        mock.ANY, UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    )


def test_deleting_by_name_multiple_same_name(
    delete_automation: mock.AsyncMock,
    read_automations_by_name: mock.AsyncMock,
    various_automations: List[Automation],
):
    read_automations_by_name.return_value = various_automations[:2]
    invoke_and_assert(
        ["automations", "delete", "A Metric one"],
        expected_code=1,
        expected_output_contains=[
            "Multiple automations found with name 'A Metric one'. Please specify an id with the `--id` flag instead."
        ],
    )

    delete_automation.assert_not_called()


def test_deleting_by_id_not_found_is_a_noop(
    delete_automation: mock.AsyncMock,
    various_automations: List[Automation],
    read_automations_by_name: mock.AsyncMock,
):
    read_automations_by_name.return_value = None
    invoke_and_assert(
        ["automations", "delete", "Who dis?"],
        expected_code=1,
        expected_output_contains=["Automation 'Who dis?' not found"],
    )

    delete_automation.assert_not_called()


def test_deleting_by_id(
    delete_automation: mock.AsyncMock,
    read_automation: mock.AsyncMock,
    various_automations: List[Automation],
):
    read_automation.return_value = various_automations[0]
    invoke_and_assert(
        ["automations", "delete", "--id", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
        prompts_and_responses=[
            (
                "Are you sure you want to delete automation with id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'?",
                "y",
            )
        ],
        expected_code=0,
        expected_output_contains=[
            "Deleted automation with id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"
        ],
    )

    delete_automation.assert_awaited_once_with(
        mock.ANY, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )


def test_deleting_by_nonexistent_id(
    delete_automation: mock.AsyncMock,
    read_automation: mock.AsyncMock,
):
    read_automation.return_value = None
    invoke_and_assert(
        ["automations", "delete", "--id", "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"],
        expected_code=1,
        expected_output_contains=[
            "Automation with id 'zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz' not found"
        ],
    )

    delete_automation.assert_not_called()
