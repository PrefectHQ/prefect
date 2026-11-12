import datetime
from typing import Optional, Union

import pytest

from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import (
    SCHEDULE_TYPES,
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
    construct_schedule,
)
from prefect.deployments.schedules import (
    create_deployment_schedule_create,
    normalize_to_deployment_schedule,
)
from prefect.schedules import Cron, Interval, RRule, Schedule
from prefect.server.schemas.schedules import CronSchedule as ServerCronSchedule


@pytest.mark.parametrize(
    "active, expected",
    [(False, False), (True, True), (None, True)],
)
def test_create_deployment_schedule_create(active: Optional[bool], expected: bool):
    schedule = create_deployment_schedule_create(
        schedule=CronSchedule(cron="0 0 * * *"), active=active
    )
    assert schedule.schedule.cron == "0 0 * * *"
    assert schedule.active is expected
    assert ("active" in schedule.model_fields_set) is (active is not None)


@pytest.mark.parametrize(
    "schedule, expected_sent",
    [
        (CronSchedule(cron="0 0 * * *"), set()),
        (construct_schedule(interval=3600), set()),
        (Cron("0 0 * * *"), set()),
        (Cron("0 0 * * *", active=True), {"active"}),
        (Interval(3600), set()),
        (Interval(3600, anchor_date=datetime.datetime(2026, 1, 1)), {"anchor_date"}),
        (RRule("RRULE:FREQ=DAILY", active=False), {"active"}),
    ],
)
def test_normalize_sends_only_values_the_caller_set(
    schedule: Union[SCHEDULE_TYPES, Schedule], expected_sent: set[str]
):
    # Redeploys send schedules with `exclude_unset=True`, so values the caller
    # didn't set don't override the server's, e.g. a paused schedule (#19302)
    (normalized,) = normalize_to_deployment_schedule([schedule])
    payload = normalized.model_dump(exclude_unset=True)
    assert {"active", "anchor_date"} & {*payload, *payload["schedule"]} == expected_sent


def test_normalize_none_returns_empty_list():
    assert normalize_to_deployment_schedule(None) == []


def test_normalize_schedule_objects():
    normalized = normalize_to_deployment_schedule(
        schedules=[
            CronSchedule(cron="0 0 * * *"),
            IntervalSchedule(interval=datetime.timedelta(minutes=10)),
            RRuleSchedule(rrule="FREQ=DAILY"),
        ]
    )

    assert all(isinstance(s, DeploymentScheduleCreate) for s in normalized)
    assert all(s.active is True for s in normalized)

    assert normalized[0].schedule.cron == "0 0 * * *"
    assert normalized[1].schedule.interval == datetime.timedelta(minutes=10)
    # `DeploymentScheduleCreate` injects an explicit DTSTART (#21362).
    assert normalized[2].schedule.rrule.endswith("FREQ=DAILY")


def test_normalize_dicts():
    normalized = normalize_to_deployment_schedule(
        schedules=[
            {"schedule": {"interval": datetime.timedelta(minutes=10)}},
            {"schedule": {"cron": "0 0 * * *"}, "active": False},
            {"schedule": {"rrule": "FREQ=DAILY"}, "active": True},
        ]
    )

    assert all(isinstance(s, DeploymentScheduleCreate) for s in normalized)

    assert normalized[0].active is True
    assert normalized[0].schedule.interval == datetime.timedelta(minutes=10)

    assert normalized[1].active is False
    assert normalized[1].schedule.cron == "0 0 * * *"

    assert normalized[2].active is True
    # `DeploymentScheduleCreate` injects an explicit DTSTART (#21362).
    assert normalized[2].schedule.rrule.endswith("FREQ=DAILY")


def test_normalize_minimal_deployment_schedules():
    schedules = [
        DeploymentScheduleCreate(schedule=CronSchedule(cron="0 0 * * *")),
        DeploymentScheduleCreate(
            schedule=IntervalSchedule(interval=datetime.timedelta(minutes=10))
        ),
        DeploymentScheduleCreate(
            schedule=RRuleSchedule(rrule="FREQ=DAILY"), active=False
        ),
    ]

    normalized = normalize_to_deployment_schedule(schedules=schedules)

    assert normalized == schedules


def test_normalize_mixed():
    normalized = normalize_to_deployment_schedule(
        schedules=[
            CronSchedule(cron="0 0 * * *"),
            {"schedule": {"interval": datetime.timedelta(minutes=10)}},
            DeploymentScheduleCreate(
                schedule=RRuleSchedule(rrule="FREQ=DAILY"), active=False
            ),
        ]
    )

    assert all(isinstance(s, DeploymentScheduleCreate) for s in normalized)

    assert normalized[0].active is True
    assert normalized[0].schedule.cron == "0 0 * * *"

    assert normalized[1].active is True
    assert normalized[1].schedule.interval == datetime.timedelta(minutes=10)

    assert normalized[2].active is False
    # `DeploymentScheduleCreate` injects an explicit DTSTART (#21362).
    assert normalized[2].schedule.rrule.endswith("FREQ=DAILY")


def test_normalize_server_schema():
    with pytest.raises(ValueError, match="Server schema schedules are not supported"):
        normalize_to_deployment_schedule(
            schedules=[ServerCronSchedule(cron="0 0 * * *")]
        )


def test_normalize_incompatible():
    with pytest.raises(ValueError, match="Invalid schedule provided"):
        normalize_to_deployment_schedule(schedules=[1, 2, 3])
