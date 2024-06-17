"""Tests for our heuristics about Automations that may contain infinite loops."""

from datetime import timedelta
from typing import Set
from uuid import uuid4

import pytest
from pydantic import ValidationError

from prefect.server.events.actions import RunDeployment
from prefect.server.events.schemas.automations import (
    AutomationCore,
    EventTrigger,
    Posture,
)


def test_running_inferred_deployment_on_all_flow_run_state_changes():
    """It's never okay to run an inferred deployment from all flow run state changes."""
    with pytest.raises(ValidationError) as exc_info:
        AutomationCore(
            name="Run inferred deployment on all flow run state changes",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                for_each={"prefect.resource.id"},
                expect={"prefect.flow-run.*"},
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=0),
            ),
            actions=[RunDeployment(source="inferred")],
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    (error,) = errors

    assert error["loc"] == tuple()
    assert "Running an inferred deployment from a flow run" in error["msg"]


def test_running_inferred_deployment_on_filtered_flow_run_state_changes():
    """It's never okay to run an inferred deployment from a flow run state change,
    even if there are filters on it (because it's inferred so the flow run will just
    generate another flow run just like it)."""
    with pytest.raises(ValidationError) as exc_info:
        AutomationCore(
            name="Run inferred deployment on some flow run state changes",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*", "some": "thing"},
                for_each={"prefect.resource.id"},
                expect={"prefect.flow-run.*"},
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=0),
            ),
            actions=[RunDeployment(source="inferred")],
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    (error,) = errors

    assert error["loc"] == tuple()
    assert "Running an inferred deployment from a flow run" in error["msg"]


def test_running_inferred_deployment_on_related_filtered_flow_run_state_changes():
    """It's never okay to run an inferred deployment from a flow run state change,
    even if there are filters on it (because it's inferred so the flow run will just
    generate another flow run just like it)."""
    with pytest.raises(ValidationError) as exc_info:
        AutomationCore(
            name="Run inferred deployment on some flow run state changes",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                match_related={"some": "thing"},
                for_each={"prefect.resource.id"},
                expect={"prefect.flow-run.*"},
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=0),
            ),
            actions=[RunDeployment(source="inferred")],
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    (error,) = errors

    assert error["loc"] == tuple()
    assert "Running an inferred deployment from a flow run" in error["msg"]


def test_running_a_selected_deployment_on_unfiltered_flow_run_state_changes():
    """It's never okay to run a selected deployment from an unfiltered flow run state
    change, because nothing could filter out the new flow run."""
    with pytest.raises(ValidationError) as exc_info:
        AutomationCore(
            name="Run selected deployment on all flow run state changes",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                for_each={"prefect.resource.id"},
                expect={"prefect.flow-run.*"},
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=0),
            ),
            actions=[RunDeployment(source="selected", deployment_id=uuid4())],
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    (error,) = errors

    assert error["loc"] == tuple()
    assert "Running a selected deployment from a flow run" in error["msg"]


def test_running_a_selected_deployment_on_filtered_flow_run_state_changes():
    """While these can still produce infinite loops, it is okay to set up an automation
    that runs a selected deployment on flow run state changes as long as there are
    some kinds of filters in place (match, match_related)"""
    AutomationCore(
        name="Run selected deployment on some flow run state changes",
        trigger=EventTrigger(
            match={"prefect.resource.id": "prefect.flow-run.*", "some": "thing"},
            for_each={"prefect.resource.id"},
            expect={"prefect.flow-run.*"},
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(seconds=0),
        ),
        actions=[RunDeployment(source="selected", deployment_id=uuid4())],
    )

    AutomationCore(
        name="Run selected deployment on some flow run state changes",
        trigger=EventTrigger(
            match={"prefect.resource.id": "prefect.flow-run.*"},
            match_related={"some": "thing"},
            for_each={"prefect.resource.id"},
            expect={"prefect.flow-run.*"},
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(seconds=0),
        ),
        actions=[RunDeployment(source="selected", deployment_id=uuid4())],
    )


