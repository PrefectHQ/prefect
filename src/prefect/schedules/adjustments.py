"""
Schedule adjustments are functions that accept a `datetime` and modify it in some way.

Adjustments have the signature `Callable[[datetime], datetime]`.
"""
from datetime import datetime, timedelta
from typing import Callable

import pendulum

from prefect.utilities.serialization_future import Serializable
import prefect.schedules.filters


class add(Serializable):
    """
    Adjustment that adds a specified interval to the date.

    Args:
        - interval (timedelta): the amount of time to add

    Returns:
        - Callable[[datetime], bool]: the adjustment function
    """
    interval: timedelta

    def __call__(self, dt: datetime) -> datetime:
        return pendulum.instance(dt) + self.interval


def next_weekday(dt: datetime) -> datetime:
    """
    Adjustment that advances a date to the next weekday. If the date is already a weekday,
    it is returned unadjusted.

    Args:
        - dt (datetime): the datetime to adjust

    Returns:
        - datetime: the adjusted datetime
    """
    pdt = pendulum.instance(dt)
    while not prefect.schedules.filters.is_weekday(pdt):
        pdt = pdt.add(days=1)
    return pdt
