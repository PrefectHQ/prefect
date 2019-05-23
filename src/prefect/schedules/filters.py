"""
Schedule filters are functions that accept a candidate `datetime` and return `True` if
the candidate is valid, and `False` otherwise.

Filters have the signature `Callable[[datetime], bool]`.
"""

from datetime import datetime, time
from typing import Callable

import pendulum


def between_datetimes(start: datetime, end: datetime) -> Callable[[datetime], bool]:
    """
    Filter that allows events between a start time and end time

    Args:
        - start (datetime): the start datetime
        - end (datetime): the end datetime

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    def _filter_fn(dt: datetime) -> bool:
        return dt >= start and dt <= end

    return _filter_fn


def between_dates(
    start_month: int, start_day: int, end_month: int, end_day: int
) -> Callable[[datetime], bool]:
    """
    Filter that allows events between specific dates in each year.

    For example, `between_dates(10, 15, 3, 31)` would only allow dates between October 15
    and March 31 in any year.

    Args:
        - start_month (int): the starting month, as a number
        - start_day (int): the starting day, as a number
        - end_month (int): the ending month, as a number
        - end_day (int): the ending day, as a number

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    def _filter_fn(dt: datetime) -> bool:
        date = (dt.month, dt.day)

        # if the start is before the end, then these reflect dates in the same year
        if start_month <= end_month:
            return date >= (start_month, start_day) and date <= (end_month, end_day)
        # otherwise they represent dates across two years
        else:
            return date >= (start_month, start_day) or date <= (end_month, end_day)

    return _filter_fn


def between_times(start: time, end: time) -> Callable[[datetime], bool]:
    """
    Filter that allows events between a start time and end time

    Args:
        - start (time): the start time
        - end (time): the end time

    Returns:
        - Callable[[datetime], bool]: a filter function
    """

    def _filter_fn(dt: datetime) -> bool:

        # if the start is before the end, these represents times in the same day
        if start <= end:
            return dt.time() >= start and dt.time() <= end
        # otherwise they represent times across two days
        else:
            return dt.time() >= start or dt.time() <= end

    return _filter_fn


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
