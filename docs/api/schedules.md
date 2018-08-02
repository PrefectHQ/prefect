---
sidebarDepth: 1
---

 ## Schedule

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.schedules.Schedule()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L13)</span>
Base class for Schedules

 ####  ```prefect.schedules.Schedule.next(n, on_or_after=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L18)</span>



 ## NoSchedule

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.schedules.NoSchedule()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L22)</span>
No schedule; this Flow will only run on demand.

 ####  ```prefect.schedules.NoSchedule.next(n, on_or_after=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L27)</span>



 ## IntervalSchedule

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.schedules.IntervalSchedule(start_date, interval)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L31)</span>
A schedule formed by adding `timedelta` increments to a start_date.

 ####  ```prefect.schedules.IntervalSchedule.next(n, on_or_after=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L42)</span>



 ## CronSchedule

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.schedules.CronSchedule(cron)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L57)</span>
Base class for Schedules

 ####  ```prefect.schedules.CronSchedule.next(n, on_or_after=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L63)</span>



 ## DateSchedule

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.schedules.DateSchedule(dates)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L74)</span>
Base class for Schedules

 ####  ```prefect.schedules.DateSchedule.next(n, on_or_after=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/schedules.py#L78)</span>



