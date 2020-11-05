from datetime import datetime, timedelta
from typing import Any, Iterable, List, Set, Union

import pendulum
import pytz
from croniter import croniter


class ClockEvent:
    """
    Base class for events emitted by Clocks.
    """

    def __init__(
        self,
        start_time: datetime,
        parameter_defaults: dict = None,
        labels: List[str] = None,
    ) -> None:
        self.start_time = start_time
        self.parameter_defaults = parameter_defaults or dict()
        self.labels = labels

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, (ClockEvent, datetime)):
            return False
        if isinstance(other, datetime):
            return self.start_time == other
        return (
            self.start_time == other.start_time
            and self.parameter_defaults == other.parameter_defaults
            and self.labels == other.labels
        )

    def __gt__(self, other: Union[datetime, "ClockEvent"]) -> bool:
        if not isinstance(other, (ClockEvent, datetime)):
            raise TypeError(
                "'>' not supported between instances of 'ClockEvent' and {}".format(
                    type(other).__name__
                )
            )
        else:
            return self.start_time > other

    def __lt__(self, other: Union[datetime, "ClockEvent"]) -> bool:
        if not isinstance(other, (ClockEvent, datetime)):
            raise TypeError(
                "'<' not supported between instances of 'ClockEvent' and {}".format(
                    type(other).__name__
                )
            )
        else:
            return self.start_time < other


class Clock:
    """
    Base class for Clocks

    Args:
        - start_date (datetime, optional): an optional start date for the clock
        - end_date (datetime, optional): an optional end date for the clock
        - parameter_defaults (dict, optional): an optional dictionary of default Parameter
            values; if provided, these values will be passed as the Parameter values for all
            Flow Runs which are run on this clock's events
        - labels (List[str], optional): a list of labels to apply to all flow runs generated
            from this Clock

    """

    def __init__(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        parameter_defaults: dict = None,
        labels: List[str] = None,
    ):
        if start_date is not None:
            start_date = pendulum.instance(start_date)
        if end_date is not None:
            end_date = pendulum.instance(end_date)
        self.start_date = start_date
        self.end_date = end_date
        self.parameter_defaults = parameter_defaults or dict()
        self.labels = labels

    def events(self, after: datetime = None) -> Iterable[ClockEvent]:
        """
        Generator that emits clock events

        Args:
            - after (datetime, optional): the first result will be after this date

        Returns:
            - Iterable[datetime]: the next scheduled events
        """
        raise NotImplementedError("Must be implemented on Clock subclasses")


