---
sidebarDepth: 2
editLink: false
---
# Clocks
---
 ## Clock
 <div class='class-sig' id='prefect-schedules-clocks-clock'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.clocks.Clock</p>(start_date=None, end_date=None, parameter_defaults=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/clocks.py#L56">[source]</a></span></div>

Base class for Clocks

**Args**:     <ul class="args"><li class="args">`start_date (datetime, optional)`: an optional start date for the clock     </li><li class="args">`end_date (datetime, optional)`: an optional end date for the clock     </li><li class="args">`parameter_defaults (dict, optional)`: an optional dictionary of default Parameter         values; if provided, these values will be passed as the Parameter values for all         Flow Runs which are run on this clock's events     </li><li class="args">`labels (List[str], optional)`: a list of labels to apply to all flow runs generated         from this Clock</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-clocks-clock-events'><p class="prefect-class">prefect.schedules.clocks.Clock.events</p>(after=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/clocks.py#L87">[source]</a></span></div>
<p class="methods">Generator that emits clock events<br><br>**Args**:     <ul class="args"><li class="args">`after (datetime, optional)`: the first result will be after this date</li></ul> **Returns**:     <ul class="args"><li class="args">`Iterable[datetime]`: the next scheduled events</li></ul></p>|

---
<br>

 ## IntervalClock
 <div class='class-sig' id='prefect-schedules-clocks-intervalclock'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.clocks.IntervalClock</p>(interval, start_date=None, end_date=None, parameter_defaults=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/clocks.py#L100">[source]</a></span></div>

A clock formed by adding `timedelta` increments to a start_date.

IntervalClocks support any interval, but if deployed to Prefect Cloud only intervals of one minute or greater are allowed.

NOTE: If the `IntervalClock` start time is provided with a DST-observing timezone, then the clock will adjust itself appropriately. Intervals greater than 24 hours will follow DST conventions, while intervals of less than 24 hours will follow UTC intervals. For example, an hourly clock will fire every UTC hour, even across DST boundaries. When clocks are set back, this will result in two runs that *appear* to both be scheduled for 1am local time, even though they are an hour apart in UTC time. For longer intervals, like a daily clock, the interval clock will adjust for DST boundaries so that the clock-hour remains constant. This means that a daily clock that always fires at 9am will observe DST and continue to fire at 9am in the local time zone.

Note that this behavior is different from the `CronClock`.

**Args**:     <ul class="args"><li class="args">`interval (timedelta)`: interval on which this clock occurs     </li><li class="args">`start_date (datetime, optional)`: first date of clock. If None, will be set to         "2019-01-01 00:00:00 UTC"     </li><li class="args">`end_date (datetime, optional)`: an optional end date for the clock     </li><li class="args">`parameter_defaults (dict, optional)`: an optional dictionary of default Parameter         values; if provided, these values will be passed as the Parameter values for all         Flow Runs which are run on this clock's events     </li><li class="args">`labels (List[str], optional)`: a list of labels to apply to all flow runs generated         from this Clock</li></ul> **Raises**:     <ul class="args"><li class="args">`TypeError`: if start_date is not a datetime     </li><li class="args">`ValueError`: if provided interval is less than or equal to zero</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-clocks-intervalclock-events'><p class="prefect-class">prefect.schedules.clocks.IntervalClock.events</p>(after=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/clocks.py#L157">[source]</a></span></div>
<p class="methods">Generator that emits clock events<br><br>**Args**:     <ul class="args"><li class="args">`after (datetime, optional)`: the first result will be after this date</li></ul> **Returns**:     <ul class="args"><li class="args">`Iterable[ClockEvent]`: the next scheduled events</li></ul></p>|

---
<br>

 ## CronClock
 <div class='class-sig' id='prefect-schedules-clocks-cronclock'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.clocks.CronClock</p>(cron, start_date=None, end_date=None, parameter_defaults=None, labels=None, day_or=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/clocks.py#L212">[source]</a></span></div>

Cron clock.

NOTE: If the `CronClock's` start time is provided with a DST-observing timezone, then the clock will adjust itself. Cron's rules for DST are based on clock times, not intervals. This means that an hourly cron clock will fire on every new clock hour, not every elapsed hour; for example, when clocks are set back this will result in a two-hour pause as the clock will fire *the first time* 1am is reached and *the first time* 2am is reached, 120 minutes later. Longer clocks, such as one that fires at 9am every morning, will automatically adjust for DST.

Note that this behavior is different from the `IntervalClock`.

NOTE: `CronClock` respects microseconds meaning for a clock that runs once a day, if the start time is `(2020, 1, 1, 0, 0, 0, 1)` then the first scheduled run will be `(2020, 1, 2, 0, 0, 0, 0)`.

**Args**:     <ul class="args"><li class="args">`cron (str)`: a valid cron string     </li><li class="args">`start_date (datetime, optional)`: an optional start date for the clock     </li><li class="args">`end_date (datetime, optional)`: an optional end date for the clock     </li><li class="args">`parameter_defaults (dict, optional)`: an optional dictionary of default Parameter         values; if provided, these values will be passed as the Parameter values for all         Flow Runs which are run on this clock's events     </li><li class="args">`labels (List[str], optional)`: a list of labels to apply to all flow runs generated         from this Clock     </li><li class="args">`day_or (bool, optional)`: Control how croniter handles `day` and `day_of_week` entries.         Defaults to True, matching cron which connects those values using OR.         If the switch is set to False, the values are connected using AND. This behaves like         fcron and enables you to e.g. define a job that executes each 2nd friday of a month         by setting the days of month and the weekday.</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the cron string is invalid</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-clocks-cronclock-events'><p class="prefect-class">prefect.schedules.clocks.CronClock.events</p>(after=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/clocks.py#L270">[source]</a></span></div>
<p class="methods">Generator that emits clock events<br><br>**Args**:     <ul class="args"><li class="args">`after (datetime, optional)`: the first result will be after this date</li></ul> **Returns**:     <ul class="args"><li class="args">`Iterable[ClockEvent]`: the next scheduled events</li></ul></p>|

---
<br>

 ## DatesClock
 <div class='class-sig' id='prefect-schedules-clocks-datesclock'><p class="prefect-sig">class </p><p class="prefect-class">prefect.schedules.clocks.DatesClock</p>(dates, parameter_defaults=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/clocks.py#L334">[source]</a></span></div>

Clock that fires on specific dates

**Args**:     <ul class="args"><li class="args">`dates (List[datetime])`: a list of `datetimes` on which the clock should fire     </li><li class="args">`parameter_defaults (dict, optional)`: an optional dictionary of default Parameter         values; if provided, these values will be passed as the Parameter values for all         Flow Runs which are run on this clock's events     </li><li class="args">`labels (List[str], optional)`: a list of labels to apply to all flow runs generated         from this Clock</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-clocks-datesclock-events'><p class="prefect-class">prefect.schedules.clocks.DatesClock.events</p>(after=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/clocks.py#L361">[source]</a></span></div>
<p class="methods">Generator that emits clock events<br><br>**Args**:     <ul class="args"><li class="args">`after (datetime, optional)`: the first result will be after this date</li></ul> **Returns**:     <ul class="args"><li class="args">`Iterable[ClockEvent]`: the next scheduled events</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>