import time
from dateutil import rrule
from datetime import timedelta

import pendulum
import pytest
from pendulum import datetime, now
from pydantic import ValidationError

from prefect.orion.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)

dt = pendulum.datetime(2020, 1, 1)
RRDaily = "FREQ=DAILY"


class TestCreateIntervalSchedule:
    def test_interval_is_required(self):
        with pytest.raises(ValidationError, match="(field required)"):
            IntervalSchedule()

    @pytest.mark.parametrize("minutes", [-1, 0])
    def test_interval_must_be_positive(self, minutes):
        with pytest.raises(ValidationError, match="(interval must be positive)"):
            IntervalSchedule(interval=timedelta(minutes=minutes))

    def test_default_anchor(self):
        clock = IntervalSchedule(interval=timedelta(days=1))
        assert clock.anchor_date == datetime(2020, 1, 1, tz="UTC")

    def test_default_anchor_respects_timezone(self):
        clock = IntervalSchedule(interval=timedelta(days=1), timezone="EST")
        assert clock.anchor_date == datetime(2020, 1, 1, tz="EST")

    def test_anchor(self):
        dt = now()
        clock = IntervalSchedule(interval=timedelta(days=1), anchor_date=dt)
        assert clock.anchor_date == dt

    def test_cant_supply_timezone_and_anchor(self):
        with pytest.raises(ValidationError, match="(anchor date or a timezone)"):
            IntervalSchedule(
                interval=timedelta(days=1), timezone="EST", anchor_date=now()
            )

    def test_invalid_timezone(self):
        with pytest.raises(ValidationError, match="(Invalid timezone)"):
            IntervalSchedule(interval=timedelta(days=1), timezone="fake")


class TestIntervalSchedule:
    @pytest.mark.parametrize(
        "start_date",
        [datetime(2018, 1, 1), datetime(2021, 2, 2), datetime(2025, 3, 3)],
    )
    async def test_get_dates_from_start_date(self, start_date):
        clock = IntervalSchedule(
            interval=timedelta(days=1), anchor_date=datetime(2021, 1, 1)
        )
        dates = await clock.get_dates(n=5, start=start_date)
        assert dates == [start_date.add(days=i) for i in range(5)]

    @pytest.mark.parametrize(
        "end_date",
        [datetime(2018, 1, 1), datetime(2021, 2, 2), datetime(2025, 3, 3)],
    )
    async def test_get_dates_until_end_date(self, end_date):
        clock = IntervalSchedule(
            interval=timedelta(days=1), anchor_date=datetime(2021, 1, 1)
        )

        dates = await clock.get_dates(start=datetime(2018, 1, 1), end=end_date)
        assert len(dates) == (end_date - datetime(2018, 1, 1)).days + 1

    async def test_default_n_is_one_without_end_date(self):
        clock = IntervalSchedule(
            interval=timedelta(days=1), anchor_date=datetime(2021, 1, 1)
        )

        dates = await clock.get_dates(start=datetime(2018, 1, 1, 6))
        assert dates == [datetime(2018, 1, 2)]

    @pytest.mark.parametrize(
        "start_date",
        [datetime(2018, 1, 1), datetime(2021, 2, 2), datetime(2025, 3, 3)],
    )
    async def test_get_dates_from_start_date_with_timezone(self, start_date):
        clock = IntervalSchedule(interval=timedelta(days=1), timezone="EST")
        dates = await clock.get_dates(n=5, start=start_date)
        assert dates == [start_date.add(days=i).set(tz="EST") for i in range(5)]

    @pytest.mark.parametrize("n", [1, 2, 5])
    async def test_get_n_dates(self, n):
        clock = IntervalSchedule(interval=timedelta(days=1))
        assert len(await clock.get_dates(n=n)) == n

    async def test_get_dates_from_anchor(self):
        clock = IntervalSchedule(
            interval=timedelta(days=1), anchor_date=datetime(2020, 2, 2, 23, 35)
        )
        dates = await clock.get_dates(n=5, start=datetime(2021, 7, 1))
        assert dates == [datetime(2021, 7, 1, 23, 35).add(days=i) for i in range(5)]

    async def test_get_dates_from_future_anchor(self):
        clock = IntervalSchedule(
            interval=timedelta(hours=17), anchor_date=datetime(2030, 2, 2, 5, 24)
        )
        dates = await clock.get_dates(n=5, start=datetime(2021, 7, 1))
        assert dates == [
            datetime(2021, 7, 1, 7, 24).add(hours=i * 17) for i in range(5)
        ]


