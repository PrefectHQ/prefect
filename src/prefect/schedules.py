# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
from crontab import CronTab
import itertools
from datetime import datetime, timedelta
import pendulum
from typing import Iterable, List
from prefect.utilities.datetimes import ensure_tz_aware


class Schedule:
    """
    Base class for Schedules

    Args:
        - start_date (datetime, optional): an optional start date for the schedule
        - end_date (datetime, optional): an optional end date for the schedule
    """

    def __init__(self, start_date: datetime = None, end_date: datetime = None):
        if start_date is not None:
            start_date = ensure_tz_aware(start_date)
        if end_date is not None:
            end_date = ensure_tz_aware(end_date)
        self.start_date = start_date
        self.end_date = end_date

    def next(self, n: int, on_or_after: datetime = None) -> List[datetime]:
        """
        Retrieve next scheduled dates.

        Args:
            - n (int): the number of future scheduled dates to return
            - on_or_after (datetime, optional): date to begin returning from

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

    Args:
        - start_date (datetime): first date of schedule
        - interval (timedelta): interval on which this schedule occurs
        - end_date (datetime, optional): an optional end date for the schedule

    Raises:
        - ValueError: if start_date is not a datetime
        - ValueError: if provided interval is negative
    """

    def __init__(
        self, start_date: datetime, interval: timedelta, end_date: datetime = None
    ) -> None:
        if not isinstance(start_date, datetime):
            raise TypeError("`start_date` must be a datetime.")
        elif interval.total_seconds() <= 0:
            raise ValueError("Interval must be positive")

        self.interval = interval
        super().__init__(start_date=start_date, end_date=end_date)

    def next(self, n: int, on_or_after: datetime = None) -> List[datetime]:
        """
        Retrieve next scheduled dates.

        Args:
            - n (int): the number of future scheduled dates to return
            - on_or_after (datetime, optional): date to begin returning from

        Returns:
            - list: list of next scheduled dates
        """
        if on_or_after is None:
            on_or_after = pendulum.now("utc")

        assert isinstance(on_or_after, datetime)  # mypy assertion
        assert isinstance(self.start_date, datetime)  # mypy assertion

        on_or_after = ensure_tz_aware(on_or_after)
        first_interval = int(
            (on_or_after - self.start_date).total_seconds()
            / self.interval.total_seconds()
        )

        dates = []

        for i in range(n):
            next_date = self.start_date + self.interval * (first_interval + i)
            if self.end_date and next_date > self.end_date:
                break
            dates.append(next_date)

        return dates


class CronSchedule(Schedule):
    """
    Cron scheduler.

    Args:
        - cron (str): a valid cron string
        - start_date (datetime, optional): an optional start date for the schedule
        - end_date (datetime, optional): an optional end date for the schedule

    Raises:
        - ValueError: if the cron string is invalid
    """

    def __init__(
        self, cron: str, start_date: datetime = None, end_date: datetime = None
    ) -> None:
        # build cron object to check the cron string - will raise an error if it's invalid
        CronTab(cron)
        self.cron = cron
        super().__init__(start_date=start_date, end_date=end_date)

    def next(self, n: int, on_or_after: datetime = None) -> List[datetime]:
        """
        Retrieve next scheduled dates.

        Args:
            - n (int): the number of future scheduled dates to return
            - on_or_after (datetime, optional): date to begin returning from

        Returns:
            - list: list of next scheduled dates
        """
        if on_or_after is None:
            on_or_after = pendulum.now("utc")

        if self.start_date is not None:
            on_or_after = max(on_or_after, self.start_date)

        assert isinstance(on_or_after, datetime)  # mypy assertion
        on_or_after = ensure_tz_aware(on_or_after)

        cron = CronTab(self.cron)

        # subtract one second because we want to include on_or_after as a possible date
        next_date = on_or_after - timedelta(seconds=1)

        dates = []
        for i in range(n):
            next_date = next_date + timedelta(seconds=cron.next(next_date))
            if self.end_date and next_date > self.end_date:
                break
            dates.append(next_date)

        return dates
