from datetime import datetime as pydatetime
from datetime import timedelta
from unittest import mock

import dateutil
import pendulum
import pytest
from dateutil import rrule
from pendulum import datetime, now
from pydantic import ValidationError

from prefect.orion.schemas.schedules import (
    MAX_ITERATIONS,
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
        mock_now = pendulum.datetime(
            year=2022,
            month=1,
            day=1,
            hour=1,
            minute=1,
        )
        with mock.patch("pendulum.now", return_value=mock_now):
            clock = IntervalSchedule(interval=timedelta(days=1))
        assert clock.anchor_date == mock_now
        assert clock.timezone == "UTC"

    def test_default_timezone_from_anchor_date(self):
        clock = IntervalSchedule(
            interval=timedelta(days=1), anchor_date=pendulum.now("America/New_York")
        )
        assert clock.timezone == "America/New_York"

    def test_different_anchor_date_and_timezone(self):
        # this is totally fine because the anchordate is serialized as a UTC offset
        # but the timezone tells us how to localize it
        clock = IntervalSchedule(
            interval=timedelta(days=1),
            timezone="America/Los_Angeles",
            anchor_date=pendulum.now("America/New_York"),
        )
        assert clock.timezone == "America/Los_Angeles"
        assert clock.anchor_date.tz.name == "America/New_York"

    def test_anchor(self):
        dt = now()
        clock = IntervalSchedule(interval=timedelta(days=1), anchor_date=dt)
        assert clock.anchor_date == dt

    def test_invalid_timezone(self):
        with pytest.raises(ValidationError, match="(Invalid timezone)"):
            IntervalSchedule(interval=timedelta(days=1), timezone="fake")

    def test_infer_utc_offset_timezone(self):
        # when pendulum parses a datetime, it keeps the UTC offset as the "timezone"
        # and we need to make sure this doesn't get picked up as the schedule's timezone
        # since the schedule should infer that it has the same behavior as "UTC"
        offset_dt = pendulum.parse(str(pendulum.now("America/New_York")))
        clock = IntervalSchedule(interval=timedelta(days=1), anchor_date=offset_dt)
        assert clock.timezone == "UTC"

    def test_parse_utc_offset_timezone(self):
        offset_dt = pendulum.parse(str(pendulum.now("America/New_York")))
        clock = IntervalSchedule(interval=timedelta(days=1), anchor_date=offset_dt)
        clock_dict = clock.dict(json_compatible=True)

        # remove the timezone
        clock_dict.pop("timezone")
        # the offset is part of the clock_dict (check for DST)
        assert clock_dict["anchor_date"].endswith("-04:00") or clock_dict[
            "anchor_date"
        ].endswith("-05:00")

        parsed = IntervalSchedule.parse_obj(clock_dict)
        assert parsed.anchor_date.tz.name in ("-04:00", "-05:00")
        assert parsed.timezone == "UTC"

    def test_parse_utc_offset_timezone_with_specified_tz(self):
        offset_dt = pendulum.parse(str(pendulum.now("America/New_York")))
        clock = IntervalSchedule(
            interval=timedelta(days=1),
            anchor_date=offset_dt,
            timezone="America/New_York",
        )
        clock_dict = clock.dict(json_compatible=True)
        assert IntervalSchedule.parse_obj(clock_dict).timezone == "America/New_York"


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
        assert len(dates) == min(
            MAX_ITERATIONS,
            (end_date - datetime(2018, 1, 1)).days + 1,
        )

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
        clock = IntervalSchedule(
            interval=timedelta(days=1),
            anchor_date=start_date,
            timezone="America/New_York",
        )
        dates = await clock.get_dates(n=5, start=start_date)

        assert dates == [start_date.add(days=i).in_tz(clock.timezone) for i in range(5)]

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

    async def test_get_dates_from_offset_naive_anchor(self):
        # Regression test for https://github.com/PrefectHQ/orion/issues/2466
        clock = IntervalSchedule(
            interval=timedelta(days=1),
            anchor_date=pydatetime(2022, 1, 1),
        )
        dates = await clock.get_dates(start=datetime(2022, 1, 1), n=3)
        assert dates == [
            datetime(2022, 1, 1),
            datetime(2022, 1, 2),
            datetime(2022, 1, 3),
        ]

    async def test_get_dates_from_offset_naive_start(self):
        # Regression test for https://github.com/PrefectHQ/orion/issues/2466
        clock = IntervalSchedule(
            interval=timedelta(days=1),
            anchor_date=datetime(2022, 1, 1),
        )
        dates = await clock.get_dates(
            start=pydatetime(2022, 1, 1),
            end=datetime(2022, 1, 3),
        )
        assert dates == [
            datetime(2022, 1, 1),
            datetime(2022, 1, 2),
            datetime(2022, 1, 3),
        ]

    async def test_get_dates_from_offset_naive_end(self):
        # Regression test for https://github.com/PrefectHQ/orion/issues/2466
        clock = IntervalSchedule(
            interval=timedelta(days=1),
            anchor_date=datetime(2022, 1, 1),
        )
        dates = await clock.get_dates(
            start=datetime(2022, 1, 1),
            end=pydatetime(2022, 1, 3),
        )
        assert dates == [
            datetime(2022, 1, 1),
            datetime(2022, 1, 2),
            datetime(2022, 1, 3),
        ]


class TestCreateCronSchedule:
    def test_create_cron_schedule(self):
        clock = CronSchedule(cron="5 4 * * *")
        assert clock.cron == "5 4 * * *"

    @pytest.mark.parametrize(
        "cron_string",
        [
            "@yearly",
            "@weekly",
            "@daily",
            "@hourly",
            "* * * * MON",
            "30 8 * * sat-sun",
            "* * * * mon,wed,fri",
        ],
    )
    def test_create_cron_schedule_with_keywords(self, cron_string):
        clock = CronSchedule(cron=cron_string)
        assert clock.cron == cron_string

    def test_create_cron_schedule_with_timezone(self):
        clock = CronSchedule(cron="5 4 * * *", timezone="America/New_York")
        assert clock.timezone == "America/New_York"

    def test_invalid_timezone(self):
        with pytest.raises(ValidationError, match="(Invalid timezone)"):
            CronSchedule(cron="5 4 * * *", timezone="fake")

    @pytest.mark.parametrize("cron_string", ["invalid cron"])
    def test_invalid_cron_string(self, cron_string):
        with pytest.raises(ValidationError, match="(Invalid cron)"):
            CronSchedule(cron=cron_string)

    @pytest.mark.parametrize("cron_string", ["5 4 R * *"])
    def test_unsupported_cron_string(self, cron_string):
        with pytest.raises(
            ValidationError, match="(Random and Hashed expressions are unsupported)"
        ):
            CronSchedule(cron=cron_string)


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
        clock = CronSchedule(cron=self.every_hour, timezone="America/New_York")
        dates = await clock.get_dates(n=5, start=datetime(2021, 1, 1))
        assert dates == [datetime(2021, 1, 1).add(hours=i) for i in range(5)]
        assert all(d.tz.name == "America/New_York" for d in dates)

    async def test_every_day_with_timezone_start(self):
        clock = CronSchedule(cron=self.every_hour)
        dates = await clock.get_dates(
            n=5, start=datetime(2021, 1, 1).in_tz("America/New_York")
        )
        assert dates == [datetime(2021, 1, 1).add(hours=i) for i in range(5)]
        assert all(d.tz.name == "UTC" for d in dates)

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
        assert len(dates) == min(
            MAX_ITERATIONS, (end_date - datetime(2018, 1, 1)).days + 1
        )

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

    async def test_rrule_validates_rrule_str(self):
        # generic validation error
        with pytest.raises(ValidationError, match="(Invalid RRule string)"):
            RRuleSchedule(rrule="bad rrule string")

        # generic validation error
        with pytest.raises(ValidationError, match="(Invalid RRule string)"):
            RRuleSchedule(rrule="FREQ=DAILYBAD")

        # informative error when possible
        with pytest.raises(ValidationError, match="(invalid 'FREQ': DAILYBAD)"):
            RRuleSchedule(rrule="FREQ=DAILYBAD")

    async def test_rrule_schedule_handles_complex_rrulesets(self):
        s = RRuleSchedule(
            rrule="DTSTART:19970902T090000\n"
            "RRULE:FREQ=YEARLY;COUNT=2;BYDAY=TU\n"
            "RRULE:FREQ=YEARLY;COUNT=1;BYDAY=TH\n"
        )
        dates_from_1900 = await s.get_dates(5, start=datetime(1900, 1, 1, tz="UTC"))
        dates_from_2000 = await s.get_dates(5, start=datetime(2000, 1, 1, tz="UTC"))
        assert len(dates_from_1900) == 3
        assert len(dates_from_2000) == 0

    async def test_rrule_schedule_preserves_and_localizes_rrules(self):
        timezone = "America/New_York"
        s = RRuleSchedule(
            rrule="DTSTART:19970902T090000\n"
            "rrule:FREQ=YEARLY;COUNT=2;BYDAY=TU\n"
            "RRULE:FREQ=YEARLY;COUNT=1;BYDAY=TH\n",
            timezone=timezone,
        )
        expected_tzinfo = dateutil.tz.gettz(timezone)
        converted_rruleset = s.to_rrule()
        assert len(converted_rruleset._rrule) == 2
        assert converted_rruleset._rrule[0]._dtstart.tzinfo == expected_tzinfo

    async def test_rrule_schedule_preserves_and_localizes_exrules(self):
        timezone = "America/New_York"
        s = RRuleSchedule(
            rrule="DTSTART:19970902T090000\n"
            "EXRULE:FREQ=YEARLY;COUNT=2;BYDAY=TU\n"
            "RRULE:FREQ=YEARLY;COUNT=1;BYDAY=TH\n",
            timezone=timezone,
        )
        expected_tzinfo = dateutil.tz.gettz(timezone)
        converted_rruleset = s.to_rrule()
        assert len(converted_rruleset._rrule) == 1
        assert len(converted_rruleset._exrule) == 1
        assert converted_rruleset._exrule[0]._dtstart.tzinfo == expected_tzinfo

    async def test_rrule_schedule_preserves_and_localizes_rdates(self):
        timezone = "America/New_York"
        s = RRuleSchedule(
            rrule="RDATE:20221012T134000Z,20221012T230000Z,20221013T120000Z,20221014T120000Z,20221015T120000Z",
            timezone=timezone,
        )
        expected_tzinfo = dateutil.tz.gettz(timezone)
        converted_rruleset = s.to_rrule()
        assert len(converted_rruleset._rdate) == 5
        assert len(converted_rruleset._exdate) == 0
        assert all(rd.tzinfo == expected_tzinfo for rd in converted_rruleset._rdate)

    async def test_rrule_schedule_preserves_and_localizes_exdates(self):
        timezone = "America/New_York"
        s = RRuleSchedule(
            rrule="EXDATE:20221012T134000Z,20221012T230000Z,20221013T120000Z,20221014T120000Z,20221015T120000Z",
            timezone=timezone,
        )
        expected_tzinfo = dateutil.tz.gettz(timezone)
        converted_rruleset = s.to_rrule()
        assert len(converted_rruleset._rdate) == 0
        assert len(converted_rruleset._exdate) == 5
        assert all(rd.tzinfo == expected_tzinfo for rd in converted_rruleset._exdate)

    async def test_serialization_preserves_rrules_rdates_exrules_exdates(self):
        dt_nyc = datetime(2018, 1, 11, 4, tz="America/New_York")
        last_leap_year = datetime(2020, 2, 29, tz="America/New_York")
        next_leap_year = datetime(2024, 2, 29, tz="America/New_York")
        rrset = rrule.rruleset(cache=True)
        rrset.rrule(rrule.rrule(rrule.HOURLY, count=10, dtstart=dt_nyc))
        rrset.exrule(rrule.rrule(rrule.DAILY, count=10, dtstart=dt_nyc))
        rrset.rdate(last_leap_year)
        rrset.exdate(next_leap_year)

        expected_tzinfo = dateutil.tz.gettz("America/New_York")
        serialized_schedule = RRuleSchedule.from_rrule(rrset)
        roundtrip_rruleset = serialized_schedule.to_rrule()

        # assert string serialization preserves all rruleset components
        assert len(roundtrip_rruleset._rrule) == 1
        assert len(roundtrip_rruleset._exrule) == 1
        assert len(roundtrip_rruleset._rdate) == 1
        assert len(roundtrip_rruleset._exdate) == 1

        # assert rruleset localizes all rruleset components
        assert roundtrip_rruleset._rrule[0]._dtstart.tzinfo == expected_tzinfo
        assert roundtrip_rruleset._exrule[0]._dtstart.tzinfo == expected_tzinfo
        assert roundtrip_rruleset._rdate[0].tzinfo == expected_tzinfo
        assert roundtrip_rruleset._exdate[0].tzinfo == expected_tzinfo

    @pytest.mark.xfail(
        reason="we currently cannot roundtrip RRuleSchedule objects for all timezones"
    )
    async def test_rrule_schedule_handles_rruleset_roundtrips(self):
        s1 = RRuleSchedule(
            rrule="DTSTART:19970902T090000\n"
            "RRULE:FREQ=YEARLY;COUNT=2;BYDAY=TU\n"
            "RRULE:FREQ=YEARLY;COUNT=1;BYDAY=TH\n"
        )
        s2 = RRuleSchedule.from_rrule(s1.to_rrule())
        s1_dates = await s1.get_dates(5, start=datetime(1900, 1, 1, tz="UTC"))
        s2_dates = await s2.get_dates(5, start=datetime(1900, 1, 1, tz="UTC"))
        assert s1_dates == s2_dates

    async def test_rrule_schedule_rejects_rrulesets_with_many_dtstart_timezones(self):
        dt_nyc = datetime(2018, 1, 11, 4, tz="America/New_York")
        dt_chicago = datetime(2018, 1, 11, 3, tz="America/Chicago")
        rrset = rrule.rruleset(cache=True)
        rrset.rrule(rrule.rrule(rrule.HOURLY, count=10, dtstart=dt_nyc))
        rrset.rrule(rrule.rrule(rrule.HOURLY, count=10, dtstart=dt_chicago))

        with pytest.raises(ValueError, match="too many dtstart timezones"):
            s = RRuleSchedule.from_rrule(rrset)

    async def test_rrule_schedule_rejects_rrulesets_with_many_dtstarts(self):
        dt_1 = datetime(2018, 1, 11, 4, tz="America/New_York")
        dt_2 = datetime(2018, 2, 11, 4, tz="America/New_York")
        rrset = rrule.rruleset(cache=True)
        rrset.rrule(rrule.rrule(rrule.HOURLY, count=10, dtstart=dt_1))
        rrset.rrule(rrule.rrule(rrule.HOURLY, count=10, dtstart=dt_2))

        with pytest.raises(ValueError, match="too many dtstarts"):
            s = RRuleSchedule.from_rrule(rrset)

    @pytest.mark.xfail(
        reason="we currently cannot roundtrip RRuleSchedule objects for all timezones"
    )
    async def test_rrule_schedule_handles_rrule_roundtrips(self):
        dt = datetime(2018, 3, 11, 4, tz="Europe/Berlin")
        base_rule = rrule.rrule(rrule.HOURLY, dtstart=dt)
        s1 = RRuleSchedule.from_rrule(base_rule)
        s2 = RRuleSchedule.from_rrule(s1.to_rrule())
        assert s1.timezone == "CET"
        assert s2.timezone == "CET"
        base_dates = list(base_rule.xafter(datetime(1900, 1, 1), count=5))
        s1_dates = await s1.get_dates(
            5, start=pendulum.DateTime(year=1900, month=1, day=1)
        )
        s2_dates = await s2.get_dates(
            5, start=pendulum.DateTime(year=1900, month=1, day=1)
        )
        assert base_dates == s1_dates == s2_dates

    async def test_rrule_from_str(self):
        # create a schedule from an RRule object
        s1 = RRuleSchedule.from_rrule(
            rrule.rrule(
                freq=rrule.DAILY,
                count=5,
                dtstart=pendulum.now("UTC").add(hours=1),
            )
        )
        assert isinstance(s1.rrule, str)
        assert s1.rrule.endswith("RRULE:FREQ=DAILY;COUNT=5")

        # create a schedule from the equivalent RRule string
        s2 = RRuleSchedule(rrule=s1.rrule)

        dts1 = await s1.get_dates(n=10)
        dts2 = await s2.get_dates(n=10)
        assert dts1 == dts2
        assert len(dts1) == 5

    async def test_rrule_validates_rrule_obj(self):
        with pytest.raises(ValueError, match="(Invalid RRule object)"):
            RRuleSchedule.from_rrule("bad rrule")

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
