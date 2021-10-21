---
sidebarDepth: 2
editLink: false
---
# Schedules
---
 ## Schedule
 <div class='class-sig' id='prefect-schedules-schedules-schedule'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.schedules.Schedule</p>(clocks, filters=None, or_filters=None, not_filters=None, adjustments=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/schedules.py#L13">[source]</a></span></div>

Schedules are used to generate dates for flow runs. Scheduling logic works as follows: First off, candidate events are emitted by one or more `clocks`. Secondly, if filters were specified, they are applied in this order: all `filters` must return True, at least one `or_filter` must return True, then all `not_filters` must return False. Thridly, events that pass the filters are adjusted based on the `adjustments` functions. Finally, the resulting `datetime` is emitted.

**Example**:


```python
from datetime import time, timedelta
from prefect.schedules import Schedule, filters
from prefect.schedules.clocks import IntervalClock

schedule = Schedule(
    # emit an event every hour
    clocks=[IntervalClock(interval=timedelta(hours=1))],

    # only include weekdays
    filters=[filters.is_weekday],

    # only include 9am and 5pm
    or_filters=[
        filters.between_times(time(9), time(9)),
        filters.between_times(time(17), time(17))
    ]
)

schedule.next(4) # returns the next 4 occurences of 9am and 5pm on weekdays

```

**Args**:     <ul class="args"><li class="args">`clocks (List[prefect.schedules.clocks.Clock])`: one or more clocks that emit events         for this schedule. At least one clock is required.     </li><li class="args">`filters (List[Callable[[datetime], bool]])`: a list of filter functions that will be         used to filter events. Events will only be emitted if all `filters` are True.     </li><li class="args">`or_filters (List[Callable[[datetime], bool]])`: a list of filter functions that         will be used to filter events. Events will only be emitted if at least one of the         `or_filters` are True     </li><li class="args">`not_filters (List[Callable[[datetime], bool]])`: a list of filter functions that         will be used to filter events. Events will only be emitted if all `not_filters` are         False     </li><li class="args">`adjustments (List[Callable[[datetime], datetime]])`: a list of adjustment functions         that will be applied to dates that pass all filters. If more than one adjustment         if provided, they will be applied in sequence.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-schedules-schedule-next'><p class="prefect-class">prefect.schedules.schedules.Schedule.next</p>(n, after=None, return_events=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/schedules.py#L86">[source]</a></span></div>
<p class="methods">Retrieve the next `n` scheduled times, optionally after a specified date.<br><br>Because clocks are potentially infinite, and filters may be prohibitive, this operation will stop after checking 10,000 events, no matter how many valid dates have been found.<br><br>**Args**:     <ul class="args"><li class="args">`n (int)`: the number of dates to return     </li><li class="args">`after (datetime)`: an optional starting point. All returned dates will be after this         time.     </li><li class="args">`return_events (bool, optional)`: an optional boolean specifying whether to return         a full Clock Event or just the start_time of the associated event; defaults to         `False`</li></ul> **Returns**:     <ul class="args"><li class="args">`List[datetime]`: a list of datetimes</li></ul></p>|

---
<br>


## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-schedules-intervalschedule'><p class="prefect-class">prefect.schedules.schedules.IntervalSchedule</p>(start_date=None, interval=None, end_date=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/schedules.py#L197">[source]</a></span></div>
<p class="methods">A schedule formed by adding `timedelta` increments to a start_date.<br><br>IntervalSchedules only support intervals of one minute or greater.<br><br>NOTE: If the `IntervalSchedule` start time is provided with a DST-observing timezone, then the clock will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. For example, an hourly clock will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that *appear* to both be scheduled for 1am local time, even though they are an hour apart in UTC time. For longer intervals, like a daily clock, the interval clock will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily clock that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.<br><br>Note that this behavior is different from the `CronSchedule`.<br><br>**Args**:     <ul class="args"><li class="args">`interval (timedelta)`: interval on which this clock occurs     </li><li class="args">`start_date (datetime, optional)`: first date of clock. If None, will be set to         "2019-01-01 00:00:00 UTC"     </li><li class="args">`end_date (datetime, optional)`: an optional end date for the clock</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if provided interval is less than one minute</li></ul></p>|
 | <div class='method-sig' id='prefect-schedules-schedules-cronschedule'><p class="prefect-class">prefect.schedules.schedules.CronSchedule</p>(cron, start_date=None, end_date=None, day_or=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/schedules.py#L238">[source]</a></span></div>
<p class="methods">Cron clock.<br><br>NOTE: If the `CronSchedule's` start time is provided with a DST-observing timezone, then the clock will adjust itself. Cron's rules for DST are based on clock times, not intervals. This means that an hourly cron clock will fire on every new clock hour, not every elapsed hour; for example, when clocks are set back this will result in a two-hour pause as the clock will fire *the first time* 1am is reached and *the first time* 2am is reached, 120 minutes later. Longer clocks, such as one that fires at 9am every morning, will automatically adjust for DST.<br><br>Note that this behavior is different from the `IntervalSchedule`.<br><br>**Args**:     <ul class="args"><li class="args">`cron (str)`: a valid cron string     </li><li class="args">`start_date (datetime, optional)`: an optional start date for the clock     </li><li class="args">`end_date (datetime, optional)`: an optional end date for the clock     </li><li class="args">`day_or (bool, optional)`: Control how croniter handles `day` and `day_of_week` entries.         Defaults to True, matching cron which connects those values using OR.         If the switch is set to False, the values are connected using AND. This behaves like         fcron and enables you to e.g. define a job that executes each 2nd friday of a month         by setting the days of month and the weekday.</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the cron string is invalid</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>