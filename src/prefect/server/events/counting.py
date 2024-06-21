import math
from datetime import timedelta
from typing import TYPE_CHECKING

import pendulum
import sqlalchemy as sa
from pendulum.datetime import DateTime
from sqlalchemy.sql.selectable import Select

from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.utilities.database import json_extract
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    from prefect.server.events.filters import EventFilter


# The earliest possible event.occurred date in any Prefect environment is
# 2024-04-04, so we use the Monday before that as our pivot date.
PIVOT_DATETIME = pendulum.DateTime(2024, 4, 1, tzinfo=pendulum.timezone("UTC"))


class InvalidEventCountParameters(ValueError):
    """Raised when the given parameters are invalid for counting events."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TimeUnit(AutoEnum):
    week = AutoEnum.auto()
    day = AutoEnum.auto()
    hour = AutoEnum.auto()
    minute = AutoEnum.auto()
    second = AutoEnum.auto()

    def as_timedelta(self, interval) -> pendulum.Duration:
        if self == self.week:
            return pendulum.Duration(days=7 * interval)
        elif self == self.day:
            return pendulum.Duration(days=1 * interval)
        elif self == self.hour:
            return pendulum.Duration(hours=1 * interval)
        elif self == self.minute:
            return pendulum.Duration(minutes=1 * interval)
        elif self == self.second:
            return pendulum.Duration(seconds=1 * interval)
        else:
            raise NotImplementedError()

    def validate_buckets(
        self, start_datetime: DateTime, end_datetime: DateTime, interval: float
    ):
        MAX_ALLOWED_BUCKETS = 1000

        delta = self.as_timedelta(interval)
        start_in_utc = start_datetime.in_timezone("UTC")
        end_in_utc = end_datetime.in_timezone("UTC")

        if interval < 0.01:
            raise InvalidEventCountParameters("The minimum interval is 0.01")

        number_of_buckets = math.ceil((end_in_utc - start_in_utc) / delta)
        if number_of_buckets > MAX_ALLOWED_BUCKETS:
            raise InvalidEventCountParameters(
                f"The given interval would create {number_of_buckets} buckets, "
                "which is too many. Please increase the interval or reduce the "
                f"time range to produce {MAX_ALLOWED_BUCKETS} buckets or fewer."
            )

    def get_interval_spans(
        self,
        start_datetime: DateTime,
        end_datetime: DateTime,
        interval: float,
    ):
        """Divide the given range of dates into evenly-sized spans of interval units"""
        self.validate_buckets(start_datetime, end_datetime, interval)

        # Our universe began on PIVOT_DATETIME and all time after that is
        # divided into `delta`-sized buckets. We want to find the bucket that
        # contains `start_datetime` and then find the all of the buckets
        # that come after it until the bucket that contains `end_datetime`.

        delta = self.as_timedelta(interval)
        start_in_utc = start_datetime.in_timezone("UTC")
        end_in_utc = end_datetime.in_timezone("UTC")

        if end_in_utc > pendulum.now("UTC"):
            end_in_utc = pendulum.now("UTC").end_of(self.value)

        first_span_index = math.floor((start_in_utc - PIVOT_DATETIME) / delta)

        yield first_span_index

        span_start = PIVOT_DATETIME + delta * first_span_index

        while span_start < end_in_utc:
            next_span_start = span_start + delta
            yield (span_start, next_span_start - timedelta(microseconds=1))
            span_start = next_span_start

    def database_value_expression(self, time_interval: float):
        """Returns the SQL expression to place an event in a time bucket"""
        # The date_bin function can do the bucketing for us:
        # https://www.postgresql.org/docs/14/functions-datetime.html#FUNCTIONS-DATETIME-BIN
        db = provide_database_interface()
        delta = self.as_timedelta(time_interval)
        if db.dialect.name == "postgresql":
            return sa.cast(
                sa.func.floor(
                    sa.extract(
                        "epoch",
                        (
                            sa.func.date_bin(delta, db.Event.occurred, PIVOT_DATETIME)
                            - PIVOT_DATETIME
                        ),
                    )
                    / delta.total_seconds(),
                ),
                sa.Text,
            )
        elif db.dialect.name == "sqlite":
            # Convert pivot date and event date to strings formatted as seconds since the epoch
            pivot_timestamp = sa.func.strftime(
                "%s", PIVOT_DATETIME.strftime("%Y-%m-%d %H:%M:%S")
            )
            event_timestamp = sa.func.strftime("%s", db.Event.occurred)
            seconds_since_pivot = event_timestamp - pivot_timestamp
            # Calculate the bucket index by dividing by the interval in seconds and flooring the result
            bucket_index = sa.func.floor(
                sa.cast(seconds_since_pivot, sa.Integer) / delta.total_seconds()
            )
            return sa.cast(bucket_index, sa.Text)
        else:
            raise NotImplementedError(f"Dialect {db.dialect.name} is not supported.")

    def database_label_expression(self, db: PrefectDBInterface, time_interval: float):
        """Returns the SQL expression to label a time bucket"""
        time_delta = self.as_timedelta(time_interval)
        if db.dialect.name == "postgresql":
            # The date_bin function can do the bucketing for us:
            # https://www.postgresql.org/docs/14/functions-datetime.html#FUNCTIONS-DATETIME-BIN
            return sa.func.to_char(
                sa.func.date_bin(time_delta, db.Event.occurred, PIVOT_DATETIME),
                'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM',
            )
        elif db.dialect.name == "sqlite":
            # We can't use date_bin in SQLite, so we have to do the bucketing manually
            seconds_since_epoch = sa.func.strftime("%s", db.Event.occurred)
            # Convert the total seconds of the timedelta to a constant in SQL
            bucket_size = time_delta.total_seconds()
            # Perform integer division and multiplication to find the bucket start epoch using SQL functions
            bucket_start_epoch = sa.func.cast(
                (sa.cast(seconds_since_epoch, sa.Integer) / bucket_size) * bucket_size,
                sa.Integer,
            )
            bucket_datetime = sa.func.strftime(
                "%Y-%m-%dT%H:%M:%SZ", sa.func.datetime(bucket_start_epoch, "unixepoch")
            )
            return bucket_datetime
        else:
            raise NotImplementedError(f"Dialect {db.dialect.name} is not supported.")


class Countable(AutoEnum):
    day = AutoEnum.auto()  # `day` will be translated into an equivalent `time`
    time = AutoEnum.auto()
    event = AutoEnum.auto()
    resource = AutoEnum.auto()

    # Implementations for storage backend

    def get_database_query(
        self,
        filter: "EventFilter",
        time_unit: TimeUnit,
        time_interval: float,
    ) -> Select:
        db = provide_database_interface()
        # The innermost SELECT pulls the matching events and groups them up by their
        # buckets.  At this point, there may be duplicate buckets for each value, since
        # the label of the thing referred to might have changed
        fundamental_counts = (
            sa.select(
                (
                    self._database_value_expression(
                        db,
                        time_unit=time_unit,
                        time_interval=time_interval,
                    ).label("value")
                ),
                (
                    self._database_label_expression(
                        db,
                        time_unit=time_unit,
                        time_interval=time_interval,
                    ).label("label")
                ),
                sa.func.max(db.Event.occurred).label("latest"),
                sa.func.min(db.Event.occurred).label("oldest"),
                sa.func.count().label("count"),
            )
            .where(sa.and_(*filter.build_where_clauses()))
            .group_by("value", "label")
        )

        fundamental_counts = fundamental_counts.select_from(db.Event)

        # An intermediate SELECT takes the fundamental counts and reprojects it with the
        # most recent value for the labels of that bucket.
        fundamental = fundamental_counts.subquery("fundamental_counts")
        with_latest_labels = (
            sa.select(
                fundamental.c.value,
                (
                    sa.func.first_value(fundamental.c.label).over(
                        partition_by=fundamental.c.value,
                        order_by=sa.desc(fundamental.c.latest),
                    )
                ).label("label"),
                fundamental.c.latest,
                fundamental.c.oldest,
                fundamental.c.count,
            )
            .select_from(fundamental)
            .subquery("with_latest_labels")
        )

        # The final SELECT re-sums with the latest labels, ensuring that we get one
        # row back for each value.  This handles the final ordering as well.
        count = sa.func.sum(with_latest_labels.c.count).label("count")

        reaggregated = (
            sa.select(
                with_latest_labels.c.value.label("value"),
                with_latest_labels.c.label.label("label"),
                count,
                sa.func.min(with_latest_labels.c.oldest).label("start_time"),
                sa.func.max(with_latest_labels.c.latest).label("end_time"),
            )
            .select_from(with_latest_labels)
            .group_by(with_latest_labels.c.value, with_latest_labels.c.label)
        )

        if self in (self.day, self.time):
            reaggregated = reaggregated.order_by(
                sa.asc("start_time"),
            )
        else:
            reaggregated = reaggregated.order_by(
                sa.desc(count),
                sa.asc(with_latest_labels.c.label),
            )

        return reaggregated

    def _database_value_expression(
        self,
        db: PrefectDBInterface,
        time_unit: TimeUnit,
        time_interval: float,
    ):
        if self == self.day:
            # The legacy `day` Countable is just a special case of the `time` one
            return TimeUnit.day.database_value_expression(1)
        elif self == self.time:
            return time_unit.database_value_expression(time_interval)
        elif self == self.event:
            return db.Event.event
        elif self == self.resource:
            return db.Event.resource_id
        else:
            raise NotImplementedError()

    def _database_label_expression(
        self,
        db: PrefectDBInterface,
        time_unit: TimeUnit,
        time_interval: float,
    ):
        if self == self.day:
            # The legacy `day` Countable is just a special case of the `time` one
            return TimeUnit.day.database_label_expression(db, 1)
        elif self == self.time:
            return time_unit.database_label_expression(db, time_interval)
        elif self == self.event:
            return db.Event.event
        elif self == self.resource:
            return sa.func.coalesce(
                json_extract(
                    db.Event.resource,
                    "prefect.resource.name",
                    wrap_quotes=db.dialect.name == "sqlite",
                ),
                json_extract(
                    db.Event.resource,
                    "prefect.name",
                    wrap_quotes=db.dialect.name == "sqlite",
                ),
                db.Event.resource_id,
            )
        else:
            raise NotImplementedError()
