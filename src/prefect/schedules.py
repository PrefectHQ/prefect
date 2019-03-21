import pytz
import itertools
from datetime import datetime, timedelta
from typing import Iterable, List

import pendulum
from croniter import croniter


class Schedule:
    """
    Base class for Schedules

    Args:
        - start_date (datetime, optional): an optional start date for the schedule
        - end_date (datetime, optional): an optional end date for the schedule
    """

    def __init__(self, start_date: datetime = None, end_date: datetime = None):
        if start_date is not None:
            start_date = pendulum.instance(start_date)
        if end_date is not None:
            end_date = pendulum.instance(end_date)
        self.start_date = start_date
        self.end_date = end_date

    def next(self, n: int, after: datetime = None) -> List[datetime]:
        """
        Retrieve next scheduled dates.

        Args:
            - n (int): the number of future scheduled dates to return
            - after (datetime, optional): the first result will be after this date

        Returns:
            - list[datetime]: a list of datetimes
        """
        raise NotImplementedError("Must be implemented on Schedule subclasses")

    def serialize(self) -> tuple:
        from prefect.serialization.schedule import ScheduleSchema

        return ScheduleSchema().dump(self)


class IntervalSchedule(Schedule):
    """
    A schedule formed by adding `timedelta` increments to a start_date.

    IntervalSchedules only support intervals of one minute or greater.

    NOTE: If the `IntervalSchedule` start time is provided with a DST-observing timezone,
    then the schedule will adjust itself appropriately. Intervals greater than 24
    hours will follow DST conventions, while intervals of less than 24 hours will
    follow UTC intervals. For example, an hourly schedule will fire every UTC hour,
    even across DST boundaries. When clocks are set back, this will result in two
    runs that *appear* to both be scheduled for 1am local time, even though they are
    an hour apart in UTC time. For longer intervals, like a daily schedule, the
    interval schedule will adjust for DST boundaries so that the clock-hour remains
    constant. This means that a daily schedule that always fires at 9am will observe
    DST and continue to fire at 9am in the local time zone.

    Note that this behavior is different from the `CronSchedule`.

    Args:
        - start_date (datetime): first date of schedule
        - interval (timedelta): interval on which this schedule occurs
        - end_date (datetime, optional): an optional end date for the schedule

    Raises:
        - TypeError: if start_date is not a datetime
        - ValueError: if provided interval is less than one minute
    """

    def __init__(
        self, start_date: datetime, interval: timedelta, end_date: datetime = None
    ):
        if not isinstance(start_date, datetime):
            raise TypeError("`start_date` must be a datetime.")
        elif interval.total_seconds() < 60:
            raise ValueError("Interval can not be less than one minute.")

        self.interval = interval
        super().__init__(start_date=start_date, end_date=end_date)

    def next(self, n: int, after: datetime = None) -> List[datetime]:
        """
        Retrieve next scheduled dates.

        Args:
            - n (int): the number of future scheduled dates to return
            - after (datetime, optional): the first result will be after this date

        Returns:
            - list: list of next scheduled dates
        """
        if after is None:
            after = pendulum.now("utc")

        assert isinstance(after, datetime)  # mypy assertion
        assert isinstance(self.start_date, pendulum.DateTime)  # mypy assertion

        after = pendulum.instance(after)

        # Use the difference between the `after` date and the `start_date` to calc the
        # number of intervals we can skip over
        skip = (after - self.start_date).total_seconds() / self.interval.total_seconds()

        # if the after date is before the start date, we jump to the start date
        if skip < 0:
            skip = 0
        # if the `after` date falls exactly on an interval, jump to the next interval
        elif int(skip) == skip:
            skip += 1
        # otherwise jump to the next integer interval
        else:
            skip = int(skip + 1)

        dates = []  # type: List[datetime]

        for i in range(n):
            interval = self.interval * (skip + i)
            # in order to handle daylight saving time boundries, we consider the interval
            # "days" separate from "seconds"; this allows Pendulum DST logic to work
            days = interval.days
            seconds = interval.total_seconds() - (days * 24 * 60 * 60)
            next_date = self.start_date.add(days=days, seconds=seconds)
            if self.end_date and next_date > self.end_date:
                break
            dates.append(next_date)

        return dates


class CronSchedule(Schedule):
    """
    Cron scheduler.

    NOTE: If the `CronSchedule's` start time is provided with a DST-observing timezone,
    then the schedule will adjust itself. Cron's rules for DST are based on clock times,
    not intervals. This means that an hourly cron schedule will fire on every new clock
    hour, not every elapsed hour; for example, when clocks are set back this will result
    in a two-hour pause as the schedule will fire *the first time* 1am is reached and
    *the first time* 2am is reached, 120 minutes later. Longer schedules, such as one
    that fires at 9am every morning, will automatically adjust for DST.

    Note that this behavior is different from the `IntervalSchedule`.

    Args:
        - cron (str): a valid cron string
        - start_date (datetime, optional): an optional start date for the schedule
        - end_date (datetime, optional): an optional end date for the schedule

    Raises:
        - ValueError: if the cron string is invalid
    """

    def __init__(
        self, cron: str, start_date: datetime = None, end_date: datetime = None
    ):
        # build cron object to check the cron string - will raise an error if it's invalid
        if not croniter.is_valid(cron):
            raise ValueError("Invalid cron string: {}".format(cron))
        self.cron = cron
        super().__init__(start_date=start_date, end_date=end_date)

    def next(self, n: int, after: datetime = None) -> List[datetime]:
        """
        Retrieve next scheduled dates.

        Args:
            - n (int): the number of future scheduled dates to return
            - after (datetime, optional): the first result will be after this date

        Returns:
            - list: list of next scheduled dates
        """
        tz = getattr(self.start_date, "tz", "UTC")
        if after is None:
            after = pendulum.now(tz)
        else:
            after = pendulum.instance(after).in_tz(tz)

        # if there is a start date, advance to at least one second before the start (so that
        # the start date itself will be registered as a valid schedule date)
        if self.start_date is not None:
            after = max(after, self.start_date - timedelta(seconds=1))

        assert isinstance(after, datetime)  # mypy assertion
        after = pendulum.instance(after)
        assert isinstance(after, pendulum.DateTime)  # mypy assertion

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
        cron = croniter(self.cron, after_localized)
        dates = []  # type: List[datetime]

        for i in range(n):
            next_date = pendulum.instance(cron.get_next(datetime))
            # because of croniter's rounding behavior, we want to avoid
            # issuing the after date; we also want to avoid duplicates caused by
            # DST boundary issues
            if next_date.in_tz("UTC") == after.in_tz("UTC") or next_date in dates:
                next_date = pendulum.instance(cron.get_next(datetime))

            if self.end_date and next_date > self.end_date:
                break
            dates.append(next_date)

        return dates


class OneTimeSchedule(IntervalSchedule):
    """
    Schedule for a single date.

    Args:
        - start_date (datetime): the start date for the schedule, which will
            also serve as the `end_date`
    """

    def __init__(self, start_date: datetime):
        super().__init__(
            start_date=start_date, interval=timedelta(days=1), end_date=start_date
        )
