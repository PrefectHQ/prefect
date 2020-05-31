"""
Schedule filters are functions that accept a candidate `datetime` and return `True` if
the candidate is valid, and `False` otherwise.

Filters have the signature `Callable[[datetime], bool]`.
"""

from datetime import datetime, time

import pendulum


class on_datetime:
    """
    Filter that allows events that match a specific datetime.

    Args:
        - dt (datetime): the datetime to match
    """

    def __init__(self, dt: datetime):
        self.kwargs = dict(dt=dt)

    def __call__(self, dt: datetime) -> bool:
        return dt == self.kwargs["dt"]


class between_datetimes:
    """
    Filter that allows events between a start time and end time

    Args:
        - start (datetime): the start datetime
        - end (datetime): the end datetime
    """

    def __init__(self, start: datetime, end: datetime):
        self.kwargs = dict(start=start, end=end)

    def __call__(self, dt: datetime) -> bool:
        return dt >= self.kwargs["start"] and dt <= self.kwargs["end"]


class on_date:
    """
    Filter that allows events that match a specific date in any year

    Args:
        - month (int): the month as a number (1 = January)
        - day (int): the day as a number
    """

    def __init__(self, month: int, day: int):
        self.kwargs = dict(month=month, day=day)

    def __call__(self, dt: datetime) -> bool:
        return (dt.month, dt.day) == (self.kwargs["month"], self.kwargs["day"])


class between_dates:
    """
    Filter that allows events between specific dates in each year.

    For example, `between_dates(10, 15, 3, 31)` would only allow dates between October 15
    and March 31 in any year.

    Args:
        - start_month (int): the starting month, as a number (1 = January)
        - start_day (int): the starting day, as a number
        - end_month (int): the ending month, as a number
        - end_day (int): the ending day, as a number
    """

    def __init__(self, start_month: int, start_day: int, end_month: int, end_day: int):
        self.kwargs = dict(
            start_month=start_month,
            start_day=start_day,
            end_month=end_month,
            end_day=end_day,
        )

    def __call__(self, dt: datetime) -> bool:
        date = (dt.month, dt.day)

        # if the start is before the end, then these reflect dates in the same year
        if self.kwargs["start_month"] <= self.kwargs["end_month"]:
            return date >= (
                self.kwargs["start_month"],
                self.kwargs["start_day"],
            ) and date <= (self.kwargs["end_month"], self.kwargs["end_day"],)
        # otherwise they represent dates across two years
        else:
            return date >= (
                self.kwargs["start_month"],
                self.kwargs["start_day"],
            ) or date <= (self.kwargs["end_month"], self.kwargs["end_day"],)


class at_time:
    """
    Filter that allows events that match a specific time.

    For example, `at_time(datetime.time(4))` would only allow runs at 4 AM
    in the given timezone.

    Args:
        - t (time): the time to match
    """

    def __init__(self, t: time):
        self.kwargs = dict(t=t)

    def __call__(self, dt: datetime) -> bool:
        return dt.time() == self.kwargs["t"]


class between_times:
    """
    Filter that allows events between a start time and end time

    For example, `between_times(start=datetime.time(14), end=datetime.time(16))` would only
    allow runs between the hours of 2 PM and 4 PM in the given timezone.

    Args:
        - start (time): the start time
        - end (time): the end time
    """

    def __init__(self, start: time, end: time):
        self.kwargs = dict(start=start, end=end)

    def __call__(self, dt: datetime) -> bool:

        # if the start is before the end, these represents times in the same day
        if self.kwargs["start"] <= self.kwargs["end"]:
            return dt.time() >= self.kwargs["start"] and dt.time() <= self.kwargs["end"]
        # otherwise they represent times across two days
        else:
            return dt.time() >= self.kwargs["start"] or dt.time() <= self.kwargs["end"]


def is_weekday(dt: datetime) -> bool:
    """
    Filter that only allows events on weekdays

    Args:
        - dt (datetime): the candidate datetime

    Returns:
        - bool: True if the date is a weekday; False otherwise
    """
    return pendulum.instance(dt).weekday() < 5


def is_month_end(dt: datetime) -> bool:
    """
    Filter that only allows events on the last day of the month

    Args:
        - dt (datetime): the candidate datetime

    Returns:
        - bool: True if the date is a month-end; False otherwise
    """
    pdt = pendulum.instance(dt)
    return pdt.month != pdt.add(days=1).month


def is_weekend(dt: datetime) -> bool:
    """
    Filter that only allows events on weekends

    Args:
        - dt (datetime): the candidate datetime

    Returns:
        - bool: True if the date is a weekend; False otherwise
    """
    return pendulum.instance(dt).weekday() > 4
