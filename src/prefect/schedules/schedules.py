import heapq
import itertools
import operator
from datetime import datetime, timedelta
from typing import Callable, Iterable, List, Optional, cast

import prefect.schedules.adjustments
import prefect.schedules.clocks
import prefect.schedules.filters


class Schedule:
    """
    Schedules are used to generate dates for flow runs. Scheduling logic works as follows:
    First off, candidate events are emitted by one or more `clocks`. Secondly, if filters were
    specified, they are applied in this order: all `filters` must return True, at least one
    `or_filter` must return True, then all `not_filters` must return False. Thridly, events
    that pass the filters are adjusted based on the `adjustments` functions. Finally, the
    resulting `datetime` is emitted.

    Example:

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

    Args:
        - clocks (List[prefect.schedules.clocks.Clock]): one or more clocks that emit events
            for this schedule. At least one clock is required.
        - filters (List[Callable[[datetime], bool]]): a list of filter functions that will be
            used to filter events. Events will only be emitted if all `filters` are True.
        - or_filters (List[Callable[[datetime], bool]]): a list of filter functions that
            will be used to filter events. Events will only be emitted if at least one of the
            `or_filters` are True
        - not_filters (List[Callable[[datetime], bool]]): a list of filter functions that
            will be used to filter events. Events will only be emitted if all `not_filters` are
            False
        - adjustments (List[Callable[[datetime], datetime]]): a list of adjustment functions
            that will be applied to dates that pass all filters. If more than one adjustment
            if provided, they will be applied in sequence.
    """

    def __init__(
        self,
        clocks: List["prefect.schedules.clocks.Clock"],
        filters: List[Callable[[datetime], bool]] = None,
        or_filters: List[Callable[[datetime], bool]] = None,
        not_filters: List[Callable[[datetime], bool]] = None,
        adjustments: List[Callable[[datetime], datetime]] = None,
    ):
        if not isinstance(clocks, Iterable):
            raise TypeError("clocks should be a list of clocks.")
        self.clocks = clocks
        self.filters = filters or []
        self.or_filters = or_filters or []
        self.not_filters = not_filters or []
        self.adjustments = adjustments or []

    @property
    def start_date(self) -> Optional[datetime]:
        return min([c.start_date for c in self.clocks if c.start_date], default=None)

    @property
    def end_date(self) -> Optional[datetime]:
        return max([c.end_date for c in self.clocks if c.end_date], default=None)

    def next(
        self, n: int, after: datetime = None, return_events: bool = False
    ) -> List[datetime]:
        """
        Retrieve the next `n` scheduled times, optionally after a specified date.

        Because clocks are potentially infinite, and filters may be prohibitive, this operation
        will stop after checking 10,000 events, no matter how many valid dates have been found.

        Args:
            - n (int): the number of dates to return
            - after (datetime): an optional starting point. All returned dates will be after this
                time.
            - return_events (bool, optional): an optional boolean specifying whether to return
                a full Clock Event or just the start_time of the associated event; defaults to
                `False`

        Returns:
            - List[datetime]: a list of datetimes
        """
        events = []
        counter = 0
        for event in self._get_clock_events(after=after):
            counter += 1
            if self._check_filters(event.start_time):
                event.start_time = self._apply_adjustments(event.start_time)
                events.append(event if return_events else event.start_time)
            if len(events) == n or counter >= 10000:
                break

        return events  # type: ignore

    def _get_clock_events(
        self, after: datetime = None
    ) -> Iterable["prefect.schedules.clocks.ClockEvent"]:
        """
        A generator of events emitted by the schedule's clocks.

        Events are sorted and unique (if two clocks emit the same date, it is only yielded once.)

        Args:
            - after (datetime): an optional starting point. All returned dates will be after this
                time.

        Returns:
            - Iterable[datetime]: An iterator of dates (as a generator)

        """
        clock_events = [clock.events(after=after) for clock in self.clocks]
        sorted_events = heapq.merge(*clock_events)

        # this next line yields items only if they differ from the previous item, which means
        # this generator only yields unique events (since the input is sorted)
        #
        # code from `unique_justseen()` at
        # https://docs.python.org/3/library/itertools.html#itertools-recipes
        unique_events = map(
            next, map(operator.itemgetter(1), itertools.groupby(sorted_events))
        )  # type: Iterable[prefect.schedules.clocks.ClockEvent]
        yield from unique_events

    def _check_filters(self, dt: datetime) -> bool:
        """
        Check the schedule's filters:
            - all `filters` must pass
            - at least one of the `or_filters` must pass
            - none of the `not_filters` may pass

        Args:
            - dt (datetime): the date to check filters against

        Returns:
            - bool: True if the filters pass; False otherwise
        """
        # check that all `filters` pass
        all_filters = all(filter_fn(dt) for filter_fn in self.filters)
        # check that at least one `or_filter` passes
        or_filters = (
            any(filter_fn(dt) for filter_fn in self.or_filters)
            if self.or_filters
            else True
        )
        # check that no `not_filters` pass
        not_filters = (
            not any(filter_fn(dt) for filter_fn in self.not_filters)
            if self.not_filters
            else True
        )
        # return True if all three filter types passed
        return all_filters and or_filters and not_filters

    def _apply_adjustments(self, dt: datetime) -> datetime:
        """
        Apply the schedule's adjustments to a date.

        Args:
            - dt (datetime): the date to adjust

        Returns:
            - datetime: the adjusted date
        """
        # run date through adjustment pipeline
        for adjust_fn in self.adjustments:
            dt = adjust_fn(dt)
        return dt


