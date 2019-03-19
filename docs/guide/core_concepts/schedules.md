# Schedules

## Overview

Schedules are serializable objects that describe when to run a flow. Schedules are not required, but automate the process of creating flow runs.

## Design

Schedule objects have a simple API. They must expose a `next(n, after)` method which returns the next `n` run times `after` a specific date.

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

NOTE: IntervalSchedules respect daylight saving time for intervals greater than 24 hours. An hourly schedule will fire every UTC hour, even during daylight saving boundaries. This means when clocks are set back, the interval schedule will appear to have two runs scheduled for 1am local time, but these are actually 60 minutes apart. However, for longer intervals, like a daily schedule, the interval schedule will adjust for daylight saving time boundaries so that the clock-hour remains constant. A 9am schedule followed by a 24-hour interval will fire at 9am the following day, even if a daylight saving boundary means the true interval is 23 hours or 25 hours.

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

NOTE: the schedule will respect the timezone of its `start_date`, including daylight savings time. CRON's rules for daylight saving time are based on clock times, not elapsed times. For example, an hourly cron schedule will have a two hour pause when clocks are set backward, because the schedule will fire *the first time* 1am is reached and *the second time* 2am is reached, resulting in a 2 hour pause (but firing each clock hour). This behavior is DIFFERENT from interval schedules, which observe elapsed times for intervals of less than 24 hours over DST boundaries.
