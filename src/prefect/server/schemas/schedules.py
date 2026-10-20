"""
Schedule schemas
"""

from __future__ import annotations

import datetime
import sys
from collections.abc import Generator, Iterator
from heapq import merge
from itertools import takewhile
from typing import (
    Annotated,
    Any,
    ClassVar,
    TypeAlias,
    Union,
)
from zoneinfo import ZoneInfo

import dateutil
import dateutil.rrule
import pytz
from pydantic import AfterValidator, ConfigDict, Field, field_validator, model_validator
from whenever import DateTimeDelta, ZonedDateTime

from prefect._internal.schemas.validators import (
    default_anchor_date,
    default_timezone,
    validate_cron_string,
    validate_rrule_string,
)
from prefect._vendor.croniter import croniter
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.types import DateTime, TimeZone
from prefect.types._datetime import (
    PositiveInterval,
    _pendulum_call,
    _whenever_pdt_from_py,
    _whenever_to_stdlib,
    _whenever_zdt_from_py,
    create_datetime_instance,
    now,
)

MAX_ITERATIONS = 1000

try:
    from whenever import ItemizedDelta as _ItemizedDelta

    _WHENEVER_DELTA_TYPES: tuple[type, ...] = (_ItemizedDelta,)
except ImportError:
    _ItemizedDelta = None  # type: ignore[assignment]
    _WHENEVER_DELTA_TYPES = (DateTimeDelta,)


def _whenever_delta_seconds(delta: Any) -> float:
    # whenever >= 0.10.0 exposes `total("seconds")`; older versions
    # expose `in_seconds()`
    return delta.total("seconds") if hasattr(delta, "total") else delta.in_seconds()


if sys.version_info >= (3, 13):
    AnchorDate: TypeAlias = datetime.datetime
    _ScheduleInterval: TypeAlias = PositiveInterval
else:
    AnchorDate: TypeAlias = Annotated[DateTime, AfterValidator(default_anchor_date)]
    _ScheduleInterval: TypeAlias = Annotated[
        datetime.timedelta, Field(gt=datetime.timedelta(0))
    ]


def _prepare_scheduling_start_and_end(
    start: Any, end: Any, timezone: str
) -> tuple[DateTime, DateTime | None]:
    """Uniformly prepares the start and end dates for any Schedule's get_dates call,
    coercing the arguments into timezone-aware datetimes."""
    timezone = timezone or "UTC"

    if start is not None:
        if sys.version_info >= (3, 13):
            start = create_datetime_instance(start).astimezone(ZoneInfo(timezone))
        else:
            start = _pendulum_call(create_datetime_instance(start), "in_tz", timezone)

    if end is not None:
        if sys.version_info >= (3, 13):
            end = create_datetime_instance(end).astimezone(ZoneInfo(timezone))
        else:
            end = _pendulum_call(create_datetime_instance(end), "in_tz", timezone)

    return start, end


