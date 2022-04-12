---
description: Prefect lets you schedule when to automatically create new flow runs.
tags:
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

You can add a schedule to any flow [deployment](/concepts/deployments/). The Prefect `Scheduler` service periodically reviews every deployment and creates new flow runs according to the schedule configured for the deployment. In addition, scheduled runs are proactively generated any time a deployment is created or modified.

## Schedule types

Prefect supports several types of schedule that cover a wide range of use cases and offer a large degree of customization:

- [`CronSchedule`](#cronschedule) is most appropriate for users who are already familiar with `cron` from use in other systems.
- [`IntervalSchedule`](#intervalschedule) is best suited for deployments that need to run at some consistent cadence that isn't related to absolute time.
- [`RRuleSchedule`](#rruleschedule) is best suited for deployments that rely on calendar logic for simple recurring schedules, irregular intervals, exclusions, or day-of-month adjustments.

## Creating schedules

You create a schedule by including a `schedule` parameter as part of the [deployment specification](/concepts/deployments/#deployment-specifications) for a deployment.

First, import the schedule class that you want to use, then set the `schedule` parameter using an instance of that class.

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

A `CronSchedule` creates new flow runs according to a provided [`cron`](https://en.wikipedia.org/wiki/Cron) string. Users may also provide a timezone to enforce DST behaviors.

```python
from prefect import DeploymentSpec
from prefect.orion.schemas.schedules import CronSchedule

DeploymentSpec(
    name="cron-schedule-deployment",
    flow_location="/path/to/flow.py",
    schedule=CronSchedule(
        cron="0 0 * * *",
        timezone="America/New_York"),
)
```

`CronSchedule` properties include:

| Property | Description |
| --- | --- |
| cron | A valid `cron` string. (Required) |
| day_or | Boolean indicating how `croniter` handles `day` and `day_of_week` entries. Default is `True`. |
| timezone | String name of a time zone. (See the [IANA Time Zone Database](https://www.iana.org/time-zones) for valid time zones.) |

The `day_or` property defaults to `True`, matching `cron`, which connects those values using `OR`. If `False`, the values are connected using `AND`. This behaves like `fcron` and enables you to, for example, define a job that executes each 2nd Friday of a month by setting the days of month and the weekday.

!!! info "Daylight saving time considerations"
    If the `timezone` is a DST-observing one, then the schedule will adjust itself appropriately. 
    
    The `cron` rules for DST are based on schedule times, not intervals. This means that an hourly `cron` schedule fires on every new schedule hour, not every elapsed hour. For example, when clocks are set back, this results in a two-hour pause as the schedule will fire _the first time_ 1am is reached and _the first time_ 2am is reached, 120 minutes later. 
    
    Longer schedules, such as one that fires at 9am every morning, will adjust for DST automatically.

For more detail, please see the [`CronSchedule` API reference][prefect.orion.schemas.schedules.CronSchedule].

## IntervalSchedule

An `IntervalSchedule` creates new flow runs on a regular interval measured in seconds. Intervals are computed from an optional `anchor_date`.

```python
from prefect import DeploymentSpec
from prefect.orion.schemas.schedules import IntervalSchedule
from datetime import timedelta

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

An example of specifying an `anchor_date` might be to start a regular flow run on a future date. Note that in this example, we import the [Pendulum](https://pendulum.eustace.io/) Python package for easy datetime manipulation. Pendulum isn’t required, but it’s a useful tool for specifying dates.

```python
from prefect.orion.schemas.schedules import IntervalSchedule
from prefect.deployments import DeploymentSpec
from datetime import timedelta
import pendulum

DeploymentSpec(
    name="daily-interval-deployment",
    flow=base_flow,
    tags=['interval','test', 'daily'],
    schedule=IntervalSchedule(
        interval=timedelta(days=1),
        anchor_date=pendulum.datetime(2022,4,8,20,0,0, tz="America/New_York")),
)
```

!!! info "Daylight saving time considerations"
    If the schedule's `anchor_date` or `timezone` are provided with a DST-observing timezone, then the schedule will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. 
    
    For example, an hourly schedule will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that _appear_ to both be scheduled for 1am local time, even though they are an hour apart in UTC time. 
    
    For longer intervals, like a daily schedule, the interval schedule will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily schedule that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.

For more detail, please see the [`IntervalSchedule` API reference][prefect.orion.schemas.schedules.IntervalSchedule].

## RRuleSchedule

An `RRuleSchedule` supports [iCal recurrence rules](https://icalendar.org/iCalendar-RFC-5545/3-8-5-3-recurrence-rule.html) (RRules), which provide convenient syntax for creating repetitive schedules. Schedules can repeat on a frequency from yearly down to every minute.

`RRuleSchedule` uses the [dateutil rrule](https://dateutil.readthedocs.io/en/stable/rrule.html) module to specify iCal recurrence rules.

RRules are appropriate for any kind of calendar-date manipulation, including simple repetition, irregular intervals, exclusions, week day or day-of-month adjustments, and more. RRules can represent complex logic like: 

- The last weekday of each month 
- The fourth Thursday of November 
- Every other day of the week

You can specify an `RRuleSchedule` as either an RRule string or an `rrule` object. The following example expresses a simple `DAILY` schedule using an RRule string.

```python
from prefect import DeploymentSpec
from prefect.orion.schemas.schedules import RRuleSchedule

DeploymentSpec(
    name="rrule-schedule-deployment",
    flow_location="/path/to/flow.py",
    schedule=RRuleSchedule(
        rrule="DTSTART:20220101T000000\nFREQ=DAILY", 
        timezone="America/New_York"),
)
```

`RRuleSchedule` properties include:

| Property | Description |
| --- | --- |
| rrule | String representation of an RRule schedule. See the [`rrulestr` examples](https://dateutil.readthedocs.io/en/stable/rrule.html#rrulestr-examples) for syntax. |
| timezone | String name of a time zone. See the [IANA Time Zone Database](https://www.iana.org/time-zones) for valid time zones. |

You may find it useful to use an RRule string generator such as the [iCalendar.org RRule Tool](https://icalendar.org/rrule-tool.html) to help create valid RRules.

For example, the following deployment RRule schedule creates flow runs on Monday, Wednesday, and Friday, until June 30.

```python
from prefect import DeploymentSpec
from prefect.orion.schemas.schedules import RRuleSchedule

r_rule_str = """
    DTSTART:20220411T000000
    RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR;UNTIL=20220630T000000Z
    """

DeploymentSpec(
    name="rrule-schedule-deployment",
    flow_location="/path/to/flow.py",
    schedule=RRuleSchedule(
        rrule=r_rule_str, 
        timezone="America/New_York"),
)
```

You can also pass an `rrule` object as the schedule by using `RRuleSchedule.from_rrule`.

```python
from prefect.deployments import DeploymentSpec
from prefect.orion.schemas.schedules import RRuleSchedule
from dateutil.rrule import rrule, DAILY, MO, TU, WE, TH, FR
import pendulum

# start the schedule tomorrow 
start_date = pendulum.now().add(days=1)

# daily schedule on weekdays, total of 8 scheduled runs
r_rule = rrule(
            DAILY, 
            start_date,
            byweekday=(MO, TU, WE, TH, FR),
            count=8,)

DeploymentSpec(
    name="rrule-schedule-deployment",
    flow_location="/path/to/flow.py",
    schedule=RRuleSchedule.from_rrule(r_rule),
)
```

!!! info "Daylight saving time considerations"
    Note that as a calendar-oriented standard, `RRuleSchedules` are sensitive to the initial timezone provided. A 9am daily schedule with a DST-aware start date will maintain a local 9am time through DST boundaries. A 9am daily schedule with a UTC start date will maintain a 9am UTC time.

For more detail, please see the [`RRuleSchedule` API reference][prefect.orion.schemas.schedules.RRuleSchedule].

## The `Scheduler` service

The `Scheduler` service is started automatically when `prefect orion start` is run and is a built-in service of Prefect Cloud. 

By default, the `Scheduler` service visits deployments on a [60-second loop][prefect.settings.Settings.PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS] and attempts to create up to [100][prefect.settings.Settings.PREFECT_ORION_SERVICES_SCHEDULER_MAX_RUNS] scheduled flow runs up to [100 days][prefect.settings.Settings.PREFECT_ORION_SERVICES_SCHEDULER_MAX_SCHEDULED_TIME] in the future. 

This means that if a deployment has an hourly schedule, the default settings will create runs for the next 4 days (or 100 hours). If it has a weekly schedule, the default settings will maintain the next 14 runs (up to 100 days in the future).

!!! info "The `Scheduler` does not affect execution"
    The Orion `Scheduler` service only creates new flow runs and places them in `Scheduled` states. It is not at all involved in flow or task execution. Making the `Scheduler` loop faster will not make flows start or run faster.

