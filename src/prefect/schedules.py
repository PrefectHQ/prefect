# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import itertools
from datetime import datetime, timedelta
from typing import Iterable, List

import croniter


class Schedule:
    """
    Base class for Schedules
    """

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

    def serialize(self):
        from prefect.serialization.schemas.schedule import ScheduleSchema

        return ScheduleSchema().dump(self)


class NoSchedule(Schedule):
    """
    No schedule; this Flow will only run on demand.
    """

    def next(self, n: int, on_or_after: datetime = None) -> List[datetime]:
        """
        Retrieve next scheduled dates.

        Args:
            - n (int): the number of future scheduled dates to return
            - on_or_after (datetime, optional): date to begin returning from

        Returns:
            - list: list of next scheduled dates; in this case, always the empty list
        """
        return []


class IntervalSchedule(Schedule):
    """
    A schedule formed by adding `timedelta` increments to a start_date.

    Args:
        - start_date (datetime): first date of schedule
        - interval (timedelta): interval on which this schedule occurs

    Raises:
        - ValueError: if provided interval is negative
    """

    def __init__(self, start_date: datetime, interval: timedelta) -> None:
        if interval.total_seconds() <= 0:
            raise ValueError("Interval must be positive")
        self.start_date = start_date
        self.interval = interval

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
            on_or_after = datetime.utcnow()

        # infinite generator of all dates in the series
        all_dates = (
            self.start_date + i * self.interval
            for i in itertools.count(start=0, step=1)
        )
        # filter generator for only dates on or after the requested date
        upcoming_dates = filter(lambda d: d >= on_or_after, all_dates)  # type: ignore
        # get the next n items from the generator
        return list(itertools.islice(upcoming_dates, n))


class CronSchedule(Schedule):
    """
    Cron scheduler.

    Args:
        - cron (str): a valid cron string
    """

    def __init__(self, cron: str) -> None:
        # build cron object to check the cron string - will raise an error if it's invalid
        croniter.croniter(cron)
        self.cron = cron

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
            on_or_after = datetime.utcnow()

        # croniter only supports >, not >=, so we subtract a microsecond
        on_or_after -= timedelta(seconds=1)

        cron = croniter.croniter(self.cron, on_or_after)
        return list(itertools.islice(cron.all_next(datetime), n))


class DateSchedule(Schedule):
    """
    Schedule for running on a manually created list of dates.

    Args:
        - dates ([datetime]): a list of datetimes to run on
    """

    def __init__(self, dates: Iterable[datetime]) -> None:
        self.dates = dates

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
            on_or_after = datetime.utcnow()
        dates = sorted([d for d in self.dates if d >= on_or_after])
        return dates[:n]
