import croniter
import datetime
import itertools
from mongoengine import Document, EmbeddedDocument
from mongoengine.fields import (
    DateTimeField,
    EmbeddedDocumentField,
    IntField,
    ListField,
    StringField,)
from prefect.state import State


class Schedule(EmbeddedDocument):
    meta = {'allow_inheritance': True, 'collection': 'schedules'}

    def next_n(self, n=1, on_or_after=None):
        raise NotImplemented('Must be implemented on Schedule subclasses')


class NoSchedule(Schedule):

    def next_n(self, n=1, on_or_after=None):
        return []


class DateSchedule(Schedule):
    dates = ListField(DateTimeField(), required=True)

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.now()
        on_or_after = DateTimeField().to_mongo(on_or_after)
        dates = sorted([d for d in self.dates if d >= on_or_after])
        return dates[:n]


class CronSchedule(Schedule):
    cron = StringField(required=True)

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.now()
        on_or_after = DateTimeField().to_mongo(on_or_after)
        cron = croniter.croniter(self.cron, on_or_after)
        return list(itertools.islice(cron.all_next(datetime.datetime), n))


class IntervalSchedule(Schedule):
    first_date = DateTimeField(required=True)
    weeks = IntField(default=0)
    days = IntField(default=0)
    hours = IntField(default=0)
    minutes = IntField(default=0)
    seconds = IntField(default=0)
    milliseconds = IntField(default=0)
    microseconds = IntField(default=0)

    def __init__(self, first_date, timedelta=None, **kwargs):
        self._timedelta_fields = (
            'weeks', 'days', 'hours', 'minutes', 'seconds', 'milliseconds',
            'microseconds',)
        if timedelta is not None:
            kwargs.update(
                {f: getattr(timedelta, f, 0)
                 for f in self._timedelta_fields})
        super().__init__(first_date=first_date, **kwargs)
        if self.get_timedelta().total_seconds() <= 0:
            raise ValueError('Interval must be provided and greater than 0')

    def get_timedelta(self):
        return datetime.timedelta(
            **{f: getattr(self, f)
               for f in self._timedelta_fields})

    def _generator(self, start):
        dt = self.first_date
        timedelta = self.get_timedelta()
        if dt >= start:
            yield dt

        while True:
            dt = dt + timedelta
            if dt < start:
                continue
            yield dt

    def next_n(self, n=1, on_or_after=None):
        if on_or_after is None:
            on_or_after = datetime.datetime.now()
        on_or_after = DateTimeField().to_mongo(on_or_after)
        return list(itertools.islice(self._generator(start=on_or_after), n))