class TestCreateCronSchedule:
    def test_create_cron_schedule(self):
        clock = CronSchedule(cron="5 4 * * *")
        assert clock.cron == "5 4 * * *"

    def test_create_cron_schedule_with_timezone(self):
        clock = CronSchedule(cron="5 4 * * *", timezone="EST")
        assert clock.timezone == "EST"

    def test_invalid_timezone(self):
        with pytest.raises(ValidationError, match="(Invalid timezone)"):
            CronSchedule(interval=timedelta(days=1), timezone="fake")


class TestCronSchedule:
    every_day = "0 0 * * *"
    every_hour = "0 * * * *"

    async def test_every_day(self):
        clock = CronSchedule(cron=self.every_day)
        dates = await clock.get_dates(n=5, start=datetime(2021, 1, 1))
        assert dates == [datetime(2021, 1, 1).add(days=i) for i in range(5)]
        assert all(d.tz.name == "UTC" for d in dates)

    async def test_every_hour(self):
        clock = CronSchedule(cron=self.every_hour)
        dates = await clock.get_dates(n=5, start=datetime(2021, 1, 1))
        assert dates == [datetime(2021, 1, 1).add(hours=i) for i in range(5)]
        assert all(d.tz.name == "UTC" for d in dates)

    async def test_every_day_with_timezone(self):
        clock = CronSchedule(cron=self.every_hour, timezone="EST")
        dates = await clock.get_dates(n=5, start=datetime(2021, 1, 1))
        assert dates == [datetime(2021, 1, 1).add(hours=i) for i in range(5)]
        assert all(d.tz.name == "EST" for d in dates)

    async def test_every_day_with_timezone_start(self):
        clock = CronSchedule(cron=self.every_hour)
        dates = await clock.get_dates(n=5, start=datetime(2021, 1, 1).in_tz("EST"))
        assert dates == [datetime(2021, 1, 1).add(hours=i) for i in range(5)]
        assert all(d.tz.name == "EST" for d in dates)

    async def test_n(self):
        clock = CronSchedule(cron=self.every_day)
        dates = await clock.get_dates(n=10, start=datetime(2021, 1, 1))
        assert dates == [datetime(2021, 1, 1).add(days=i) for i in range(10)]

    async def test_start_date(self):
        start_date = datetime(2025, 5, 5)
        clock = CronSchedule(cron=self.every_day)
        dates = await clock.get_dates(n=10, start=start_date)
        assert dates == [start_date.add(days=i) for i in range(10)]

    @pytest.mark.parametrize(
        "end_date",
        [datetime(2018, 1, 1), datetime(2021, 2, 2), datetime(2022, 3, 3)],
    )
    async def test_get_dates_until_end_date(self, end_date):
        clock = CronSchedule(cron=self.every_day)
        dates = await clock.get_dates(start=datetime(2018, 1, 1), end=end_date)
        assert len(dates) == (end_date - datetime(2018, 1, 1)).days + 1

    async def test_default_n_is_one_without_end_date(self):
        clock = CronSchedule(cron=self.every_day)
        dates = await clock.get_dates(start=datetime(2018, 1, 1, 6))
        assert dates == [datetime(2018, 1, 2)]


