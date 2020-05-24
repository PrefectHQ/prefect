# PIN 10: Flexible Schedules

Date: May 16, 2019
Author: Jeremiah Lowin

## Status

Accepted

## Context

Prefect exposes a number of different `Schedule` objects that allow users to specify when they want flows to run. Schedules can be run, for example, on an interval, according to a cron string, on a single specific date, or any union thereof.

It is common, particularly in the business world, to encounter schedules that are repeated but not regular. Prefect has a disproportionate number of users in the financial services industry, where trading-day and business-day calendars are common, as are schedules that fire on market-open and market-close. There is also demand for schedules that fire near, but not necessarily on, a specific date: the first weekday at least 5 days after month end, for example; or the next business day from any date.

Building a custom schedule in Prefect is trivial. However, it is important for users to be able to share scheduling logic with each other and services like Prefect Cloud. Therefore, rather than having users write custom functions (which would be opaque), we would like to provide a vocabulary of useful transformations that could be safely JSON-serialized and run on any remote machine.

## Proposal

Schedules have three components:

- a list of `clocks`
- a list of `filters`
- a list of `adjustments`

First, clocks generate potential dates for scheduling. Then, the filters are applied to the date. If any filter returns `False`, the date is skipped. Lastly, the adjustments are applied to any dates that pass the filters.

For example, a schedule that fires every day at 6pm could use a daily Interval clock; no filters; and no adjustments.

A schedule that fires every day at 3pm and 6pm could use an hourly interval clock; a filter for the hours of 3pm and 6pm; and no adjustments.

A schedule that only fires on businesses days could use a daily interval clock; a filter for weekdays; and no adjustments.

A schedule that fires on the last weekday before the 15th of the month could use a monthly interval clock (for the 15th); no filters; and a "previous weekday" adjustment.

A schedule that fires on trading days could use a daily interval clock; a weekday and non-holiday filter; and no adjustments.

### Clock

Clocks are essentially the same as Prefect's current `Schedule` classes: they emit `datetimes` on some predetermined schedule - for example, an `IntervalClock` might fire hourly or daily (similar to the current `IntervalSchedule`) and a `CronClock` might fire on a time dictated by a cron string.

### Filter

Filters are functions that accept a `datetime` and return `True` if it is valid or `False` if it should be skipped:

```python
def business_day(dt: datetime) -> bool:
    return dt.weekday() <= 4
```

When multiple filters are passed, they must all be `True` for a date to be used.

### Adjustment

Adjustments are less common, but can be used to adjust a date forward or backward. For example, they could round it to the nearest time, do business-day adjustments, or any other transformation. A list of adjustments will process a date in sequence.

```python
def next_business_day(dt: datetime) -> datetime:
    while not business_day(dt):
        dt = dt.add(days=1)
    return dt
```

### Schedules

Therefore, a Schedule is now just a combination of these three components.

```python
class Schedule:
    def __init__(
            self,
            clocks: List[Clock],
            filters: List[Callable[[dt], bool]],
            adjustments: List[Callable[[dt], dt]]):
        pass
```

## Consequences

Adopting this construction will allow flexible, custom schedules by composing well-understood and small building blocks. References to those components (clocks, filters, adjustments) can be safely deserialized on remote computers.

Old schedule objects will need to be deprecated. We could maintain compatibility for a release cycle, or translate old schedules automatically into new schedules on deserialization.

## Actions
