import heapq
import itertools
import operator
import warnings
from datetime import datetime, timedelta
from typing import Callable, Iterable, List, Optional

import prefect.schedules.adjustments
import prefect.schedules.clocks
import prefect.schedules.filters
from prefect.schedules.old_schedules import (
    IntervalSchedule,
    CronSchedule,
    UnionSchedule,
    OneTimeSchedule,
)


class Schedule:
    """
    Schedules are used to generate dates for flow runs. Scheduling logic works as follows:
        1. Candidate events are emitted by one or more `clocks`
        2. If filters were specified, they are applied in this order:
            - all `filters` must return True
            - at least one `or_filter` must return True
            - all `not_filters` must return False
        3. Events that pass the filters are adjusted based on the `adjustments` functions
        4. The resulting `datetime` is emitted.

    Example:

    ```python
    schedule = Schedule(
        # emit an event every hour
        clocks=[IntervalSchedule(interval=timedelta(hours=1))]
        # only include weekdays
        filters=[is_weekday]
        # only include 9am and 5pm
        or_filters=[time_between(Time(9), Time(9)), time_between(Time(17), Time(17))]
    )

    schedule.next(4) # returns the next 4 occurances of 9am and 5pm on weekdays
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

    def next(self, n: int, after: datetime = None) -> List[datetime]:
        """
        Retrieve the next `n` scheduled times, optionally after a specified date.

        Because clocks are potentially infinite, and filters may be prohibitive, this operation
        will stop after checking 10,000 events, no matter how many valid dates have been found.

        Args:
            - n (int): the number of dates to return
            - after (datetime): an optional starting point. All returned dates will be after this
                time.

        Returns:
            - List[datetime]: a list of datetimes
        """
        events = []
        counter = 0
        for event in self._get_clock_events(after=after):
            counter += 1
            if self._check_filters(event):
                adjusted_event = self._apply_adjustments(event)
                events.append(adjusted_event)
            if len(events) == n or counter >= 10000:
                break
        return events

    def _get_clock_events(self, after: datetime = None) -> Iterable[datetime]:
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
        # code from `unique_justseen()` at https://docs.python.org/3/library/itertools.html#itertools-recipes
        unique_events = map(
            next, map(operator.itemgetter(1), itertools.groupby(sorted_events))
        )  # type: Iterable[datetime]
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