class TestIntervalScheduleDaylightSavingsTime:
    async def test_interval_schedule_always_has_the_right_offset(self):
        """
        Tests the situation where a long duration has passed since the start date that crosses a DST boundary;
        for very short intervals this occasionally could result in "next" scheduled times that are in the past by one hour.
        """
        anchor_date = pendulum.from_timestamp(1582002945.964696).astimezone(
            pendulum.timezone("US/Pacific")
        )
        current_date = pendulum.from_timestamp(1593643144.233938).astimezone(
            pendulum.timezone("UTC")
        )
        s = IntervalSchedule(
            interval=timedelta(minutes=1, seconds=15), anchor_date=anchor_date
        )
        dates = await s.get_dates(n=4, start=current_date)
        assert all(d > current_date for d in dates)

    async def test_interval_schedule_hourly_daylight_savings_time_forward_with_UTC(
        self,
    ):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = datetime(2018, 3, 10, 23, tz="America/New_York")
        s = IntervalSchedule(interval=timedelta(hours=1))
        dates = await s.get_dates(n=5, start=dt)
        # skip 2am
        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 3, 4]
        # constant hourly clock in utc time
        assert [d.in_tz("UTC").hour for d in dates] == [4, 5, 6, 7, 8]

    async def test_interval_schedule_hourly_daylight_savings_time_forward(self):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = datetime(2018, 3, 10, 23, tz="America/New_York")
        s = IntervalSchedule(interval=timedelta(hours=1), timezone="America/New_York")
        dates = await s.get_dates(n=5, start=dt)
        # skip 2am
        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 3, 4]
        # constant hourly clock in utc time
        assert [d.in_tz("UTC").hour for d in dates] == [4, 5, 6, 7, 8]

    async def test_interval_schedule_hourly_daylight_savings_time_backward(self):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = datetime(2018, 11, 3, 23, tz="America/New_York")
        s = IntervalSchedule(interval=timedelta(hours=1), timezone="America/New_York")
        dates = await s.get_dates(n=5, start=dt)

        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 2, 3]
        # skips an hour UTC - note interval clocks skip the "6"
        assert [d.in_tz("UTC").hour for d in dates] == [3, 4, 5, 7, 8]

    async def test_interval_schedule_daily_start_daylight_savings_time_forward(self):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.

        Confirm that a clock for 9am America/New_York stays 9am through the switch.
        """
        dt = datetime(2018, 3, 8, 9, tz="America/New_York")
        s = IntervalSchedule(interval=timedelta(days=1), anchor_date=dt)
        dates = await s.get_dates(n=5, start=dt)
        # constant 9am start
        assert [d.in_tz("America/New_York").hour for d in dates] == [9, 9, 9, 9, 9]
        # utc time shifts
        assert [d.in_tz("UTC").hour for d in dates] == [14, 14, 14, 13, 13]

    async def test_interval_schedule_daily_start_daylight_savings_time_backward(self):
        """
        On 11/4/2018, at 2am, America/New_York switched clocks back an hour.

        Confirm that a clock for 9am America/New_York stays 9am through the switch.
        """
        dt = datetime(2018, 11, 1, 9, tz="America/New_York")
        s = IntervalSchedule(interval=timedelta(days=1), anchor_date=dt)
        dates = await s.get_dates(n=5, start=dt)
        # constant 9am start
        assert [d.in_tz("America/New_York").hour for d in dates] == [9, 9, 9, 9, 9]
        assert [d.in_tz("UTC").hour for d in dates] == [13, 13, 13, 14, 14]


class TestCronScheduleDaylightSavingsTime:
    """
    Tests that DST boundaries are respected
    """

    async def test_cron_schedule_hourly_daylight_savings_time_forward_ignored_with_UTC(
        self,
    ):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = datetime(2018, 3, 10, 23, tz="America/New_York")
        s = CronSchedule(cron="0 * * * *", timezone="America/New_York")
        dates = await s.get_dates(n=5, start=dt)

        # skip 2am
        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 3, 4]
        # constant hourly clock in utc time
        assert [d.in_tz("UTC").hour for d in dates] == [4, 5, 6, 7, 8]

    async def test_cron_schedule_hourly_daylight_savings_time_forward(self):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = datetime(2018, 3, 10, 23, tz="America/New_York")
        s = CronSchedule(cron="0 * * * *", timezone="America/New_York")
        dates = await s.get_dates(n=5, start=dt)

        # skip 2am
        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 3, 4]
        # constant hourly clock in utc time
        assert [d.in_tz("UTC").hour for d in dates] == [4, 5, 6, 7, 8]

    async def test_cron_schedule_hourly_daylight_savings_time_backward(self):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = datetime(2018, 11, 3, 23, tz="America/New_York")
        s = CronSchedule(cron="0 * * * *", timezone="America/New_York")
        dates = await s.get_dates(n=5, start=dt)

        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 2, 3]
        # skips an hour UTC - note cron clocks skip the "5"
        assert [d.in_tz("UTC").hour for d in dates] == [3, 4, 6, 7, 8]

    async def test_cron_schedule_daily_start_daylight_savings_time_forward(self):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.

        Confirm that a clock for 9am America/New_York stays 9am through the switch.
        """
        dt = datetime(2018, 3, 8, 9, tz="America/New_York")
        s = CronSchedule(cron="0 9 * * *", timezone="America/New_York")
        dates = await s.get_dates(n=5, start=dt)

        # constant 9am start
        assert [d.in_tz("America/New_York").hour for d in dates] == [9, 9, 9, 9, 9]
        # utc time shifts
        assert [d.in_tz("UTC").hour for d in dates] == [14, 14, 14, 13, 13]

    async def test_cron_schedule_daily_start_daylight_savings_time_backward(self):
        """
        On 11/4/2018, at 2am, America/New_York switched clocks back an hour.

        Confirm that a clock for 9am America/New_York stays 9am through the switch.
        """
        dt = datetime(2018, 11, 1, 9, tz="America/New_York")
        s = CronSchedule(cron="0 9 * * *", timezone="America/New_York")
        dates = await s.get_dates(n=5, start=dt)

        # constant 9am start
        assert [d.in_tz("America/New_York").hour for d in dates] == [9, 9, 9, 9, 9]
        assert [d.in_tz("UTC").hour for d in dates] == [13, 13, 13, 14, 14]


