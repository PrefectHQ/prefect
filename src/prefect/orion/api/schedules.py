import pendulum
from pydantic import BaseModel, conint, Field, validator
import datetime
from typing import Set, List


class IntervalSchedule(BaseModel):
    class Config:
        extra = "forbid"

    interval: datetime.timedelta
    anchor: datetime.datetime = Field(default_factory=lambda: pendulum.now("utc"))

    # filters
    months: Set[conint(ge=1, le=12)] = Field(default_factory=set)
    days_of_month: Set[conint(ge=-31, le=31)] = Field(default_factory=set)
    days_of_week: Set[conint(ge=0, le=6)] = Field(default_factory=set)
    hours_of_day: Set[conint(ge=0, le=23)] = Field(default_factory=set)
    minutes_of_hour: Set[conint(ge=0, le=59)] = Field(default_factory=set)

    # adjustments
    advance_to_next_business_day: bool = False

    @validator("days_of_month")
    def zero_is_invalid_day_of_month(cls, v):
        if 0 in v:
            raise ValueError("0 is not a valid day of the month")
        return v

    @validator("interval")
    def interval_must_be_positive(cls, v):
        if v.total_seconds() <= 0:
            raise ValueError("The interval must be positive")
        return v

    def get_dates(
        self, n: int, start: datetime.datetime = None
    ) -> List[datetime.datetime]:
        """Retrieves dates from the schedule

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or after
                this date. Defaults to None.

        Returns:
            List[pendulum.DateTime]: a list of dates
        """
        if start is None:
            start = pendulum.now("utc")

        # compute the offset between the anchor date and the start date to jump to the next date
        offset = (start - self.anchor).total_seconds() / self.interval.total_seconds()
        next_date = self.anchor.add(seconds=self.interval.total_seconds() * int(offset))

        # daylight savings time boundaries can create a situation where the next date is before
        # the start date, so we advance it if necessary
        while next_date < start:
            next_date += self.interval

        counter = 0
        dates = []

        # don't exceed 1000 candidates
        while len(dates) < n and counter < 1000:

            # check filters
            if self.evaluate_filters(next_date):

                # advance to the next business day
                if self.advance_to_next_business_day:
                    while next_date.weekday() >= 5:
                        next_date += self.interval

                dates.append(next_date)

            counter += 1
            next_date += self.interval

        return dates

    def evaluate_filters(self, dt: pendulum.DateTime) -> bool:
        """Evaluates whether a candidate date satisfies the filters
        applied to this schedule.

        Args:
            dt (pendulum.DateTime): A candidate date

        Returns:
            bool: True if the datetime passes the filters; False otherwise
        """
        if self.months and dt.month not in self.months:
            return False

        if self.days_of_month:
            negative_day = dt.day - dt.end_of("month").day - 1
            if (
                dt.day not in self.days_of_month
                and negative_day not in self.days_of_month
            ):
                return False

        if self.days_of_week and dt.weekday() not in self.days_of_week:
            return False

        if self.hours_of_day and dt.hour not in self.hours_of_day:
            return False

        if self.minutes_of_hour and dt.minute not in self.minutes_of_hour:
            return False

        return True
