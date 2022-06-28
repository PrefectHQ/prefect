# Schedules

## Overview

Prefect assumes that flows can be run at any time, for any reason. However, it is often useful to automate flow runs at certain times. Simple schedules can be attached to Flows via the `schedule` keyword argument. For more detailed or complex schedules, Prefect provides a versatile `Schedule` object which allows for subtle date time adjustments and filtering, along with updating `Parameter` values based on the scheduled time.

## Simple Schedules

Simple schedules can be attached to Flows via the `schedule` keyword argument:

```python
from prefect import task, Flow
from datetime import timedelta
from prefect.schedules import IntervalSchedule


@task
def say_hello():
    print("Hello, world!")


schedule = IntervalSchedule(interval=timedelta(minutes=2))

with Flow("Hello", schedule=schedule) as flow:
    say_hello()

flow.run()
```

You can see a cron schedule in [this example](https://github.com/PrefectHQ/prefect/blob/d61fa6aac9330c5817cc8e8b8f8cca2d634ea7e1/examples/old/daily_github_stats_to_airtable.py).

## Complex Schedules

Prefect `Schedules` have three components:

- a `clock` that emits events. For example, an `IntervalClock` might emit an event every hour; a `CronClock` could emit an event according to a cron string. A single schedule may include multiple clocks.  Clocks can also be used to specify varying `Parameter` values for each flow run.
- `filters` that decide whether an event should be included or not. For example, a filter might be set that only allows events on weekdays, or only during business hours.
- `adjustments` that can be used to modify events that pass the filters. For example, an adjustment could advance an event to the next business day, or the last business day of the month.

These three components allow users to combine simple functions into complex behavior.

Note that many examples here use the [Pendulum](https://pendulum.eustace.io/) Python package for easy datetime manipulation. Pendulum isn’t required, but it’s employed in many schedule use cases, such as start and end dates.

### Clocks

#### Interval clocks

The most basic Prefect clock is the [`IntervalClock`](/api/latest/schedules/clocks.html#intervalclock). It takes an `interval` argument and emits events on a regular basis. An optional `start_date` can be provided, in which case the intervals will be relative to that date; an `end_date` can be provided as well.

Prefect does not support sub-minute schedules.

```python
from datetime import timedelta
from prefect.schedules import Schedule
from prefect.schedules.clocks import IntervalClock

schedule = Schedule(clocks=[IntervalClock(timedelta(hours=24))])

schedule.next(5)
```

!!! tip Time Zones
    Want to pin your schedule to a time zone? Specify a `start_date` corresponding to that time zone for your clock:

    ```python
    import pendulum

    schedules.clocks.IntervalClock(
        start_date=pendulum.datetime(2019, 1, 1, tz="America/New_York"),
        interval=timedelta(days=1),
    )
    ```



!!! warning Daylight Saving Time
    If the `IntervalClock` start time is provided with a DST-observing timezone, then the schedule will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. For example, an hourly schedule will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that _appear_ to both be scheduled for 1am local time, even though they are an hour apart in UTC time. For longer intervals, like a daily schedule, the interval schedule will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily schedule that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.

    Note that this behavior is different from the `CronClock`.


#### Cron clocks

Clocks can also be generated from cron strings with the Prefect [`CronClock`](/api/latest/schedules/clocks.html#cronclock).

```python
from datetime import timedelta
from prefect.schedules import Schedule
from prefect.schedules.clocks import CronClock

schedule = Schedule(clocks=[CronClock("0 0 * * *")])

schedule.next(5)
```

!!! warning Daylight Saving Time
    If the `CronClock` start time is provided with a DST-observing timezone, then the schedule will adjust itself. Cron's rules for DST are based on clock times, not intervals. This means that an hourly cron schedule will fire on every new clock hour, not every elapsed hour; for example, when clocks are set back this will result in a two-hour pause as the schedule will fire _the first time_ 1am is reached and _the first time_ 2am is reached, 120 minutes later. Longer schedules, such as one that fires at 9am every morning, will automatically adjust for DST.

    Note that this behavior is different from the `IntervalClock`.


#### Date clocks

For more ad-hoc schedules, Prefect provides a [`DatesClock`](/api/latest/schedules/clocks.html#datesclock) that only fires on specific, user-provided dates.

```python
import pendulum
from prefect.schedules import Schedule
from prefect.schedules.clocks import DatesClock

schedule = Schedule(
    clocks=[DatesClock([pendulum.now().add(days=1), pendulum.now().add(days=2)])]
)

schedule.next(2)
```

#### Recurrence Rule Clocks

The Prefect [`RRuleClock`](/api/latest/schedules/clocks.html#rruleclock) supports [iCal recurrence rules](https://icalendar.org/iCalendar-RFC-5545/3-8-5-3-recurrence-rule.html) (RRules), which provide convenient syntax for creating repetitive schedules. Schedules can repeat on a frequency from yearly down to every minute. 

`RRuleClock` uses the [dateutil rrule module](https://dateutil.readthedocs.io/en/stable/rrule.html) to specify iCal recurrence rules.

For example, `RRuleClock` can specify a schedule recurring every day for a week:

```python
from dateutil.rrule import rrule, DAILY
import pendulum
from prefect.schedules import Schedule
from prefect.schedules.clocks import RRuleClock

start_date = pendulum.now().add(days=1)
r_rule = rrule(freq=DAILY, count=7)

schedule = Schedule(clocks=[RRuleClock(r_rule, start_date=start_date)])
```

#### Varying Parameter Values

All clocks support an optional `parameter_defaults` argument that allows users to specify varying `Parameter` values for each flow run generated from this clock.  For example, suppose we have the following flow that logs the value of the `Parameter` that is passed to it:

```python
import prefect
from prefect import task, Flow, Parameter


@task
def log_param(p):
    logger = prefect.context["logger"]
    logger.info(f"Received parameter value {p}")


p = Parameter("p", default=None, required=False)

with Flow("Varying Parameters") as flow:
    log_param(p)
```

Each time we run this flow, we can optionally pass a new value for the `p` parameter; if we were to run this flow on a fixed schedule, we might want to pass different values for `p` depending on which schedule is being called - we can do this through the use of clocks:

```python
import datetime
from prefect.schedules import clocks, Schedule

now = datetime.datetime.utcnow()

clock1 = clocks.IntervalClock(
    start_date=now,
    interval=datetime.timedelta(minutes=1),
    parameter_defaults={"p": "CLOCK 1"},
)
clock2 = clocks.IntervalClock(
    start_date=now + datetime.timedelta(seconds=30),
    interval=datetime.timedelta(minutes=1),
    parameter_defaults={"p": "CLOCK 2"},
)

# the full schedule
schedule = Schedule(clocks=[clock1, clock2])

flow.schedule = schedule  # set the schedule on the Flow
flow.run()
```

When we run this flow on its schedule as above, we will see the parameter value change in the log with each new run:

```
...
INFO - prefect.Task: log_param | Received parameter value CLOCK 2
...
INFO - prefect.Task: log_param | Received parameter value CLOCK 1
...
```

### Filters

Prefect provides a variety of event filters, including:

- `on_datetime` (allows events on a certain datetime)
- `on_date` (allows events on a certain date, for example March 15)
- `at_time` (allows events at a certain time, such as 3:30pm)
- `between_datetimes` (allows events between two specific datetimes)
- `between_times` (allows events between two times, for example 9am and 5pm)
- `between_dates` (allows events between two calendar dates, such as January 1 and March 31)
- `is_weekday` (allows events on weekdays)
- `is_weekend` (allows events on weekends)
- `is_month_end` (allows events on month-end)

Filters can be provided to schedules in three different ways:

- `filters`: ALL filters must return `True` for the event to be included
- `or_filters`: AT LEAST ONE filter must return `True` for the even to be included
- `not_filters`: NO filters can return `True` for the event to be included

```python
schedules.Schedule(
    # fire every hour
    clocks=[clocks.IntervalClock(timedelta(hours=1))],
    # but only on weekdays
    filters=[filters.is_weekday],
    # and only at 9am or 3pm
    or_filters=[
        filters.between_times(pendulum.time(9), pendulum.time(9)),
        filters.between_times(pendulum.time(15), pendulum.time(15)),
    ],
    # and not in January
    not_filters=[filters.between_dates(1, 1, 1, 31)],
)
```

### Adjustments

Adjustments allow schedules to modify dates that are emitted by clocks and pass a collection of filters:

- `add` (adds an interval to the date)
- `next_weekday` (advances the date to the next weekday)

```python
schedules.Schedule(
    # fire every day
    clocks=[clocks.IntervalClock(timedelta(days=1))],
    # filtered for month ends
    filters=[filters.is_month_end],
    # and run on the next weekday
    adjustments=[adjustments.next_weekday],
)
```