class IntervalClock(Clock):
    """
    A clock formed by adding `timedelta` increments to a start_date.

    IntervalClocks support any interval, but if deployed to Prefect Cloud only
    intervals of one minute or greater are allowed.

    NOTE: If the `IntervalClock` start time is provided with a DST-observing timezone,
    then the clock will adjust itself appropriately. Intervals greater than 24
    hours will follow DST conventions, while intervals of less than 24 hours will
    follow UTC intervals. For example, an hourly clock will fire every UTC hour,
    even across DST boundaries. When clocks are set back, this will result in two
    runs that *appear* to both be scheduled for 1am local time, even though they are
    an hour apart in UTC time. For longer intervals, like a daily clock, the
    interval clock will adjust for DST boundaries so that the clock-hour remains
    constant. This means that a daily clock that always fires at 9am will observe
    DST and continue to fire at 9am in the local time zone.

    Note that this behavior is different from the `CronClock`.

    Args:
        - interval (timedelta): interval on which this clock occurs
        - start_date (datetime, optional): first date of clock. If None, will be set to
            "2019-01-01 00:00:00 UTC"
        - end_date (datetime, optional): an optional end date for the clock
        - parameter_defaults (dict, optional): an optional dictionary of default Parameter
            values; if provided, these values will be passed as the Parameter values for all
            Flow Runs which are run on this clock's events
        - labels (List[str], optional): a list of labels to apply to all flow runs generated
            from this Clock

    Raises:
        - TypeError: if start_date is not a datetime
        - ValueError: if provided interval is less than or equal to zero
    """

    def __init__(
        self,
        interval: timedelta,
        start_date: datetime = None,
        end_date: datetime = None,
        parameter_defaults: dict = None,
        labels: List[str] = None,
    ):
        if not isinstance(interval, timedelta):
            raise TypeError("Interval must be a timedelta.")
        elif interval.total_seconds() <= 0:
            raise ValueError("Interval must be greater than 0.")

        self.interval = interval
        super().__init__(
            start_date=start_date,
            end_date=end_date,
            parameter_defaults=parameter_defaults,
            labels=labels,
        )

    def events(self, after: datetime = None) -> Iterable[ClockEvent]:
        """
        Generator that emits clock events

        Args:
            - after (datetime, optional): the first result will be after this date

        Returns:
            - Iterable[ClockEvent]: the next scheduled events
        """
        if after is None:
            after = pendulum.now("utc")

        start_date = self.start_date or pendulum.datetime(2019, 1, 1)

        assert isinstance(after, datetime)  # mypy assertion
        assert isinstance(start_date, pendulum.DateTime)  # mypy assertion

        after = pendulum.instance(after)

        # Use the difference between the `after` date and the `start_date` to calc the
        # number of intervals we can skip over
        skip = (after - start_date).total_seconds() / self.interval.total_seconds()

        # if the after date is before the start date, we jump to the start date
        if skip < 0:
            skip = 0
        # if the `after` date falls exactly on an interval, jump to the next interval
        elif int(skip) == skip:
            skip += 1
        # otherwise jump to the next integer interval
        else:
            skip = int(skip + 1)

        interval = self.interval * skip

        while True:
            # in order to handle daylight saving time boundries, we consider the interval
            # "days" separate from "seconds"; this allows Pendulum DST logic to work
            days = interval.days
            seconds = interval.total_seconds() - (days * 24 * 60 * 60)
            next_date = start_date.add(days=days, seconds=seconds)
            if next_date < after:
                interval += self.interval
                continue
            if self.end_date and next_date > self.end_date:
                break
            yield ClockEvent(
                start_time=next_date,
                parameter_defaults=self.parameter_defaults,
                labels=self.labels,
            )
            interval += self.interval


