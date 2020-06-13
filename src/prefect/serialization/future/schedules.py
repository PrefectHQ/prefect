import datetime
from pydantic import Field
from typing import Dict, List, Any, Union, Callable
import prefect
from prefect.utilities.serialization_future import Serializable, PolymorphicSerializable
from prefect.serialization.future.results import Result


class Clock(PolymorphicSerializable):
    # all clocks
    start_date: datetime.datetime = None
    end_date: datetime.datetime = None
    parameter_defaults: Dict[str, Any] = None

    # IntervalClock
    interval: datetime.timedelta = None

    # CronClock
    cron: str = None

    # DatesClock
    dates: List[datetime.datetime] = None

    @classmethod
    def from_clock(cls, clock: prefect.schedules.clocks.Clock) -> "Clock":
        return super()._from_object(clock)

    def to_clock(self) -> prefect.schedules.clocks.Clock:
        return super()._to_object()


ScheduleFunctions = List[Union[Callable[[datetime.datetime], bool], Serializable]]


class Schedule(Serializable):
    clocks: List[Clock]
    filters: ScheduleFunctions = Field(default_factory=list)
    or_filters: ScheduleFunctions = Field(default_factory=list)
    not_filters: ScheduleFunctions = Field(default_factory=list)
    adjustments: ScheduleFunctions = Field(default_factory=list)

    @classmethod
    def from_schedule(cls, schedule: prefect.schedules.Schedule) -> "Schedule":
        return super()._from_object(
            schedule, clocks=[Clock.from_clock(c) for c in schedule.clocks]
        )

    def to_schedule(self) -> prefect.schedules.Schedule:
        return super()._to_object()
