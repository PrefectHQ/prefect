---
description: Prefect lets you schedule when to automatically create new flow runs.
tags:
    - Orion
    - flows
    - flow runs
    - deployments
    - schedules
    - cron
    - RRule
    - iCal
---

# Schedules

Schedules tell the Prefect API how to create new flow runs for you automatically on a specified cadence.

You can add a schedule to any flow [deployment](/concepts/deployments/). The Prefect `Scheduler` service periodically reviews every deployment and creates new flow runs according to the schedule configured for the deployment. In addition, auto-scheduled runs are proactively generated any time a deployment is created or modified.

## Schedule types

Prefect supports several types of schedule that cover a wide range of use cases and offer a large degree of customization:

- [`CronSchedule`](#cronschedule) is most appropriate for users who are already familiar with `cron` from use in other systems.
- [`IntervalSchedule`](#intervalschedule) is best suited for deployments that need to run at some consistent cadence that isn't related to absolute time.
- [`RRuleSchedule`](#rruleschedule) is best suited for deployments that rely on calendar logic for simple recurring schedules, irregular intervals, exclusions, or day-of-month adjustments.

## Creating schedules

You create a schedule by defining a `schedule` parameter as part of the [deployment specification](/concepts/deployments/#deployment-specifications) for a deployment.

First, import the schedule class that you want to use, then define the `schedule` parameter using an instance of that class.

```python
from prefect import DeploymentSpec
from prefect.orion.schemas.schedules import CronSchedule

DeploymentSpec(
    name="scheduled-deployment",
    flow_location="/path/to/flow.py",
    schedule=CronSchedule(cron="0 0 * * *"),
)
```

When you create or update a deployment with `prefect deployment create`, the Prefect API creates scheduled flow runs based on the `schedule` parameter value in the deployment specification.

If you change a schedule, previously scheduled flow runs that have not started are removed, and new scheduled flow runs are created to reflect the new schedule.

To remove all scheduled runs for a flow deployment, update the deployment with no `schedule` parameter.

## CronSchedule

A `CronSchedule` creates new flow runs according to a provided [cron](https://en.wikipedia.org/wiki/Cron) string. Users may also provide a timezone to enforce DST behaviors.

!!! info "Daylight saving time considerations"
    If the timezone is a DST-observing one, then the schedule will adjust itself appropriately. Cron's rules for DST are based on schedule times, not intervals. This means that an hourly cron schedule will fire on every new schedule hour, not every elapsed hour; for example, when clocks are set back this will result in a two-hour pause as the schedule will fire _the first time_ 1am is reached and _the first time_ 2am is reached, 120 minutes later. Longer schedules, such as one that fires at 9am every morning, will automatically adjust for DST.

For more detail, please see the [`CronSchedule` API reference][prefect.orion.schemas.schedules.CronSchedule].

## IntervalSchedule

An `IntervalSchedule` creates new flow runs on a regular interval measured in seconds. Intervals are computed from an optional `anchor_date`.

```python
from prefect import DeploymentSpec
from prefect.orion.schemas.schedules import IntervalSchedule

DeploymentSpec(
    name="interval-schedule-deployment",
    flow_location="/path/to/flow.py",
    schedule=IntervalSchedule(interval=timedelta(hours=1)),
)
```

`IntervalSchedule` properties include:

| Property | Description |
| --- | --- |
| interval | `datetime.timedelta` indicating the time between flow runs. (Required) |
| anchor_date | `datetime.datetime` indicating the starting or "anchor" date to begin the schedule. If no `anchor_date` is supplied, January 1, 2020 at midnight UTC is used. |
| timezone | String name of a time zone. (See the [IANA Time Zone Database](https://www.iana.org/time-zones) for valid time zones.) |




!!! info "Daylight saving time considerations"
    If the schedule's `anchor_date` or `timezone` are provided with a DST-observing timezone, then the schedule will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. For example, an hourly schedule will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that _appear_ to both be scheduled for 1am local time, even though they are an hour apart in UTC time. For longer intervals, like a daily schedule, the interval schedule will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily schedule that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.

For more detail, please see the [`IntervalSchedule` API reference][prefect.orion.schemas.schedules.IntervalSchedule]

## RRuleSchedule



An `RRuleSchedule` creates calendar-based recurrances that are compatible with the iCalendar (`.ics`) standard ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) as implemented by `dateutils.rrule`.

RRules are appropriate for any kind of calendar-date manipulation, including simple repetition, irregular intervals, exclusions, week day or day-of-month adjustments, and more. RRules can represent complex logic like: - The last weekday of each month - The fourth Thursday of November - Every other day of the week - etc.

!!! info "Daylight saving time considerations"
    Note that as a calendar-oriented standard, `RRuleSchedules` are sensitive to to the initial timezone provided. A 9am daily schedule with a daylight saving time-aware start date will maintain a local 9am time through DST boundaries; a 9am daily schedule with a UTC start date will maintain a 9am UTC time.

For more detail, please see the [`RRuleSchedule` API reference][prefect.orion.schemas.schedules.RRuleSchedule].



## The `Scheduler` service

The `Scheduler` service is started automatically when `prefect orion start` is run. By default, it visits deployments on a [60-second loop][prefect.settings.Settings.PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS] and attempts to create up to [100][prefect.settings.Settings.PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS] scheduled flow runs up to [100 days][prefect.settings.Settings.PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME] in the future. This means that if a deployment has an hourly schedule, the default settings will create runs for the next 4 days (or 100 hours). If it has a weekly schedule, the default settings will maintain the next 14 runs (up to 100 days in the future).

!!! info "The scheduler does not affect execution"
    The Orion `Scheduler` service only creates new flow runs and places them in `Scheduled` states; it is not at all involved in flow or task execution. Making the scheduler loop faster will not make flows start or run faster.

