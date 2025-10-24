from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import prefect.cli.root as root
from prefect.cli._prompts import prompt_schedules
from prefect.cli.root import app
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.types._datetime import parse_datetime
from prefect.utilities.annotations import NotSet
from prefect.utilities.templating import apply_values


def _construct_schedules(
    deploy_config: dict[str, Any],
    step_outputs: dict[str, Any],
) -> list[dict[str, Any]]:
    schedules: list[dict[str, Any]] = []
    schedule_configs = deploy_config.get("schedules", NotSet) or []

    if schedule_configs is not NotSet:
        schedules = [
            _schedule_config_to_deployment_schedule(schedule_config)
            for schedule_config in apply_values(schedule_configs, step_outputs)
        ]
    elif schedule_configs is NotSet:
        if root.is_interactive():
            schedules = prompt_schedules(app.console)

    return schedules


def _schedule_config_to_deployment_schedule(
    schedule_config: dict[str, Any],
) -> dict[str, Any]:
    anchor_date = schedule_config.get("anchor_date")
    timezone = schedule_config.get("timezone")
    schedule_active = schedule_config.get("active")
    parameters = schedule_config.get("parameters", {})
    slug = schedule_config.get("slug")

    if cron := schedule_config.get("cron"):
        day_or = schedule_config.get("day_or")
        cron_kwargs = {"cron": cron, "timezone": timezone, "day_or": day_or}
        schedule = CronSchedule(
            **{k: v for k, v in cron_kwargs.items() if v is not None}
        )
    elif interval := schedule_config.get("interval"):
        interval_kwargs = {
            "interval": timedelta(seconds=interval),
            "anchor_date": parse_datetime(anchor_date) if anchor_date else None,
            "timezone": timezone,
        }
        schedule = IntervalSchedule(
            **{k: v for k, v in interval_kwargs.items() if v is not None}
        )
    elif rrule := schedule_config.get("rrule"):
        try:
            schedule = RRuleSchedule(**json.loads(rrule))
            if timezone:
                schedule.timezone = timezone
        except json.JSONDecodeError:
            schedule = RRuleSchedule(rrule=rrule, timezone=timezone)
    else:
        raise ValueError(
            f"Unknown schedule type. Please provide a valid schedule. schedule={schedule_config}"
        )

    schedule_obj: dict[str, Any] = {"schedule": schedule}
    if schedule_active is not None:
        schedule_obj["active"] = schedule_active
    if parameters:
        schedule_obj["parameters"] = parameters
    if slug:
        schedule_obj["slug"] = slug

    return schedule_obj
