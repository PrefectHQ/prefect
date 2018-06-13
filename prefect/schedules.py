from typing import List, Iterable
import datetime
import itertools
import json

import croniter

import prefect.utilities.datetimes
from prefect.utilities.json import Serializable


class Schedule(Serializable):
    """
    Base class for Schedules
    """

    def next_n(
        self, n: int = 1, on_or_after: datetime.datetime = None
    ) -> List[datetime.datetime]:
        raise NotImplementedError("Must be implemented on Schedule subclasses")

    def __eq__(self, other: object) -> bool:
        if type(self) == type(other) and json.dumps(self) == json.dumps(other):
            return True
        return False


class NoSchedule(Schedule):
    """
    No schedule; this Flow will only run on demand.
    """

    def next_n(
        self, n: int = 1, on_or_after: datetime.datetime = None
    ) -> List[datetime.datetime]:
        return []


class IntervalSchedule(Schedule):
    """
    A schedule formed by adding `timedelta` increments to a start_date.
    """

    def __init__(
        self, start_date: datetime.datetime, interval: datetime.timedelta
    ) -> None:
        if interval.total_seconds() <= 0:
            raise ValueError("Interval must be provided and greater than 0")
        self.start_date = prefect.utilities.datetimes.parse_datetime(
            start_date
        )  # type: datetime.datetime
        self.interval = interval

    def _generator(self, start: datetime.datetime) -> Iterable[datetime.datetime]:
        dt = self.start_date
        if dt >= start:
            yield dt

        while True:
            dt = dt + self.interval
            if dt < start:
                continue
            yield dt

    def next_n(
        self, n: int = 1, on_or_after: datetime.datetime = None
    ) -> List[datetime.datetime]:
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        elif isinstance(on_or_after, (str, bytes)):
            on_or_after = prefect.utilities.datetimes.parse_datetime(on_or_after)
        return list(itertools.islice(self._generator(start=on_or_after), n))


class CronSchedule(Schedule):
    def __init__(self, cron: str) -> None:
        self.cron = cron

    def next_n(
        self, n: int = 1, on_or_after: datetime.datetime = None
    ) -> List[datetime.datetime]:
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        elif isinstance(on_or_after, (str, bytes)):
            on_or_after = prefect.utilities.datetimes.parse_datetime(on_or_after)
        cron = croniter.croniter(self.cron, on_or_after)
        return list(itertools.islice(cron.all_next(datetime.datetime), n))


class DateSchedule(Schedule):
    def __init__(self, dates: Iterable[datetime.datetime]) -> None:
        self.dates = [prefect.utilities.datetimes.parse_datetime(d) for d in dates]

    def next_n(
        self, n: int = 1, on_or_after: datetime.datetime = None
    ) -> List[datetime.datetime]:
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        elif isinstance(on_or_after, (str, bytes)):
            on_or_after = prefect.utilities.datetimes.parse_datetime(on_or_after)
        dates = sorted([d for d in self.dates if d >= on_or_after])
        return dates[:n]
