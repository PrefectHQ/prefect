import croniter
import datetime
import itertools
import prefect.utilities.dates


class Schedule:

    def next_n(self, n=1, on_or_after=None):
        raise NotImplemented('Must be implemented on Schedule subclasses')


class NoSchedule(Schedule):
    """
    No schedule; this Flow will only run on demand.
    """

    def next_n(self, n=1, on_or_after=None):
        return []


class IntervalSchedule(Schedule):
    """
    A schedule formed by adding `timedelta` increments to a start_date.
    """

    def __init__(self, start_date, interval):
        if interval.total_seconds() <= 0:
            raise ValueError('Interval must be provided and greater than 0')
        self.start_date = prefect.utilities.dates.parse_datetime(start_date)
        self.interval = interval

    def _generator(self, start):
        dt = self.start_date
        if dt >= start:
            yield dt

        while True:
            dt = dt + self.interval
            if dt < start:
                continue
            yield dt

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        elif isinstance(on_or_after, (str, bytes)):
            on_or_after = prefect.utilities.dates.parse_datetime(on_or_after)
        return list(itertools.islice(self._generator(start=on_or_after), n))


class CronSchedule(Schedule):

    def __init__(self, cron):
        self.cron = cron

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        elif isinstance(on_or_after, (str, bytes)):
            on_or_after = prefect.utilities.dates.parse_datetime(on_or_after)
        cron = croniter.croniter(self.cron, on_or_after)
        return list(itertools.islice(cron.all_next(datetime.datetime), n))


class DateSchedule(Schedule):

    def __init__(self, dates):
        self.dates = [prefect.utilities.dates.parse_datetime(d) for d in dates]

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.utcnow()
        elif isinstance(on_or_after, (str, bytes)):
            on_or_after = prefect.utilities.dates.parse_datetime(on_or_after)
        dates = sorted([d for d in self.dates if d >= on_or_after])
        return dates[:n]
