---
sidebarDepth: 2
editLink: false
---
# Schedules
---
 ## Schedule
 <div class='class-sig' id='prefect-schedules-schedule'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.Schedule</p>(start_date=None, end_date=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L10">[source]</a></span></div>

Base class for Schedules

**Args**:     <ul class="args"><li class="args">`start_date (datetime, optional)`: an optional start date for the schedule     </li><li class="args">`end_date (datetime, optional)`: an optional end date for the schedule</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-schedule-next'><p class="prefect-class">prefect.schedules.Schedule.next</p>(n, after=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L27">[source]</a></span></div>
<p class="methods">Retrieve next scheduled dates.<br><br>**Args**:     <ul class="args"><li class="args">`n (int)`: the number of future scheduled dates to return     </li><li class="args">`after (datetime, optional)`: the first result will be after this date</li></ul>**Returns**:     <ul class="args"><li class="args">`list[datetime]`: a list of datetimes</li></ul></p>|
 | <div class='method-sig' id='prefect-schedules-schedule-serialize'><p class="prefect-class">prefect.schedules.Schedule.serialize</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L40">[source]</a></span></div>
<p class="methods"></p>|

---
<br>

 ## IntervalSchedule
 <div class='class-sig' id='prefect-schedules-intervalschedule'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.IntervalSchedule</p>(start_date, interval, end_date=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L46">[source]</a></span></div>

A schedule formed by adding `timedelta` increments to a start_date.

IntervalSchedules only support intervals of one minute or greater.

NOTE: If the `IntervalSchedule` start time is provided with a DST-observing timezone, then the schedule will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. For example, an hourly schedule will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that *appear* to both be scheduled for 1am local time, even though they are an hour apart in UTC time. For longer intervals, like a daily schedule, the interval schedule will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily schedule that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.

Note that this behavior is different from the `CronSchedule`.

**Args**:     <ul class="args"><li class="args">`start_date (datetime)`: first date of schedule     </li><li class="args">`interval (timedelta)`: interval on which this schedule occurs     </li><li class="args">`end_date (datetime, optional)`: an optional end date for the schedule</li></ul>**Raises**:     <ul class="args"><li class="args">`TypeError`: if start_date is not a datetime     </li><li class="args">`ValueError`: if provided interval is less than one minute</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-intervalschedule-next'><p class="prefect-class">prefect.schedules.IntervalSchedule.next</p>(n, after=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L86">[source]</a></span></div>
<p class="methods">Retrieve next scheduled dates.<br><br>**Args**:     <ul class="args"><li class="args">`n (int)`: the number of future scheduled dates to return     </li><li class="args">`after (datetime, optional)`: the first result will be after this date</li></ul>**Returns**:     <ul class="args"><li class="args">`list`: list of next scheduled dates</li></ul></p>|

---
<br>

 ## CronSchedule
 <div class='class-sig' id='prefect-schedules-cronschedule'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.CronSchedule</p>(cron, start_date=None, end_date=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L135">[source]</a></span></div>

Cron scheduler.

NOTE: If the `CronSchedule's` start time is provided with a DST-observing timezone, then the schedule will adjust itself. Cron's rules for DST are based on clock times, not intervals. This means that an hourly cron schedule will fire on every new clock hour, not every elapsed hour; for example, when clocks are set back this will result in a two-hour pause as the schedule will fire *the first time* 1am is reached and *the first time* 2am is reached, 120 minutes later. Longer schedules, such as one that fires at 9am every morning, will automatically adjust for DST.

Note that this behavior is different from the `IntervalSchedule`.

**Args**:     <ul class="args"><li class="args">`cron (str)`: a valid cron string     </li><li class="args">`start_date (datetime, optional)`: an optional start date for the schedule     </li><li class="args">`end_date (datetime, optional)`: an optional end date for the schedule</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if the cron string is invalid</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-cronschedule-next'><p class="prefect-class">prefect.schedules.CronSchedule.next</p>(n, after=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L167">[source]</a></span></div>
<p class="methods">Retrieve next scheduled dates.<br><br>**Args**:     <ul class="args"><li class="args">`n (int)`: the number of future scheduled dates to return     </li><li class="args">`after (datetime, optional)`: the first result will be after this date</li></ul>**Returns**:     <ul class="args"><li class="args">`list`: list of next scheduled dates</li></ul></p>|

---
<br>

 ## UnionSchedule
 <div class='class-sig' id='prefect-schedules-unionschedule'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.UnionSchedule</p>(schedules=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L238">[source]</a></span></div>

A schedule formed by combining multiple other schedules.

Both `start_date` and `end_date` are inferred as the min / max (resp.) of all provided schedules.  Note that the schedules are not required to all be from the same timezone.  Only unique dates will be used if multiple overlapping schedules are provided.

**Args**:     <ul class="args"><li class="args">`schedules (List[Schedule])`: a list of schedules to combine</li></ul>**Example**:     
```python
    import pendulum
    from datetime import timedelta

    from prefect.schedules import CronSchedule, IntervalSchedule, UnionSchedule

    cron = CronSchedule("0 * * * *", start_date=pendulum.now("US/Eastern"))
    cron.next(2)
    # [DateTime(2019, 5, 15, 19, 0, 0, tzinfo=Timezone('US/Eastern')),
    # DateTime(2019, 5, 15, 20, 0, 0, tzinfo=Timezone('US/Eastern'))]

    first_cron = cron.next(1)[0]
    interval = IntervalSchedule(start_date=first_cron.in_timezone("US/Pacific"), interval=timedelta(minutes=30))
    interval.next(2)
    # [DateTime(2019, 5, 15, 16, 0, 0, tzinfo=Timezone('US/Pacific')),
    # DateTime(2019, 5, 15, 16, 30, 0, tzinfo=Timezone('US/Pacific'))]

    union = UnionSchedule([cron, interval])
    union.next(4)
    # [DateTime(2019, 5, 15, 19, 0, 0, tzinfo=Timezone('US/Eastern')),
    # DateTime(2019, 5, 15, 16, 30, 0, tzinfo=Timezone('US/Pacific')),
    # DateTime(2019, 5, 15, 20, 0, 0, tzinfo=Timezone('US/Eastern')),
    # DateTime(2019, 5, 15, 17, 30, 0, tzinfo=Timezone('US/Pacific'))]

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-unionschedule-next'><p class="prefect-class">prefect.schedules.UnionSchedule.next</p>(n, after=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules.py#L289">[source]</a></span></div>
<p class="methods">Retrieve next scheduled dates.<br><br>**Args**:     <ul class="args"><li class="args">`n (int)`: the number of future scheduled dates to return     </li><li class="args">`after (datetime, optional)`: the first result will be after this date</li></ul>**Returns**:     <ul class="args"><li class="args">`list`: list of next scheduled dates</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 16, 2019 at 04:54 UTC</p>