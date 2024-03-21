import datetime
from typing import Optional

import pytest

from prefect.client.schemas.objects import MinimalDeploymentSchedule
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.deployments.schedules import (
    create_minimal_deployment_schedule,
    normalize_to_minimal_deployment_schedules,
)
from prefect.server.schemas.schedules import CronSchedule as ServerCronSchedule


@pytest.mark.parametrize(
    "active, expected",
    [(False, False), (True, True), (None, True)],
)
def test_create_minimal_deployment_schedule(active: Optional[bool], expected: bool):
    schedule = create_minimal_deployment_schedule(
        schedule=CronSchedule(cron="0 0 * * *"), active=active
    )
    assert schedule.schedule.cron == "0 0 * * *"
    assert schedule.active is expected


def test_normalize_none_returns_empty_list():
    assert normalize_to_minimal_deployment_schedules(None) == []


def test_normalize_schedule_objects():
    normalized = normalize_to_minimal_deployment_schedules(
        schedules=[
            CronSchedule(cron="0 0 * * *"),
            IntervalSchedule(interval=datetime.timedelta(minutes=10)),
            RRuleSchedule(rrule="FREQ=DAILY"),
        ]
    )

    assert all(isinstance(s, MinimalDeploymentSchedule) for s in normalized)
    assert all(s.active is True for s in normalized)

    assert normalized[0].schedule.cron == "0 0 * * *"
    assert normalized[1].schedule.interval == datetime.timedelta(minutes=10)
    assert normalized[2].schedule.rrule == "FREQ=DAILY"


def test_normalize_dicts():
    normalized = normalize_to_minimal_deployment_schedules(
        schedules=[
            {"schedule": {"interval": datetime.timedelta(minutes=10)}},
            {"schedule": {"cron": "0 0 * * *"}, "active": False},
            {"schedule": {"rrule": "FREQ=DAILY"}, "active": True},
        ]
    )

    assert all(isinstance(s, MinimalDeploymentSchedule) for s in normalized)

    assert normalized[0].active is True
    assert normalized[0].schedule.interval == datetime.timedelta(minutes=10)

    assert normalized[1].active is False
    assert normalized[1].schedule.cron == "0 0 * * *"

    assert normalized[2].active is True
    assert normalized[2].schedule.rrule == "FREQ=DAILY"


def test_normalize_minimal_deployment_schedules():
    schedules = [
        MinimalDeploymentSchedule(schedule=CronSchedule(cron="0 0 * * *")),
        MinimalDeploymentSchedule(
            schedule=IntervalSchedule(interval=datetime.timedelta(minutes=10))
        ),
        MinimalDeploymentSchedule(
            schedule=RRuleSchedule(rrule="FREQ=DAILY"), active=False
        ),
    ]

    normalized = normalize_to_minimal_deployment_schedules(schedules=schedules)

    assert normalized == schedules


def test_normalize_mixed():
    normalized = normalize_to_minimal_deployment_schedules(
        schedules=[
            CronSchedule(cron="0 0 * * *"),
            {"schedule": {"interval": datetime.timedelta(minutes=10)}},
            MinimalDeploymentSchedule(
                schedule=RRuleSchedule(rrule="FREQ=DAILY"), active=False
            ),
        ]
    )

    assert all(isinstance(s, MinimalDeploymentSchedule) for s in normalized)

    assert normalized[0].active is True
    assert normalized[0].schedule.cron == "0 0 * * *"

    assert normalized[1].active is True
    assert normalized[1].schedule.interval == datetime.timedelta(minutes=10)

    assert normalized[2].active is False
    assert normalized[2].schedule.rrule == "FREQ=DAILY"


def test_normalize_server_schema():
    with pytest.raises(ValueError, match="Server schema schedules are not supported"):
        normalize_to_minimal_deployment_schedules(
            schedules=[ServerCronSchedule(cron="0 0 * * *")]
        )


def test_normalize_incompatible():
    with pytest.raises(ValueError, match="Invalid schedule provided"):
        normalize_to_minimal_deployment_schedules(schedules=[1, 2, 3])