# FIXME the proper signature for this function should be:
# interval (required), start_date (optional), end_date (optional)
# but start_date is currently first to maintain compatibility with an older version of
# Prefect
def IntervalSchedule(
    start_date: datetime = None, interval: timedelta = None, end_date: datetime = None
) -> Schedule:
    """
    A schedule formed by adding `timedelta` increments to a start_date.

    IntervalSchedules only support intervals of one minute or greater.

    NOTE: If the `IntervalSchedule` start time is provided with a DST-observing timezone,
    then the clock will adjust itself appropriately. Intervals greater than 24
    hours will follow DST conventions, while intervals of less than 24 hours will
    follow UTC intervals. For example, an hourly clock will fire every UTC hour,
    even across DST boundaries. When clocks are set back, this will result in two
    runs that *appear* to both be scheduled for 1am local time, even though they are
    an hour apart in UTC time. For longer intervals, like a daily clock, the
    interval clock will adjust for DST boundaries so that the clock-hour remains
    constant. This means that a daily clock that always fires at 9am will observe
    DST and continue to fire at 9am in the local time zone.

    Note that this behavior is different from the `CronSchedule`.

    Args:
        - interval (timedelta): interval on which this clock occurs
        - start_date (datetime, optional): first date of clock. If None, will be set to
            "2019-01-01 00:00:00 UTC"
        - end_date (datetime, optional): an optional end date for the clock

    Raises:
        - ValueError: if provided interval is less than one minute
    """
    return Schedule(
        clocks=[
            prefect.schedules.clocks.IntervalClock(
                interval=cast(timedelta, interval),  # due to FIXME, above
                start_date=start_date,
                end_date=end_date,
            )
        ]
    )


def CronSchedule(
    cron: str,
    start_date: datetime = None,
    end_date: datetime = None,
    day_or: bool = None,
) -> Schedule:
    """
    Cron clock.

    NOTE: If the `CronSchedule's` start time is provided with a DST-observing timezone,
    then the clock will adjust itself. Cron's rules for DST are based on clock times,
    not intervals. This means that an hourly cron clock will fire on every new clock
    hour, not every elapsed hour; for example, when clocks are set back this will result
    in a two-hour pause as the clock will fire *the first time* 1am is reached and
    *the first time* 2am is reached, 120 minutes later. Longer clocks, such as one
    that fires at 9am every morning, will automatically adjust for DST.

    Note that this behavior is different from the `IntervalSchedule`.

    Args:
        - cron (str): a valid cron string
        - start_date (datetime, optional): an optional start date for the clock
        - end_date (datetime, optional): an optional end date for the clock
        - day_or (bool, optional): Control how croniter handles `day` and `day_of_week` entries.
            Defaults to True, matching cron which connects those values using OR.
            If the switch is set to False, the values are connected using AND. This behaves like
            fcron and enables you to e.g. define a job that executes each 2nd friday of a month
            by setting the days of month and the weekday.

    Raises:
        - ValueError: if the cron string is invalid
    """
    return Schedule(
        clocks=[
            prefect.schedules.clocks.CronClock(
                cron=cron, start_date=start_date, end_date=end_date, day_or=day_or
            )
        ]
    )
