# Schedules

## Overview

Schedules are serializable objects that describe when to run a flow. Schedules are not required, but automate the process of creating flow runs.

## Design

Schedule objects have a simple API. They must expose a `next(n, after)` method which returns the next `n` run times `after` a specific date.

Schedules may also have a `start_date` and `end_date`. Some schedules require one or both fields.

## Interval schedules

The most basic Prefect schedule is the `IntervalSchedule`. It takes a `start_date` and an `interval` and produces new runs on a regular basis.

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