@pytest.mark.parametrize(
    "allowed_events",
    [
        {"prefect.flow-run.Failed"},
        {"prefect.flow-run.Crashed"},
        {"prefect.flow-run.TimedOut"},
        {
            "prefect.flow-run.Failed",
            "prefect.flow-run.Crashed",
            "prefect.flow-run.TimedOut",
        },
    ],
)
def test_allowing_specialized_flow_run_events(allowed_events: Set[str]):
    """Regression test for a bug the first time we released this: many people have
    totally valid and encouraged automations to run deployments on flow run state
    events liked TimedOut, Failed, or Crashed.  These should be accepted."""
    AutomationCore(
        name="Run inferred deployment on failure events",
        trigger=EventTrigger(
            match={"prefect.resource.id": "prefect.flow-run.*"},
            for_each={"prefect.resource.id"},
            expect=allowed_events,
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(seconds=0),
        ),
        actions=[RunDeployment(source="inferred")],
    )

    AutomationCore(
        name="Run selected deployment on failure events",
        trigger=EventTrigger(
            match={"prefect.resource.id": "prefect.flow-run.*"},
            for_each={"prefect.resource.id"},
            expect={
                "prefect.flow-run.TimedOut",
                "prefect.flow-run.Failed",
                "prefect.flow-run.Crashed",
            },
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(seconds=0),
        ),
        actions=[RunDeployment(source="selected", deployment_id=uuid4())],
    )


@pytest.mark.parametrize(
    "naughty_events",
    [
        {
            "prefect.flow-run.Failed",
            "prefect.flow-run.Crashed",
            "prefect.flow-run.Scheduled",  # nope
        },
        {
            "prefect.flow-run.Failed",
            "prefect.flow-run.*",  # nope
            "prefect.flow-run.Crashed",
        },
        {"prefect.flow-run.Pending"},  # nope
        {"prefect.flow-run.Running"},  # nope
        {"prefect.flow-run.Scheduled"},  # nope
    ],
)
def test_blocking_inferred_on_universal_flow_run_events(naughty_events: Set[str]):
    """Regression test for a bug the first time we released this: many people have
    totally valid and encouraged automations to run deployments on flow run state
    events liked TimedOut, Failed, or Crashed.  However, if they sneak in one of the
    universal events, like Scheduled, Pending, Running, or *, they should be blocked."""
    with pytest.raises(ValidationError) as exc_info:
        AutomationCore(
            name="Run inferred deployment on failure events",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                for_each={"prefect.resource.id"},
                expect=naughty_events,
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=0),
            ),
            actions=[RunDeployment(source="inferred")],
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    (error,) = errors

    assert error["loc"] == tuple()
    assert "Running an inferred deployment from a flow run" in error["msg"]


@pytest.mark.parametrize(
    "naughty_events",
    [
        {
            "prefect.flow-run.Failed",
            "prefect.flow-run.Crashed",
            "prefect.flow-run.Scheduled",  # nope
        },
        {
            "prefect.flow-run.Failed",
            "prefect.flow-run.*",  # nope
            "prefect.flow-run.Crashed",
        },
        {"prefect.flow-run.Pending"},  # nope
        {"prefect.flow-run.Running"},  # nope
    ],
)
def test_blocking_selected_on_universal_flow_run_events(naughty_events: Set[str]):
    """Regression test for a bug the first time we released this: many people have
    totally valid and encouraged automations to run deployments on flow run state
    events liked TimedOut, Failed, or Crashed.  However, if they sneak in one of the
    universal events, like Scheduled, Pending, Running, or *, they should be blocked."""
    with pytest.raises(ValidationError) as exc_info:
        AutomationCore(
            name="Run inferred deployment on failure events",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                for_each={"prefect.resource.id"},
                expect=naughty_events,
                posture=Posture.Reactive,
                threshold=1,
                within=timedelta(seconds=0),
            ),
            actions=[RunDeployment(source="selected", deployment_id=uuid4())],
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    (error,) = errors

    assert error["loc"] == tuple()
    assert "Running a selected deployment from a flow run" in error["msg"]
