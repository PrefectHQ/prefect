from __future__ import annotations

import pendulum
from pendulum.date import Date as PendulumDate
from pendulum.datetime import DateTime as PendulumDateTime
from pendulum.duration import Duration as PendulumDuration
from pendulum.time import Time as PendulumTime
from pydantic_extra_types.pendulum_dt import Date as PydanticDate
from pydantic_extra_types.pendulum_dt import DateTime as PydanticDateTime
from typing_extensions import TypeAlias

DateTime: TypeAlias = PydanticDateTime
Date: TypeAlias = PydanticDate


def parse_datetime(
    value: str,
) -> PendulumDateTime | PendulumDate | PendulumTime | PendulumDuration:
    return pendulum.parse(value)
