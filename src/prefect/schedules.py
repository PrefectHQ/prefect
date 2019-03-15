# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/beta-eula
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

        dates = []

        for i in range(n):
            interval = self.interval * (skip + i)
            # in order to handle daylight savings time boundries, we consider the interval
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
    Cron scheduler. Note that this schedule operates entirely in UTC and has no notion of daylight
    savings time.

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
        if after is None:
            after = pendulum.now("utc")

        # if there is a start date, advance to at least one second before the start (so that
        # the start date itself will be registered as a value schedule date)
        if self.start_date is not None:
            after = max(after, self.start_date - timedelta(seconds=1))

        assert isinstance(after, datetime)  # mypy assertion
        after = pendulum.instance(after)
        assert isinstance(after, pendulum.DateTime)  # mypy assertion

        cron = croniter(self.cron, after.in_tz("utc"))
        dates = []

        for i in range(n):
            next_date = pendulum.instance(cron.get_next(datetime))
            # because of croniter's rounding behavior, we want to avoid
            # issuing the after date
            if next_date == after:
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
