# date_utils.py
import pendulum
from typing import List, Optional

MAX_ITERATIONS = 1000


def get_dates(
    anchor_date: pendulum.DateTime,
    interval: pendulum.Duration,
    timezone: str,
    n: Optional[int] = None,
    start: Optional[pendulum.DateTime] = None,
    end: Optional[pendulum.DateTime] = None,
) -> List[pendulum.DateTime]:
    if n is None:
        if end is not None:
            n = MAX_ITERATIONS
        else:
            n = 1

    if start is None:
        start = pendulum.now(timezone)

    offset = (
        start - anchor_date.in_tz(timezone)
    ).total_seconds() / interval.total_seconds()
    next_date = anchor_date.add(seconds=interval.total_seconds() * int(offset))

    interval_days = interval.days
    interval_seconds = interval.total_seconds() - (interval_days * 24 * 60 * 60)

    while next_date < start:
        next_date = next_date.add(days=interval_days, seconds=interval_seconds)

    counter = 0
    dates = set()
    generated_dates = []

    while True:
        if end and next_date > end:
            break

        if next_date not in dates:
            dates.add(next_date)
            generated_dates.append(next_date)

        if len(dates) >= n or counter > MAX_ITERATIONS:
            break

        counter += 1
        next_date = next_date.add(days=interval_days, seconds=interval_seconds)

    return generated_dates