class IntervalSchedule(PrefectBaseModel):
    """
    A schedule formed by adding `interval` increments to an `anchor_date`. If no
    `anchor_date` is supplied, the current UTC time is used.  If a
    timezone-naive datetime is provided for `anchor_date`, it is assumed to be
    in the schedule's timezone (or UTC). Even if supplied with an IANA timezone,
    anchor dates are always stored as UTC offsets, so a `timezone` can be
    provided to determine localization behaviors like DST boundary handling. If
    none is provided it will be inferred from the anchor date.

    NOTE: If the `IntervalSchedule` `anchor_date` or `timezone` is provided in a
    DST-observing timezone, then the schedule will adjust itself appropriately.
    Intervals greater than 24 hours will follow DST conventions, while intervals
    of less than 24 hours will follow UTC intervals. For example, an hourly
    schedule will fire every UTC hour, even across DST boundaries. When clocks
    are set back, this will result in two runs that *appear* to both be
    scheduled for 1am local time, even though they are an hour apart in UTC
    time. For longer intervals, like a daily schedule, the interval schedule
    will adjust for DST boundaries so that the clock-hour remains constant. This
    means that a daily schedule that always fires at 9am will observe DST and
    continue to fire at 9am in the local time zone.

    Args:
        interval (datetime.timedelta): an interval to schedule on.
        anchor_date (DateTime, optional): an anchor date to schedule increments against;
            if not provided, the current timestamp will be used.
        timezone (str, optional): a valid timezone string.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    interval: _ScheduleInterval = Field()
    anchor_date: AnchorDate = Field(
        default_factory=lambda: now("UTC"),
        examples=["2020-01-01T00:00:00Z"],
    )
    timezone: str | None = Field(default=None, examples=["America/New_York"])

    @model_validator(mode="after")
    def validate_timezone(self):
        self.timezone = default_timezone(self.timezone, self.model_dump())
        return self

    async def get_dates(
        self,
        n: int | None = None,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ) -> list[DateTime]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to None.  If a timezone-naive datetime is
                provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): The maximum scheduled date to return. If
                a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: A list of dates
        """
        return sorted(self._get_dates_generator(n=n, start=start, end=end))

    def _get_dates_generator(
        self,
        n: int | None = None,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ) -> Generator[DateTime, None, None]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (Optional[int]): The number of dates to generate
            start (Optional[datetime.datetime]): The first returned date will be on or
                after this date. Defaults to None.  If a timezone-naive datetime is
                provided, it is assumed to be in the schedule's timezone.
            end (Optional[datetime.datetime]): The maximum scheduled date to return. If
                a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: a list of dates
        """
        if sys.version_info < (3, 13):
            # Pendulum arithmetic and resolution stay authoritative on
            # 3.11-3.12 throughout the deprecation window.
            yield from self._pendulum_dates_generator(n=n, start=start, end=end)
            return

        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up to
            # MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        if start is None:
            start = now("UTC")

        target_timezone = self.timezone or "UTC"

        def to_local_zdt(dt: datetime.datetime | None) -> ZonedDateTime | None:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return _whenever_pdt_from_py(dt).assume_tz(target_timezone)
            if isinstance(dt.tzinfo, ZoneInfo):
                return _whenever_zdt_from_py(dt).to_tz(target_timezone)
            # For offset-based tzinfo instances (e.g. datetime.timezone(+09:00)),
            # use astimezone to preserve the instant, then convert to ZonedDateTime.
            return _whenever_zdt_from_py(dt.astimezone(ZoneInfo(target_timezone)))

        anchor_zdt = to_local_zdt(self.anchor_date)
        assert anchor_zdt is not None

        local_start = to_local_zdt(start)
        assert local_start is not None

        local_end = to_local_zdt(end)

        interval = self.interval
        # Keep the public timedelta contract while seeking in calendar days across DST.
        if isinstance(interval, datetime.timedelta) and _ItemizedDelta is not None:
            interval = _ItemizedDelta(
                days=interval.days,
                seconds=interval.seconds,
                nanoseconds=interval.microseconds * 1000,
            )
        has_calendar_parts = False
        _years = _weeks = 0
        if isinstance(interval, _WHENEVER_DELTA_TYPES):
            # whenever delta types distinguish calendar days from exact hours,
            # so we can use them directly. We still need an approximate
            # total-seconds value for the initial offset jump.
            if isinstance(interval, DateTimeDelta):
                _months, _days, _secs, _nanos = interval.in_months_days_secs_nanos()
                has_day_or_time_parts = bool(_days or _secs or _nanos)
                approx_total_seconds = (
                    _months * 30 * 86400 + _days * 86400 + _secs + _nanos / 1e9
                )
            else:  # ItemizedDelta (whenever >= 0.10.0)
                _date, _time = interval.date_and_time_parts()
                _years = _date.get("years") or 0 if _date else 0
                _months = _date.get("months") or 0 if _date else 0
                _weeks = _date.get("weeks") or 0 if _date else 0
                _days = _date.get("days") or 0 if _date else 0
                has_day_or_time_parts = bool(_weeks or _days or _time)
                approx_total_seconds = (
                    _years * 365 * 86400
                    + _months * 30 * 86400
                    + _weeks * 7 * 86400
                    + _days * 86400
                    + (_time.total("seconds") if _time else 0)
                )
            has_calendar_parts = bool(_years or _months or _weeks or _days)

            def _advance(zdt: ZonedDateTime) -> ZonedDateTime:
                return zdt + interval

            def _scaled_date_delta(k: int) -> _ItemizedDelta | None:
                if _date is None:
                    return None
                _kw = {
                    unit: value * k
                    for unit in ("years", "months", "weeks", "days")
                    if (value := _date.get(unit))
                }
                return _ItemizedDelta(**_kw) if _kw else None

            def _subtract_scaled(zdt: ZonedDateTime, k: int) -> ZonedDateTime:
                # `zdt - k * interval` as a single calendar step so the
                # result keeps the anchor's phase — repeated subtraction
                # compounds clamping (Mar 31 -> Feb 28 -> Jan 28).
                if isinstance(interval, DateTimeDelta):
                    return zdt - interval * k
                result = zdt
                if (_dd := _scaled_date_delta(k)) is not None:
                    result = result - _dd
                if _time is not None:
                    result = result - _time * k
                return result

            def _add_scaled(zdt: ZonedDateTime, k: int) -> ZonedDateTime:
                # `zdt + k * interval` as a single calendar step. This equals
                # advancing `interval` k times only when no month-end clamping
                # can occur along the way (iterating Jan 31 + 1 month drifts
                # to Feb 28/29 -> Mar 28/29, while one step stays at day 31).
                if isinstance(interval, DateTimeDelta):
                    return zdt + interval * k
                result = zdt
                if (_dd := _scaled_date_delta(k)) is not None:
                    result = result + _dd
                if _time is not None:
                    result = result + _time * k
                return result

            def _first_offset_change_after(
                a: ZonedDateTime, b: ZonedDateTime
            ) -> ZonedDateTime | None:
                # Consult the zone's transitions instead of scanning its history.
                transition = a.next_transition()
                while transition is not None and transition <= b:
                    if transition.offset != a.offset:
                        return transition
                    transition = transition.next_transition()
                return None

            def _seek_within(frm: ZonedDateTime, upto: ZonedDateTime) -> ZonedDateTime:
                # The last occurrence on or before `upto`, computed with a
                # scaled step. Valid only where the UTC offset is constant
                # and no month-end clamping occurs over (frm, upto].
                _span_secs = _whenever_delta_seconds(upto - frm)
                k = max(0, int(_span_secs / approx_total_seconds))
                while k > 0 and _add_scaled(frm, k) > upto:
                    k -= 1
                while _add_scaled(frm, k + 1) <= upto:
                    k += 1
                return _add_scaled(frm, k)

        else:
            approx_total_seconds = interval.total_seconds()
            # break the interval into `days` and `seconds` because
            # ZonedDateTime.add will handle DST boundaries properly if
            # days are provided, but not if we add `total seconds`.
            _interval_days = interval.days
            _interval_seconds = interval.total_seconds() - (
                _interval_days * 24 * 60 * 60
            )

            def _advance(zdt: ZonedDateTime) -> ZonedDateTime:
                return zdt.add(days=_interval_days, seconds=_interval_seconds)

        _diff_secs = _whenever_delta_seconds(local_start - anchor_zdt)
        if has_calendar_parts:
            # Calendar additions are not uniform (months clamp to the end of
            # the month and days shift across DST), so an exact-seconds jump
            # would leave the recurrence phase. Advance from the anchor
            # instead; the yield loop below bounds any leftover distance.
            next_date = anchor_zdt
            if local_start < anchor_zdt:
                # `start` precedes the anchor: occurrences between `start`
                # and the anchor must not be skipped, and they must keep the
                # anchor's phase, so each is computed as
                # `anchor - i * interval` in one calendar step. `pre_i`
                # counts the steps back for the earliest such occurrence and
                # the yield loop drains i = pre_i..0 lazily, so only the
                # occurrences actually yielded are computed.
                def _occurrence(i: int) -> ZonedDateTime | None:
                    try:
                        return _subtract_scaled(anchor_zdt, i)
                    except (ValueError, OverflowError):
                        # out of the representable range — earlier than any
                        # valid occurrence
                        return None

                pre_i = max(1, int(-_diff_secs / approx_total_seconds))
                while (
                    _occurrence(pre_i) is not None and _occurrence(pre_i) > local_start
                ):
                    pre_i += 1
                while pre_i > 1 and (
                    (o := _occurrence(pre_i - 1)) is None or o <= local_start
                ):
                    pre_i -= 1
            else:
                pre_i = -1
                # When no month-end clamping can occur, `anchor + k * interval`
                # in one step equals advancing k times within a constant-offset
                # segment, so seek near `start` instead of replaying every
                # occurrence — a daily schedule anchored years back would
                # otherwise walk the whole range on each query. Across a DST
                # transition a calendar add can drift the phase, so hop
                # transition to transition: seek within each constant-offset
                # segment, then `_advance` once across the change.
                if not (_years or _months) or (
                    anchor_zdt.date().day <= 28 and not has_day_or_time_parts
                ):
                    for _ in range(MAX_ITERATIONS):
                        if next_date >= local_start:
                            break
                        _trans = _first_offset_change_after(next_date, local_start)
                        if _trans is None:
                            break
                        next_date = _seek_within(next_date, _trans)
                        if next_date < local_start:
                            next_date = _advance(next_date)
                    if _first_offset_change_after(next_date, local_start) is None:
                        next_date = _seek_within(next_date, local_start)
        else:
            offset = _diff_secs / approx_total_seconds
            next_date = anchor_zdt.add(seconds=approx_total_seconds * int(offset))
            pre_i = -1

        while next_date < local_start:
            next_date = _advance(next_date)

        counter = 0
        dates: set[ZonedDateTime] = set()

        while True:
            if pre_i >= 0:
                # i == 0 is the anchor itself; resume forward advancement
                # after it is emitted.
                next_date = anchor_zdt if pre_i == 0 else _occurrence(pre_i)
                pre_i -= 1
                if next_date is None or next_date < local_start:
                    if pre_i < 0:
                        next_date = anchor_zdt
                    continue

            # if the end date was exceeded, exit
            if local_end and next_date > local_end:
                break

            # ensure no duplicates; weird things can happen with DST
            if next_date not in dates:
                dates.add(next_date)
                yield create_datetime_instance(_whenever_to_stdlib(next_date))

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

            if pre_i < 0:
                next_date = _advance(next_date)

    def _pendulum_dates_generator(
        self,
        n: int | None = None,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ) -> Generator[DateTime, None, None]:
        """Legacy Pendulum engine, preserved verbatim for the deprecation
        window. Only reached on Python < 3.13."""
        if start is None:
            start = now("UTC")
        if n is None:
            # if an end was supplied, we do our best to supply all matching
            # dates (up to MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1
        anchor_tz = _pendulum_call(self.anchor_date, "in_tz", self.timezone)
        start, end = _prepare_scheduling_start_and_end(start, end, self.timezone)

        # compute the offset between the anchor date and the start date to jump to the
        # next date
        offset = (start - anchor_tz).total_seconds() / self.interval.total_seconds()
        next_date = _pendulum_call(
            anchor_tz, "add", seconds=self.interval.total_seconds() * int(offset)
        )

        # break the interval into `days` and `seconds` because the datetime
        # library will handle DST boundaries properly if days are provided, but not
        # if we add `total seconds`. Therefore, `next_date + self.interval`
        # fails while `next_date.add(days=days, seconds=seconds)` works.
        interval_days = self.interval.days
        interval_seconds = self.interval.total_seconds() - (
            interval_days * 24 * 60 * 60
        )

        # daylight saving time boundaries can create a situation where the next date is
        # before the start date, so we advance it if necessary
        while next_date < start:
            next_date = _pendulum_call(
                next_date, "add", days=interval_days, seconds=interval_seconds
            )

        counter = 0
        dates = set()

        while True:
            # if the end date was exceeded, exit
            if end and next_date > end:
                break

            # ensure no duplicates; weird things can happen with DST
            if next_date not in dates:
                dates.add(next_date)
                yield next_date

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

            next_date = _pendulum_call(
                next_date, "add", days=interval_days, seconds=interval_seconds
            )


class CronSchedule(PrefectBaseModel):
    """
    Cron schedule

    NOTE: If the timezone is a DST-observing one, then the schedule will adjust
    itself appropriately. Cron's rules for DST are based on schedule times, not
    intervals. This means that an hourly cron schedule will fire on every new
    schedule hour, not every elapsed hour; for example, when clocks are set back
    this will result in a two-hour pause as the schedule will fire *the first
    time* 1am is reached and *the first time* 2am is reached, 120 minutes later.
    Longer schedules, such as one that fires at 9am every morning, will
    automatically adjust for DST.

    Args:
        cron (str): a valid cron string
        timezone (str): a valid timezone string in IANA tzdata format (for example,
            America/New_York).
        day_or (bool, optional): Control how croniter handles `day` and `day_of_week`
            entries. Defaults to True, matching cron which connects those values using
            OR. If the switch is set to False, the values are connected using AND. This
            behaves like fcron and enables you to e.g. define a job that executes each
            2nd friday of a month by setting the days of month and the weekday.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    cron: str = Field(default=..., examples=["0 0 * * *"])
    timezone: str | None = Field(default=None, examples=["America/New_York"])
    day_or: bool = Field(
        default=True,
        description=(
            "Control croniter behavior for handling day and day_of_week entries."
        ),
    )

    @model_validator(mode="after")
    def validate_timezone(self):
        self.timezone = default_timezone(self.timezone, self.model_dump())
        return self

    @field_validator("cron")
    @classmethod
    def valid_cron_string(cls, v: str) -> str:
        return validate_cron_string(v)

    async def get_dates(
        self,
        n: int | None = None,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ) -> list[DateTime]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to None.  If a timezone-naive datetime is
                provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): The maximum scheduled date to return. If
                a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: A list of dates
        """
        return sorted(self._get_dates_generator(n=n, start=start, end=end))

    def _get_dates_generator(
        self,
        n: int | None = None,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ) -> Generator[DateTime, None, None]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to the current date. If a timezone-naive
                datetime is provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): No returned date will exceed this date.
                If a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: a list of dates
        """
        if sys.version_info < (3, 13):
            # Pendulum arithmetic and resolution stay authoritative on
            # 3.11-3.12 throughout the deprecation window.
            yield from self._pendulum_dates_generator(n=n, start=start, end=end)
            return

        if start is None:
            start = now("UTC")

        start, end = _prepare_scheduling_start_and_end(start, end, self.timezone)

        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up to
            # MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        # Keep wall-clock arithmetic in stdlib datetime even when the public
        # input is a Pendulum datetime during the deprecation window.
        start = datetime.datetime.combine(start, start.timetz())
        if self.timezone:
            start = start.astimezone(ZoneInfo(self.timezone or "UTC"))

        # subtract one second from the start date, so that croniter returns it
        # as an event (if it meets the cron criteria). The croniter anchor is
        # wall-clock time: subtracting on the instant timeline would cross a
        # DST fold and skip a matching occurrence in the second fold.
        start_naive_tz = start.replace(tzinfo=None) - datetime.timedelta(seconds=1)
        # The instant anchor is used to disambiguate candidates inside a fold
        # and stays on the instant timeline.
        start_localized = (
            start.astimezone(datetime.UTC) - datetime.timedelta(seconds=1)
        ).astimezone(start.tzinfo)

        # Respect microseconds by rounding up
        if start.microsecond > 0:
            start_naive_tz += datetime.timedelta(seconds=1)
            # The +1s undoes the -1s on the instant anchor; rebuilding it
            # from `start` keeps its fold — adding a timedelta to an aware
            # datetime resets `fold` to 0.
            start_localized = start

        start_instant = _whenever_zdt_from_py(start_localized)

        def localize(next_wall: datetime.datetime) -> datetime.datetime:
            # Pick the earliest fold still on/after the start instant.
            first = _whenever_zdt_from_py(
                next_wall.replace(tzinfo=start_localized.tzinfo, fold=0)
            )
            candidates = {first}
            # A nonexistent wall time is shifted forward, matching the
            # existing Whenever behavior. Only consider the second fold
            # when the first interpretation preserves the wall time.
            if _whenever_to_stdlib(first).replace(tzinfo=None) == next_wall:
                candidates.add(
                    _whenever_zdt_from_py(
                        next_wall.replace(tzinfo=start_localized.tzinfo, fold=1)
                    )
                )
            viable = [c for c in candidates if c >= start_instant]
            _zdt = (min(viable) if viable else min(candidates)).to_tz(
                self.timezone or "UTC"
            )
            return _whenever_to_stdlib(_zdt)

        cron = croniter(self.cron, start_naive_tz, day_or=self.day_or)  # type: ignore
        wall_times = iter(lambda: cron.get_next(datetime.datetime), None)
        candidate_dates: Iterator[datetime.datetime] = map(localize, wall_times)

        start_zdt = _whenever_zdt_from_py(start)
        # Transition lookup excludes the current second, including its fractions.
        transition = start_zdt.add(seconds=1).prev_transition()
        if transition is not None:
            gap = _whenever_delta_seconds(
                transition.offset - transition.subtract(seconds=1).offset
            )
            if 0 <= _whenever_delta_seconds(start_zdt - transition) < gap:
                # Recover nominal times in the gap whose shifted instants are still
                # ahead. Merge with ordinary times for non-hour gaps like Lord Howe.
                lookback = croniter(
                    self.cron,
                    start_naive_tz - datetime.timedelta(seconds=gap),
                    day_or=self.day_or,
                )
                gap_end = _whenever_to_stdlib(transition).replace(tzinfo=None)
                shifted_times = takewhile(
                    lambda wall: wall < gap_end,
                    iter(lambda: lookback.get_next(datetime.datetime), None),
                )
                candidate_dates = merge(
                    map(localize, shifted_times),
                    candidate_dates,
                    key=lambda date: date.astimezone(datetime.UTC),
                )

        start_utc = start.astimezone(datetime.UTC)
        end_utc = end.astimezone(datetime.UTC) if end else None
        dates = set()
        counter = 0
        for next_date in candidate_dates:
            next_utc = next_date.astimezone(datetime.UTC)

            # if the end date was exceeded, exit
            if end_utc and next_utc > end_utc:
                break
            # ensure no duplicates; weird things can happen with DST
            if next_utc >= start_utc and next_date not in dates:
                dates.add(next_date)
                yield create_datetime_instance(next_date)

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

    # Legacy Pendulum engine, preserved verbatim for the deprecation
    # window. Only reached on Python < 3.13; its internal
    # `sys.version_info >= (3, 13)` branches are unreachable.
    def _pendulum_dates_generator(
        self,
        n: int | None = None,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ) -> Generator[DateTime, None, None]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to the current date. If a timezone-naive
                datetime is provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): No returned date will exceed this date.
                If a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: a list of dates
        """
        if start is None:
            start = now("UTC")

        start, end = _prepare_scheduling_start_and_end(start, end, self.timezone)

        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up to
            # MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        if self.timezone:
            if sys.version_info >= (3, 13):
                start = start.astimezone(ZoneInfo(self.timezone or "UTC"))
            else:
                start = _pendulum_call(start, "in_tz", self.timezone)

        # subtract one second from the start date, so that croniter returns it
        # as an event (if it meets the cron criteria)
        start = start - datetime.timedelta(seconds=1)

        # Respect microseconds by rounding up
        if start.microsecond > 0:
            start += datetime.timedelta(seconds=1)

        # croniter's DST logic interferes with all other datetime libraries except pytz
        if sys.version_info >= (3, 13):
            start_localized = start.astimezone(ZoneInfo(self.timezone or "UTC"))
            start_naive_tz = start.replace(tzinfo=None)
        else:
            start_localized = pytz.timezone(start.tz.name).localize(
                datetime.datetime(
                    year=start.year,
                    month=start.month,
                    day=start.day,
                    hour=start.hour,
                    minute=start.minute,
                    second=start.second,
                    microsecond=start.microsecond,
                )
            )
            start_naive_tz = _pendulum_call(start, "naive")

        cron = croniter(self.cron, start_naive_tz, day_or=self.day_or)  # type: ignore
        dates = set()
        counter = 0

        while True:
            # croniter does not handle DST properly when the start time is
            # in and around when the actual shift occurs. To work around this,
            # we use the naive start time to get the next cron date delta, then
            # add that time to the original scheduling anchor.
            next_time = cron.get_next(datetime.datetime)
            delta = next_time - start_naive_tz
            if sys.version_info >= (3, 13):
                from whenever import ZonedDateTime

                # Use `whenever` to handle DST correctly
                _zdt_from_dt = (
                    ZonedDateTime
                    if hasattr(ZonedDateTime, "to_stdlib")
                    else ZonedDateTime.from_py_datetime
                )
                _zdt = _zdt_from_dt(start_localized + delta).to_tz(
                    self.timezone or "UTC"
                )
                next_date = (
                    _zdt.to_stdlib()
                    if hasattr(_zdt, "to_stdlib")
                    else _zdt.py_datetime()
                )
            else:
                next_date = create_datetime_instance(start_localized + delta)

            # if the end date was exceeded, exit
            if end and next_date > end:
                break
            # ensure no duplicates; weird things can happen with DST
            if next_date not in dates:
                dates.add(next_date)
                yield next_date

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1


DEFAULT_ANCHOR_DATE = datetime.date(2020, 1, 1)


class RRuleSchedule(PrefectBaseModel):
    """
    RRule schedule, based on the iCalendar standard
    ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) as
    implemented in `dateutils.rrule`.

    RRules are appropriate for any kind of calendar-date manipulation, including
    irregular intervals, repetition, exclusions, week day or day-of-month
    adjustments, and more.

    Note that as a calendar-oriented standard, `RRuleSchedules` are sensitive to
    to the initial timezone provided. A 9am daily schedule with a daylight saving
    time-aware start date will maintain a local 9am time through DST boundaries;
    a 9am daily schedule with a UTC start date will maintain a 9am UTC time.

    Args:
        rrule (str): a valid RRule string
        timezone (str, optional): a valid timezone string
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    rrule: str
    timezone: TimeZone | None = "UTC"

    @field_validator("rrule")
    @classmethod
    def validate_rrule_str(cls, v: str) -> str:
        return validate_rrule_string(v)

    @classmethod
    def from_rrule(
        cls, rrule: dateutil.rrule.rrule | dateutil.rrule.rruleset
    ) -> RRuleSchedule:
        if isinstance(rrule, dateutil.rrule.rrule):
            if rrule._dtstart.tzinfo is not None:
                timezone = getattr(rrule._dtstart.tzinfo, "name", None) or getattr(
                    rrule._dtstart.tzinfo, "key", "UTC"
                )
            else:
                timezone = "UTC"
            return RRuleSchedule(rrule=str(rrule), timezone=timezone)
        elif isinstance(rrule, dateutil.rrule.rruleset):
            dtstarts = [rr._dtstart for rr in rrule._rrule if rr._dtstart is not None]
            unique_dstarts = set(
                create_datetime_instance(d).astimezone(ZoneInfo("UTC"))
                for d in dtstarts
            )
            unique_timezones = set(d.tzinfo for d in dtstarts if d.tzinfo is not None)

            if len(unique_timezones) > 1:
                raise ValueError(
                    f"rruleset has too many dtstart timezones: {unique_timezones}"
                )

            if len(unique_dstarts) > 1:
                raise ValueError(f"rruleset has too many dtstarts: {unique_dstarts}")

            if unique_dstarts and unique_timezones:
                tzinfo = dtstarts[0].tzinfo
                timezone = getattr(tzinfo, "name", None) or getattr(
                    tzinfo, "key", "UTC"
                )
            else:
                timezone = "UTC"

            rruleset_string = ""
            if rrule._rrule:
                rruleset_string += "\n".join(str(r) for r in rrule._rrule)
            if rrule._exrule:
                rruleset_string += "\n" if rruleset_string else ""
                rruleset_string += "\n".join(str(r) for r in rrule._exrule).replace(
                    "RRULE", "EXRULE"
                )
            if rrule._rdate:
                rruleset_string += "\n" if rruleset_string else ""
                rruleset_string += "RDATE:" + ",".join(
                    rd.strftime("%Y%m%dT%H%M%SZ") for rd in rrule._rdate
                )
            if rrule._exdate:
                rruleset_string += "\n" if rruleset_string else ""
                rruleset_string += "EXDATE:" + ",".join(
                    exd.strftime("%Y%m%dT%H%M%SZ") for exd in rrule._exdate
                )
            return RRuleSchedule(rrule=rruleset_string, timezone=timezone)
        else:
            raise ValueError(f"Invalid RRule object: {rrule}")

    def to_rrule(self) -> dateutil.rrule.rrule:
        """
        Since rrule doesn't properly serialize/deserialize timezones, we localize dates
        here
        """
        rrule = dateutil.rrule.rrulestr(
            self.rrule,
            dtstart=DEFAULT_ANCHOR_DATE,
            cache=True,
        )
        timezone = dateutil.tz.gettz(self.timezone)
        if isinstance(rrule, dateutil.rrule.rrule):
            kwargs = dict(dtstart=rrule._dtstart.replace(tzinfo=timezone))
            if rrule._until:
                kwargs.update(
                    until=rrule._until.replace(tzinfo=timezone),
                )
            return rrule.replace(**kwargs)
        elif isinstance(rrule, dateutil.rrule.rruleset):
            # update rrules
            localized_rrules = []
            for rr in rrule._rrule:
                kwargs = dict(dtstart=rr._dtstart.replace(tzinfo=timezone))
                if rr._until:
                    kwargs.update(
                        until=rr._until.replace(tzinfo=timezone),
                    )
                localized_rrules.append(rr.replace(**kwargs))
            rrule._rrule = localized_rrules

            # update exrules
            localized_exrules = []
            for exr in rrule._exrule:
                kwargs = dict(dtstart=exr._dtstart.replace(tzinfo=timezone))
                if exr._until:
                    kwargs.update(
                        until=exr._until.replace(tzinfo=timezone),
                    )
                localized_exrules.append(exr.replace(**kwargs))
            rrule._exrule = localized_exrules

            # update rdates
            localized_rdates = []
            for rd in rrule._rdate:
                localized_rdates.append(rd.replace(tzinfo=timezone))
            rrule._rdate = localized_rdates

            # update exdates
            localized_exdates = []
            for exd in rrule._exdate:
                localized_exdates.append(exd.replace(tzinfo=timezone))
            rrule._exdate = localized_exdates

            return rrule

    async def get_dates(
        self,
        n: int | None = None,
        start: datetime.datetime = None,
        end: datetime.datetime = None,
    ) -> list[DateTime]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to None.  If a timezone-naive datetime is
                provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): The maximum scheduled date to return. If
                a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: A list of dates
        """
        return sorted(self._get_dates_generator(n=n, start=start, end=end))

    def _get_dates_generator(
        self,
        n: int | None = None,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ) -> Generator[DateTime, None, None]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to the current date. If a timezone-naive
                datetime is provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): No returned date will exceed this date.
                If a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: a list of dates
        """
        if start is None:
            start = now("UTC")

        start, end = _prepare_scheduling_start_and_end(start, end, self.timezone)

        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up
            # to MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        dates = set()
        counter = 0

        # pass count = None to account for discrepancies with duplicates around DST
        # boundaries
        for next_date in self.to_rrule().xafter(start, count=None, inc=True):
            next_date = create_datetime_instance(next_date).astimezone(
                ZoneInfo(self.timezone)
            )

            # if the end date was exceeded, exit
            if end and next_date > end:
                break

            # ensure no duplicates; weird things can happen with DST
            if next_date not in dates:
                dates.add(next_date)
                yield create_datetime_instance(next_date)

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1


SCHEDULE_TYPES = Union[IntervalSchedule, CronSchedule, RRuleSchedule]
