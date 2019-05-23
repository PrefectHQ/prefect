# Schedules

## Overview

Prefect assumes that flows can be run at any time, for any reason. However, it is often useful to automate flow runs at certain times. For this purpose, Prefect provides a versatile `Schedule` object.

## Design

Prefect `Schedules` have three components: 
- a `clock` that emits events. For example, an `IntervalClock` might emit an event every hour; a `CronClock` could emit an event according to a cron string. A single schedule may include multiple clocks. 
- `filters` that decide whether an event should be included or not. For example, a filter might be set that only allows events on weekdays, or only during business hours. 
- `adjustments` that can be used to modify events that pass the filters. For example, an adjustment could advance an event to the next business day, or the last business day of the month.

These three components allow users to combine simple functions into complex behavior.

### Clocks

#### Interval clocks

The most basic Prefect clock is the `IntervalClock`. It takes an `interval` argument and emits events on a regular basis. An optional `start_date` can be provided, in which case the intervals will be relative to that date; an `end_date` can be provided as well.

Prefect does not support sub-minute schedules.

```python
from datetime import timedelta
from prefect.schedules import Schedule
from prefect.schedules.clocks import IntervalClock

schedule = Schedule(clocks=[IntervalClock(timedelta(hours=24))])

schedule.next(5)
```

::: warning Daylight Saving Time
If the `IntervalClock` start time is provided with a DST-observing timezone, then the schedule will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. For example, an hourly schedule will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that _appear_ to both be scheduled for 1am local time, even though they are an hour apart in UTC time. For longer intervals, like a daily schedule, the interval schedule will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily schedule that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.

Note that this behavior is different from the `CronClock`.
:::

#### Cron clocks

Clocks can also be generated from cron strings with Prefect's `CronClock`.

```python
from datetime import timedelta
from prefect.schedules import Schedule
from prefect.schedules.clocks import CronClock

schedule = Schedule(clocks=[CronClock("0 0 * * *")])

schedule.next(5)
```

::: warning Daylight Saving Time
If the `CronClock's` start time is provided with a DST-observing timezone, then the schedule will adjust itself. Cron's rules for DST are based on clock times, not intervals. This means that an hourly cron schedule will fire on every new clock hour, not every elapsed hour; for example, when clocks are set back this will result in a two-hour pause as the schedule will fire _the first time_ 1am is reached and _the first time_ 2am is reached, 120 minutes later. Longer schedules, such as one that fires at 9am every morning, will automatically adjust for DST.

Note that this behavior is different from the `IntervalClock`.
:::

#### Date clocks

For more ad-hoc schedules, Prefect supplies a `DatesClock` that can be instantiated with all the events it should fire.

```python
from datetime import timedelta
import pendulum
from prefect.schedules import Schedule
from prefect.schedules.clocks import DatesClock

schedule = Schedule(
    clocks=[DatesClock([pendulum.now().add(days=1), pendulum.now().add(days=2)])])

schedule.next(2)
```

### Filters

Prefect provides a variety of event filters, including:
    - `between` (allows events between two dates)
    - `between_times` (allows events between two times)
    - `between_dates` (allows events between two calendar dates)
    - `is_weekday` (allows events on weekdays)
    - `is_weekend` (allows events on weekends)

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
    not_filters=[filters.between_dates(1, 1, 1, 31)]
)
```

### Adjustments

Adjustments allow schedules to modify dates that are emitted by clocks and pass a filter bank:
    - `add` (adds an interval to the date)
    - `next_weekday` (advances the date to the next weekday)