class CronClock(Clock):
    """
    Cron clock.

    NOTE: If the `CronClock's` start time is provided with a DST-observing timezone,
    then the clock will adjust itself. Cron's rules for DST are based on clock times,
    not intervals. This means that an hourly cron clock will fire on every new clock
    hour, not every elapsed hour; for example, when clocks are set back this will result
    in a two-hour pause as the clock will fire *the first time* 1am is reached and
    *the first time* 2am is reached, 120 minutes later. Longer clocks, such as one
    that fires at 9am every morning, will automatically adjust for DST.

    Note that this behavior is different from the `IntervalClock`.

    NOTE: `CronClock` respects microseconds meaning for a clock that runs once a day, if
    the start time is `(2020, 1, 1, 0, 0, 0, 1)` then the first scheduled run will be
    `(2020, 1, 2, 0, 0, 0, 0)`.

    Args:
        - cron (str): a valid cron string
        - start_date (datetime, optional): an optional start date for the clock
        - end_date (datetime, optional): an optional end date for the clock
        - parameter_defaults (dict, optional): an optional dictionary of default Parameter
            values; if provided, these values will be passed as the Parameter values for all
            Flow Runs which are run on this clock's events
        - labels (List[str], optional): a list of labels to apply to all flow runs generated
            from this Clock
        - day_or (bool, optional): Control how croniter handles `day` and `day_of_week` entries.
            Defaults to True, matching cron which connects those values using OR.
            If the switch is set to False, the values are connected using AND. This behaves like
            fcron and enables you to e.g. define a job that executes each 2nd friday of a month
            by setting the days of month and the weekday.

    Raises:
        - ValueError: if the cron string is invalid
    """

    def __init__(
        self,
        cron: str,
        start_date: datetime = None,
        end_date: datetime = None,
        parameter_defaults: dict = None,
        labels: List[str] = None,
        day_or: bool = None,
    ):
        # build cron object to check the cron string - will raise an error if it's invalid
        if not croniter.is_valid(cron):
            raise ValueError("Invalid cron string: {}".format(cron))
        self.cron = cron
        self.day_or = True if day_or is None else day_or
        super().__init__(
            start_date=start_date,
            end_date=end_date,
            parameter_defaults=parameter_defaults,
            labels=labels,
        )

    def events(self, after: datetime = None) -> Iterable[ClockEvent]:
        """
        Generator that emits clock events

        Args:
            - after (datetime, optional): the first result will be after this date

        Returns:
            - Iterable[ClockEvent]: the next scheduled events
        """
        tz = getattr(self.start_date, "tz", "UTC")
        if after is None:
            after = pendulum.now(tz)
        else:
            after = pendulum.instance(after).in_tz(tz)

        # if there is a start date, advance to at least one second before the start (so that
        # the start date itself will be registered as a valid clock date)
        if self.start_date is not None:
            after = max(after, self.start_date - timedelta(seconds=1))  # type: ignore

        assert isinstance(after, datetime)  # mypy assertion
        after = pendulum.instance(after)
        assert isinstance(after, pendulum.DateTime)  # mypy assertion
        assert isinstance(after.tz, pendulum.tz._Timezone)  # mypy assertion

        # croniter's DST logic interferes with all other datetime libraries except pytz
        after_localized = pytz.timezone(after.tz.name).localize(
            datetime(
                year=after.year,
                month=after.month,
                day=after.day,
                hour=after.hour,
                minute=after.minute,
                second=after.second,
                microsecond=after.microsecond,
            )
        )

        # Respect microseconds by rounding up
        if after_localized.microsecond:
            after_localized = after_localized + timedelta(seconds=1)

        cron = croniter(self.cron, after_localized, day_or=self.day_or)  # type: ignore
        dates = set()  # type: Set[datetime]

        while True:
            next_date = pendulum.instance(cron.get_next(datetime))
            # because of croniter's rounding behavior, we want to avoid
            # issuing the after date; we also want to avoid duplicates caused by
            # DST boundary issues
            if next_date.in_tz("UTC") == after.in_tz("UTC") or next_date in dates:
                next_date = pendulum.instance(cron.get_next(datetime))

            if self.end_date and next_date > self.end_date:
                break
            dates.add(next_date)
            yield ClockEvent(
                start_time=next_date,
                parameter_defaults=self.parameter_defaults,
                labels=self.labels,
            )


class DatesClock(Clock):
    """
    Clock that fires on specific dates

    Args:
        - dates (List[datetime]): a list of `datetimes` on which the clock should fire
        - parameter_defaults (dict, optional): an optional dictionary of default Parameter
            values; if provided, these values will be passed as the Parameter values for all
            Flow Runs which are run on this clock's events
        - labels (List[str], optional): a list of labels to apply to all flow runs generated
            from this Clock
    """

    def __init__(
        self,
        dates: List[datetime],
        parameter_defaults: dict = None,
        labels: List[str] = None,
    ):
        super().__init__(
            start_date=min(dates),
            end_date=max(dates),
            parameter_defaults=parameter_defaults,
            labels=labels,
        )
        self.dates = dates

    def events(self, after: datetime = None) -> Iterable[ClockEvent]:
        """
        Generator that emits clock events

        Args:
            - after (datetime, optional): the first result will be after this date

        Returns:
            - Iterable[ClockEvent]: the next scheduled events
        """
        if after is None:
            after = pendulum.now("UTC")
        yield from (
            ClockEvent(
                start_time=date,
                parameter_defaults=self.parameter_defaults,
                labels=self.labels,
            )
            for date in sorted(self.dates)
            if date > after
        )
