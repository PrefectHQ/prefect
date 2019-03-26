# Schedules

## Overview

Schedules are serializable objects that describe when to run a flow. Schedules are not required, but automate the process of creating flow runs.

## Design

Schedule objects have a simple API. They must expose a `next(n, after)` method that returns the next `n` run times `after` a specific date.

Schedules may also have a `start_date` and `end_date`. Some schedules require one or both fields.

## Interval schedules

The most basic Prefect schedule is the `IntervalSchedule`. It takes a `start_date` and an `interval` and produces new runs on a regular basis.

Prefect does not support sub-minute schedules.

For example:

```python
from datetime import timedelta
import pendulum
from prefect import Flow
from prefect.schedules import IntervalSchedule

flow = Flow(
    schedule=IntervalSchedule(
        start_date=pendulum.now(),
        interval=timedelta(hours=24)))

flow.schedule.next(5)
```

::: warning Daylight Saving Time
If the `IntervalSchedule` start time is provided with a DST-observing timezone, then the schedule will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. For example, an hourly schedule will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that *appear* to both be scheduled for 1am local time, even though they are an hour apart in UTC time. For longer intervals, like a daily schedule, the interval schedule will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily schedule that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.

Note that this behavior is different from the `CronSchedule`.
:::

## Cron schedules

Prefect also includes a `CronSchedule`, which can be instantiated with a cron string.

For example:

```python
from prefect import Flow
from prefect.schedules import CronSchedule

flow = Flow(
    schedule=CronSchedule('0 0 * * *'))

flow.schedule.next(5)
```

::: warning Daylight Saving Time
If the `CronSchedule's` start time is provided with a DST-observing timezone, then the schedule will adjust itself. Cron's rules for DST are based on clock times, not intervals. This means that an hourly cron schedule will fire on every new clock hour, not every elapsed hour; for example, when clocks are set back this will result in a two-hour pause as the schedule will fire *the first time* 1am is reached and *the first time* 2am is reached, 120 minutes later. Longer schedules, such as one that fires at 9am every morning, will automatically adjust for DST.

Note that this behavior is different from the `IntervalSchedule`.
:::
