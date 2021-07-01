---
sidebarDepth: 2
editLink: false
---
# Adjustments
---
Schedule adjustments are functions that accept a `datetime` and modify it in some way.

Adjustments have the signature `Callable[[datetime], datetime]`.

## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-adjustments-add'><p class="prefect-class">prefect.schedules.adjustments.add</p>(interval)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/adjustments.py#L14">[source]</a></span></div>
<p class="methods">Adjustment that adds a specified interval to the date.<br><br>**Args**:     <ul class="args"><li class="args">`interval (timedelta)`: the amount of time to add</li></ul> **Returns**:     <ul class="args"><li class="args">`Callable[[datetime], bool]`: the adjustment function</li></ul></p>|
 | <div class='method-sig' id='prefect-schedules-adjustments-next-weekday'><p class="prefect-class">prefect.schedules.adjustments.next_weekday</p>(dt)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/adjustments.py#L31">[source]</a></span></div>
<p class="methods">Adjustment that advances a date to the next weekday. If the date is already a weekday, it is returned unadjusted.<br><br>**Args**:     <ul class="args"><li class="args">`dt (datetime)`: the datetime to adjust</li></ul> **Returns**:     <ul class="args"><li class="args">`datetime`: the adjusted datetime</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>