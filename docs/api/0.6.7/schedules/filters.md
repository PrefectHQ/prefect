---
sidebarDepth: 2
editLink: false
---
# Filters
---
Schedule filters are functions that accept a candidate `datetime` and return `True` if
the candidate is valid, and `False` otherwise.

Filters have the signature `Callable[[datetime], bool]`.

## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-schedules-filters-between-datetimes'><p class="prefect-class">prefect.schedules.filters.between_datetimes</p>(start, end)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/filters.py#L14">[source]</a></span></div>
<p class="methods">Filter that allows events between a start time and end time<br><br>**Args**:     <ul class="args"><li class="args">`start (datetime)`: the start datetime     </li><li class="args">`end (datetime)`: the end datetime</li></ul>**Returns**:     <ul class="args"><li class="args">`Callable[[datetime], bool]`: a filter function</li></ul></p>|
 | <div class='method-sig' id='prefect-schedules-filters-between-dates'><p class="prefect-class">prefect.schedules.filters.between_dates</p>(start_month, start_day, end_month, end_day)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/filters.py#L32">[source]</a></span></div>
<p class="methods">Filter that allows events between specific dates in each year.<br><br>For example, `between_dates(10, 15, 3, 31)` would only allow dates between October 15 and March 31 in any year.<br><br>**Args**:     <ul class="args"><li class="args">`start_month (int)`: the starting month, as a number     </li><li class="args">`start_day (int)`: the starting day, as a number     </li><li class="args">`end_month (int)`: the ending month, as a number     </li><li class="args">`end_day (int)`: the ending day, as a number</li></ul>**Returns**:     <ul class="args"><li class="args">`Callable[[datetime], bool]`: a filter function</li></ul></p>|
 | <div class='method-sig' id='prefect-schedules-filters-between-times'><p class="prefect-class">prefect.schedules.filters.between_times</p>(start, end)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/filters.py#L64">[source]</a></span></div>
<p class="methods">Filter that allows events between a start time and end time<br><br>**Args**:     <ul class="args"><li class="args">`start (time)`: the start time     </li><li class="args">`end (time)`: the end time</li></ul>**Returns**:     <ul class="args"><li class="args">`Callable[[datetime], bool]`: a filter function</li></ul></p>|
 | <div class='method-sig' id='prefect-schedules-filters-is-weekday'><p class="prefect-class">prefect.schedules.filters.is_weekday</p>(dt)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/filters.py#L88">[source]</a></span></div>
<p class="methods">Filter that only allows events on weekdays<br><br>**Args**:     <ul class="args"><li class="args">`dt (datetime)`: the candidate datetime</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: True if the date is a weekday; False otherwise</li></ul></p>|
 | <div class='method-sig' id='prefect-schedules-filters-is-weekend'><p class="prefect-class">prefect.schedules.filters.is_weekend</p>(dt)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/filters.py#L115">[source]</a></span></div>
<p class="methods">Filter that only allows events on weekends<br><br>**Args**:     <ul class="args"><li class="args">`dt (datetime)`: the candidate datetime</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: True if the date is a weekend; False otherwise</li></ul></p>|
 | <div class='method-sig' id='prefect-schedules-filters-is-month-end'><p class="prefect-class">prefect.schedules.filters.is_month_end</p>(dt)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/schedules/filters.py#L101">[source]</a></span></div>
<p class="methods">Filter that only allows events on the last day of the month<br><br>**Args**:     <ul class="args"><li class="args">`dt (datetime)`: the candidate datetime</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: True if the date is a month-end; False otherwise</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 17, 2019 at 13:42 UTC</p>