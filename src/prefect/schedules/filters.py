"""
Schedule filters are functions that accept a candidate `datetime` and return `True` if
the candidate is valid, and `False` otherwise.

Filters have the signature `Callable[[datetime], bool]`.
"""

from datetime import datetime, time
from typing import Callable

import pendulum
from prefect.utilities.serialization_future import Serializable


class on_datetime(Serializable):

    """
    Filter that allows events that match a specific datetime.

    Args:
        - dt (datetime): the datetime to match

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    dt: datetime

    def __call__(self, dt: datetime) -> bool:
        return dt == self.dt


class between_datetimes(Serializable):
    """
    Filter that allows events between a start time and end time

    Args:
        - start (datetime): the start datetime
        - end (datetime): the end datetime

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    start: datetime
    end: datetime

    def __call__(self, dt: datetime) -> bool:
        return dt >= self.start and dt <= self.end


class on_date(Serializable):
    """
    Filter that allows events that match a specific date in any year

    Args:
        - month (int): the month as a number (1 = January)
        - day (int): the day as a number

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    month: int
    day: int

    def __call__(self, dt: datetime) -> bool:
        return (dt.month, dt.day) == (self.month, self.day)


class between_dates(Serializable):
    """
    Filter that allows events between specific dates in each year.

    For example, `between_dates(10, 15, 3, 31)` would only allow dates between October 15
    and March 31 in any year.

    Args:
        - start_month (int): the starting month, as a number (1 = January)
        - start_day (int): the starting day, as a number
        - end_month (int): the ending month, as a number
        - end_day (int): the ending day, as a number

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    start_month: int
    start_day: int
    end_month: int
    end_day: int

    def __call__(self, dt: datetime) -> bool:
        date = (dt.month, dt.day)

        # if the start is before the end, then these reflect dates in the same year
        if self.start_month <= self.end_month:
            return date >= (self.start_month, self.start_day) and date <= (
                self.end_month,
                self.end_day,
            )
        # otherwise they represent dates across two years
        else:
            return date >= (self.start_month, self.start_day) or date <= (
                self.end_month,
                self.end_day,
            )


class at_time(Serializable):
    """
    Filter that allows events that match a specific time.

    For example, `at_time(datetime.time(4))` would only allow runs at 4 AM
    in the given timezone.

    Args:
        - t (time): the time to match

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    t: time

    def __call__(self, dt: datetime) -> bool:
        return dt.time() == self.t


class between_times(Serializable):
    """
    Filter that allows events between a start time and end time

    For example, `between_times(start=datetime.time(14), end=datetime.time(16))` would only
    allow runs between the hours of 2 PM and 4 PM in the given timezone.

    Args:
        - start (time): the start time
        - end (time): the end time

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    start: time
    end: time

    def __call__(self, dt: datetime) -> bool:

        # if the start is before the end, these represents times in the same day
        if self.start <= self.end:
            return dt.time() >= self.start and dt.time() <= self.end
        # otherwise they represent times across two days
        else:
            return dt.time() >= self.start or dt.time() <= self.end


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
