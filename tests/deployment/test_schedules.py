import datetime
from typing import Optional

import pytest

from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.deployments.schedules import (
    create_deployment_schedule_create,
    normalize_to_deployment_schedule,
)
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
    assert normalized[2].schedule.rrule == "FREQ=DAILY"


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
    assert normalized[2].schedule.rrule == "FREQ=DAILY"


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
    assert normalized[2].schedule.rrule == "FREQ=DAILY"


def test_normalize_server_schema():
    with pytest.raises(ValueError, match="Server schema schedules are not supported"):
        normalize_to_deployment_schedule(
            schedules=[ServerCronSchedule(cron="0 0 * * *")]
        )


def test_normalize_incompatible():
    with pytest.raises(ValueError, match="Invalid schedule provided"):
        normalize_to_deployment_schedule(schedules=[1, 2, 3])
