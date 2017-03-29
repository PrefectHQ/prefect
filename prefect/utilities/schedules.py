import croniter
import datetime
import dateutil
import itertools
from prefect.state import State


class Schedule:

    def next_n(self, n=1, on_or_after=None):
        raise NotImplemented('Must be implemented on Schedule subclasses')


class NoSchedule(Schedule):

    def next_n(self, n=1, on_or_after=None):
        return []


class DateSchedule(Schedule):

    def __init__(self, dates):
        self.dates = [dateutil.parser.parse(d) for d in dates]

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        on_or_after = dateutil.parser.parse(on_or_after)
        dates = sorted([d for d in self.dates if d >= on_or_after])
        return dates[:n]


class CronSchedule(Schedule):

    def __init__(self, cron):
        self.cron = cron

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        on_or_after = dateutil
        cron = croniter.croniter(self.cron, on_or_after)
        return list(itertools.islice(cron.all_next(datetime.datetime), n))


class IntervalSchedule(Schedule):

    def __init__(self, first_date, timedelta):
        if timedelta.total_seconds() <= 0:
            raise ValueError('Interval must be provided and greater than 0')
        self.first_date = first_date
        self.timedelta = timedelta

    def _generator(self, start):
        dt = self.first_date
        if dt >= start:
            yield dt

        while True:
            dt = dt + self.timedelta
            if dt < start:
                continue
            yield dt

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        on_or_after = dateutil.parser.parse(on_or_after)
        return list(itertools.islice(self._generator(start=on_or_after), n))