class TestRRuleScheduleDaylightSavingsTime:
    async def test_rrule_schedule_hourly_daylight_savings_time_forward_with_UTC(
        self,
    ):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = datetime(2018, 3, 11, 4, tz="UTC")
        s = RRuleSchedule.from_rrule(rrule.rrule(rrule.HOURLY, dtstart=dt))
        dates = await s.get_dates(n=5, start=dt)
        assert dates[0].tzinfo.name == "UTC"
        # skip 2am
        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 3, 4]
        # constant hourly clock in utc time
        assert [d.in_tz("UTC").hour for d in dates] == [4, 5, 6, 7, 8]

    async def test_rrule_schedule_hourly_daylight_savings_time_forward(self):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = datetime(2018, 3, 10, 23, tz="America/New_York")
        s = RRuleSchedule.from_rrule(rrule.rrule(rrule.HOURLY, dtstart=dt))
        dates = await s.get_dates(n=5, start=dt)
        # skip 2am
        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 3, 4]
        # constant hourly clock in utc time
        assert [d.in_tz("UTC").hour for d in dates] == [4, 5, 6, 7, 8]

    async def test_rrule_schedule_hourly_daylight_savings_time_backward(self):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = datetime(2018, 11, 3, 23, tz="America/New_York")
        s = RRuleSchedule.from_rrule(rrule.rrule(rrule.HOURLY, dtstart=dt))
        dates = await s.get_dates(n=5, start=dt)
        assert [d.in_tz("America/New_York").hour for d in dates] == [23, 0, 1, 2, 3]
        # skips an hour UTC - note rrule clocks skip the "6"
        assert [d.in_tz("UTC").hour for d in dates] == [3, 4, 5, 7, 8]

    async def test_rrule_schedule_daily_start_daylight_savings_time_forward(self):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.

        Confirm that a clock for 9am America/New_York stays 9am through the switch.
        """
        dt = datetime(2018, 3, 8, 9, tz="America/New_York")
        s = RRuleSchedule.from_rrule(rrule.rrule(rrule.DAILY, dtstart=dt))

        dates = await s.get_dates(n=5, start=dt)
        # constant 9am start
        assert [d.in_tz("America/New_York").hour for d in dates] == [9, 9, 9, 9, 9]
        # utc time shifts
        assert [d.in_tz("UTC").hour for d in dates] == [14, 14, 14, 13, 13]

    async def test_rrule_schedule_daily_start_daylight_savings_time_backward(self):
        """
        On 11/4/2018, at 2am, America/New_York switched clocks back an hour.

        Confirm that a clock for 9am America/New_York stays 9am through the switch.
        """
        dt = datetime(2018, 11, 1, 9, tz="America/New_York")
        s = RRuleSchedule.from_rrule(rrule.rrule(rrule.DAILY, dtstart=dt))
        dates = await s.get_dates(n=5, start=dt)
        # constant 9am start
        assert [d.in_tz("America/New_York").hour for d in dates] == [9, 9, 9, 9, 9]
        assert [d.in_tz("UTC").hour for d in dates] == [13, 13, 13, 14, 14]

    async def test_rrule_schedule_daily_start_daylight_savings_time_backward_utc(self):
        """
        On 11/4/2018, at 2am, America/New_York switched clocks back an hour.

        Confirm that a clock for 9am UTC stays 9am through the switch.
        """
        dt = datetime(2018, 11, 1, 9, tz="UTC")
        s = RRuleSchedule.from_rrule(rrule.rrule(rrule.DAILY, dtstart=dt))
        dates = await s.get_dates(n=5, start=dt)
        # constant 9am start
        assert [d.in_tz("America/New_York").hour for d in dates] == [5, 5, 5, 4, 4]
        assert [d.in_tz("UTC").hour for d in dates] == [9, 9, 9, 9, 9]


class TestCreateRRuleSchedule:
    async def test_rrule_is_required(self):
        with pytest.raises(ValidationError, match="(field required)"):
            RRuleSchedule()

    async def test_create_from_rrule_str(self):
        assert RRuleSchedule(rrule=RRDaily)

    async def test_create_from_rrule_obj(self):
        s = RRuleSchedule.from_rrule(rrule.rrulestr("FREQ=DAILY"))
        assert "RRULE:FREQ=DAILY" in s.rrule
        s = RRuleSchedule.from_rrule(rrule.rrule(freq=rrule.MONTHLY))
        assert "RRULE:FREQ=MONTHLY" in s.rrule

    async def test_create_from_rrule_obj_reads_timezone(self):
        s = RRuleSchedule.from_rrule(
            rrule.rrule(
                rrule.DAILY,
                dtstart=pendulum.datetime(2020, 1, 1, tz="America/New_York"),
            )
        )
        assert s.timezone == "America/New_York"

    async def test_default_timezone_is_utc(self):
        s = RRuleSchedule(rrule=RRDaily)
        assert s.timezone == "UTC"

    async def test_create_with_dtstart(self):
        s = RRuleSchedule(rrule="DTSTART:20210905T000000\nFREQ=DAILY")
        assert "DTSTART:20210905T000000" in str(s.rrule)
        assert s.timezone == "UTC"

    async def test_create_with_timezone(self):
        s = RRuleSchedule(
            rrule="DTSTART:20210101T000000\nFREQ=DAILY", timezone="America/New_York"
        )
        assert s.timezone == "America/New_York"

        dates = await s.get_dates(5)
        assert dates[0].tz.name == "America/New_York"
        assert dates == [
            pendulum.now("America/New_York").start_of("day").add(days=i + 1)
            for i in range(5)
        ]


class TestRRuleSchedule:
    @pytest.mark.parametrize(
        "start_date",
        [datetime(2018, 1, 1), datetime(2021, 2, 2), datetime(2025, 3, 3)],
    )
    async def test_daily_with_start_date(self, start_date):
        s = RRuleSchedule.from_rrule(rrule.rrule(freq=rrule.DAILY, dtstart=start_date))
        dates = await s.get_dates(5, start=start_date)
        assert dates == [start_date.add(days=i) for i in range(5)]

    @pytest.mark.parametrize(
        "start_date",
        [datetime(2018, 1, 1), datetime(2021, 2, 2), datetime(2025, 3, 3)],
    )
    async def test_daily_with_end_date(self, start_date):
        s = RRuleSchedule.from_rrule(rrule.rrule(freq=rrule.DAILY, dtstart=start_date))
        dates = await s.get_dates(
            5, start=start_date, end=start_date.add(days=2, hours=-1)
        )
        assert dates == [start_date.add(days=i) for i in range(2)]

    async def test_rrule_returns_nothing_before_dtstart(self):
        s = RRuleSchedule.from_rrule(
            rrule.rrule(freq=rrule.DAILY, dtstart=pendulum.datetime(2030, 1, 1))
        )
        dates = await s.get_dates(5, start=pendulum.now("UTC"))
        assert dates == [pendulum.datetime(2030, 1, 1).add(days=i) for i in range(5)]

    async def test_rrule_returns_nothing_before_dtstart(self):
        s = RRuleSchedule.from_rrule(
            rrule.rrule(freq=rrule.DAILY, dtstart=pendulum.datetime(2030, 1, 1))
        )
        dates = await s.get_dates(5, start=pendulum.now("UTC"))
        assert dates == [pendulum.datetime(2030, 1, 1).add(days=i) for i in range(5)]

    @pytest.mark.parametrize(
        "rrule_obj,rrule_str,expected_dts",
        [
            # Every third year (INTERVAL) on the first Tuesday (BYDAY) after a Monday (BYMONTHDAY) in October.
            (
                rrule.rrule(
                    rrule.YEARLY,
                    dt,
                    interval=3,
                    bymonth=10,
                    byweekday=rrule.TU,
                    bymonthday=(2, 3, 4, 5, 6, 7, 8),
                ),
                "DTSTART:20200101T000000\nRRULE:FREQ=YEARLY;INTERVAL=3;BYMONTH=10;BYMONTHDAY=2,3,4,5,6,7,8;BYDAY=TU",
                [
                    pendulum.datetime(2020, 10, 6, 0, 0),
                    pendulum.datetime(2023, 10, 3, 0, 0),
                    pendulum.datetime(2026, 10, 6, 0, 0),
                ],
            ),
            # every minute
            (
                rrule.rrule(rrule.MINUTELY, dt),
                "DTSTART:20200101T000000\nRRULE:FREQ=MINUTELY",
                [
                    dt.add(minutes=0),
                    dt.add(minutes=1),
                    dt.add(minutes=2),
                ],
            ),
            # last weekday of every other month
            (
                rrule.rrule(
                    rrule.MONTHLY,
                    dt,
                    interval=2,
                    byweekday=(rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR),
                    bysetpos=-1,
                ),
                "DTSTART:20200101T000000\nRRULE:FREQ=MONTHLY;INTERVAL=2;BYSETPOS=-1;BYDAY=MO,TU,WE,TH,FR",
                [
                    pendulum.datetime(2020, 1, 31),
                    pendulum.datetime(2020, 3, 31),
                    pendulum.datetime(2020, 5, 29),
                ],
            ),
            # Every weekday (BYDAY) for the next 8 weekdays (COUNT).
            (
                rrule.rrule(
                    rrule.DAILY,
                    dt,
                    byweekday=(rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR),
                    count=8,
                ),
                "DTSTART:20200101T000000\nRRULE:FREQ=DAILY;COUNT=8;BYDAY=MO,TU,WE,TH,FR",
                [
                    pendulum.datetime(2020, 1, 1),
                    pendulum.datetime(2020, 1, 2),
                    pendulum.datetime(2020, 1, 3),
                ],
            ),
            # Every three weeks on Sunday until 9/23/2021
            (
                rrule.rrule(
                    rrule.WEEKLY,
                    dt,
                    byweekday=rrule.SU,
                    interval=3,
                    until=pendulum.datetime(2021, 9, 23, tz="UTC"),
                ),
                "DTSTART:20200101T000000\nRRULE:FREQ=WEEKLY;INTERVAL=3;UNTIL=20210923T000000;BYDAY=SU",
                [
                    pendulum.datetime(2020, 1, 5),
                    pendulum.datetime(2020, 1, 26),
                    pendulum.datetime(2020, 2, 16),
                ],
            ),
            # every week at 9:13:54
            (
                rrule.rrule(rrule.WEEKLY, dt, byhour=9, byminute=13, bysecond=54),
                "DTSTART:20200101T000000\nRRULE:FREQ=WEEKLY;BYHOUR=9;BYMINUTE=13;BYSECOND=54",
                [
                    pendulum.datetime(2020, 1, 1, 9, 13, 54),
                    pendulum.datetime(2020, 1, 8, 9, 13, 54),
                    pendulum.datetime(2020, 1, 15, 9, 13, 54),
                ],
            ),
            # every year on the 7th and 16th week, on the first weekday
            (
                rrule.rrule(rrule.YEARLY, dt, byweekno=(7, 16), byweekday=rrule.WE),
                "DTSTART:20200101T000000\nRRULE:FREQ=YEARLY;BYWEEKNO=7,16;BYDAY=WE",
                [
                    pendulum.datetime(2020, 2, 12),
                    pendulum.datetime(2020, 4, 15),
                    pendulum.datetime(2021, 2, 17),
                ],
            ),
        ],
    )
    async def test_rrule(self, rrule_obj, rrule_str, expected_dts):
        s = RRuleSchedule.from_rrule(rrule_obj)
        assert s.dict()["rrule"] == rrule_str
        dates = await s.get_dates(n=3, start=dt)
        assert dates == expected_dts

    async def test_rrule_with_count(self):
        # Every weekday (BYDAY) for the next 8 weekdays (COUNT).
        s = RRuleSchedule.from_rrule(
            rrule.rrule(
                rrule.DAILY,
                dt,
                byweekday=(rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR),
                count=8,
            )
        )
        assert (
            s.dict()["rrule"]
            == "DTSTART:20200101T000000\nRRULE:FREQ=DAILY;COUNT=8;BYDAY=MO,TU,WE,TH,FR"
        )
        dates = await s.get_dates(n=100, start=dt)
        assert dates == [
            dt.add(days=0),
            dt.add(days=1),
            dt.add(days=2),
            dt.add(days=5),
            dt.add(days=6),
            dt.add(days=7),
            dt.add(days=8),
            dt.add(days=9),
        ]
