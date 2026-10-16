import datetime
from itertools import combinations
from zoneinfo import ZoneInfo

import dateutil.rrule
import dateutil.tz
import pytest
import pytz
from pydantic import ValidationError

from prefect.client.schemas.actions import (
    DeploymentFlowRunCreate,
    DeploymentScheduleCreate,
    DeploymentScheduleUpdate,
)
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
    _iana_timezone_name,
    construct_schedule,
)
from prefect.types import DateTime
from prefect.types._datetime import Interval, ItemizedDelta, now


class TestConstructSchedule:
    def test_construct_interval_schedule(self):
        interval = 300  # 5 minutes
        result = construct_schedule(interval=interval)
        assert isinstance(result, IntervalSchedule)
        assert result.interval == datetime.timedelta(seconds=interval)

    def test_construct_cron_schedule(self):
        cron_string = "0 0 * * *"
        result = construct_schedule(cron=cron_string)
        assert isinstance(result, CronSchedule)
        assert result.cron == cron_string

    def test_construct_rrule_schedule(self):
        rrule_string = "FREQ=DAILY;COUNT=2"
        result = construct_schedule(rrule=rrule_string)
        assert isinstance(result, RRuleSchedule)
        assert result.rrule == rrule_string

    @pytest.mark.parametrize(
        "kwargs",
        [
            {**d1, **d2}
            for d1, d2 in combinations(
                [
                    {"interval": 3600},
                    {"cron": "* * * * *"},
                    {"rrule": "FREQ=MINUTELY"},
                ],
                2,
            )
        ],
    )
    def test_multiple_schedules_error(self, kwargs):
        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            construct_schedule(**kwargs)

    def test_anchor_date_without_interval_error(self):
        with pytest.raises(
            ValueError,
            match="An anchor date can only be provided with an interval schedule",
        ):
            construct_schedule(anchor_date="2023-01-01")

    def test_timezone_without_schedule_error(self):
        with pytest.raises(
            ValueError,
            match="A timezone can only be provided with interval, cron, or rrule",
        ):
            construct_schedule(timezone="UTC")

    def test_no_schedule_error(self):
        with pytest.raises(
            ValueError, match="Either interval, cron, or rrule must be provided"
        ):
            construct_schedule()

    def test_timedelta_interval_schedule(self):
        interval = datetime.timedelta(minutes=5)
        result = construct_schedule(interval=interval)
        assert isinstance(result, IntervalSchedule)
        assert result.interval == interval

    def test_calendar_interval_schedule(self):
        interval = ItemizedDelta(months=1)
        result = construct_schedule(interval=interval)
        assert isinstance(result, IntervalSchedule)
        assert result.interval == interval

    def test_datetime_anchor_date(self):
        anchor = now()
        result = construct_schedule(interval=300, anchor_date=anchor)
        assert result == IntervalSchedule(
            interval=datetime.timedelta(seconds=300), anchor_date=anchor
        )

    def test_string_anchor_date(self):
        anchor = "2023-01-01T00:00:00+00:00"
        result = construct_schedule(interval=300, anchor_date=anchor)
        assert result == IntervalSchedule(
            interval=datetime.timedelta(seconds=300),
            anchor_date=DateTime.fromisoformat(anchor),
        )

    @pytest.mark.parametrize(
        "value",
        [
            "not even almost a boolean",
            "{{ to.be.templated }}",
        ],
    )
    def test_invalid_active_value(self, value: str):
        with pytest.raises(
            ValueError, match="active must be able to be parsed as a boolean"
        ):
            schedule = IntervalSchedule(interval=datetime.timedelta(seconds=300))
            DeploymentScheduleCreate(active=value, schedule=schedule)

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("True", True),
            ("False", False),
            ("true", True),
            ("false", False),
            ("TRUE", True),
            ("FALSE", False),
            ("1", True),
            ("0", False),
        ],
    )
    def test_parsable_active_value(self, value: str, expected: bool):
        schedule = IntervalSchedule(interval=datetime.timedelta(seconds=300))
        assert (
            DeploymentScheduleCreate(active=value, schedule=schedule).active == expected
        )


class TestIntervalScheduleSerialization:
    @pytest.mark.parametrize(
        "interval, expected",
        [
            ("P1M", "P1M"),
            ("P1Y2M3DT4H", "P1Y2M3DT4H"),
            ("PT48H", "PT48H"),
            (ItemizedDelta(months=1), "P1M"),
            (datetime.timedelta(days=2), 172800.0),
            (300.0, 300.0),
        ],
    )
    @pytest.mark.parametrize(
        "action_type", [DeploymentScheduleCreate, DeploymentScheduleUpdate]
    )
    def test_interval_survives_client_read_and_write(
        self,
        interval: str | Interval | float,
        expected: str | float,
        action_type: type[DeploymentScheduleCreate] | type[DeploymentScheduleUpdate],
    ):
        schedule = IntervalSchedule.model_validate(
            {
                "interval": interval,
                "anchor_date": "2024-01-31T00:00:00Z",
                "timezone": "UTC",
            }
        )

        payload = action_type(schedule=schedule).model_dump(
            mode="json", exclude_unset=True
        )

        assert payload["schedule"]["interval"] == expected
        assert payload["schedule"]["timezone"] == "UTC"

    @pytest.mark.parametrize(
        "interval",
        [
            datetime.timedelta(0),
            datetime.timedelta(days=-1),
            ItemizedDelta(seconds=0),
            ItemizedDelta(months=-1),
        ],
    )
    def test_interval_must_be_positive(self, interval: Interval):
        with pytest.raises(ValidationError):
            IntervalSchedule(interval=interval)


class TestRRuleNormalizationOnClientWrite:
    """Mirror of `tests/server/schemas/test_actions.py::TestRRuleNormalizationOnWrite`.

    The client SDK constructs `DeploymentScheduleCreate` /
    `DeploymentScheduleUpdate` before sending to the API, so it must
    apply the same `DTSTART` injection. Without this, prefect-client
    users would send bare RRules and the server would silently
    re-normalize them, hiding the contract from anyone reading the
    client code. Keeping client and server in lockstep is the standing
    rule (`src/prefect/client/CLAUDE.md`).
    """

    def test_create_normalizes_bare_minutely(self):
        action = DeploymentScheduleCreate(
            schedule=RRuleSchedule(rrule="FREQ=MINUTELY;INTERVAL=5")
        )
        assert action.schedule.rrule.startswith("DTSTART:")
        assert action.schedule.rrule.endswith("FREQ=MINUTELY;INTERVAL=5")
        # Recent anchor (not the legacy 2020 fallback).
        assert "DTSTART:2020" not in action.schedule.rrule

    def test_create_preserves_anchored_rule(self):
        original = "DTSTART:19970902T090000\nRRULE:FREQ=YEARLY;COUNT=2;BYDAY=TU"
        action = DeploymentScheduleCreate(schedule=RRuleSchedule(rrule=original))
        assert action.schedule.rrule == original

    def test_update_normalizes_bare_secondly(self):
        action = DeploymentScheduleUpdate(schedule=RRuleSchedule(rrule="FREQ=SECONDLY"))
        assert action.schedule.rrule.startswith("DTSTART:")
        assert action.schedule.rrule.endswith("FREQ=SECONDLY")

    def test_rrule_schedule_constructed_directly_is_not_normalized(self):
        # The validator must NOT live on RRuleSchedule itself — only on
        # the action schemas. Otherwise every DB read would re-inject
        # DTSTART and cause phase drift on INTERVAL>1 schedules.
        bare = RRuleSchedule(rrule="FREQ=MINUTELY;INTERVAL=5")
        assert bare.rrule == "FREQ=MINUTELY;INTERVAL=5"


class TestDeploymentFlowRunCreate:
    """Test DeploymentFlowRunCreate schema serialization"""

    def test_datetime_parameter_serialization(self):
        """datetime.datetime should be serialized as ISO string"""
        dt = datetime.datetime(2025, 10, 24, 11, 5, 30, 123456)

        flow_run_create = DeploymentFlowRunCreate(parameters={"dt": dt})
        dumped = flow_run_create.model_dump(mode="json")

        # Should be ISO string, not timestamp float
        assert isinstance(dumped["parameters"]["dt"], str)
        assert dumped["parameters"]["dt"] == "2025-10-24T11:05:30.123456"

    def test_date_parameter_serialization(self):
        """datetime.date should be serialized as ISO string"""
        date = datetime.date(2025, 10, 24)

        flow_run_create = DeploymentFlowRunCreate(parameters={"date": date})
        dumped = flow_run_create.model_dump(mode="json")

        # Should be ISO string, not timestamp float
        assert isinstance(dumped["parameters"]["date"], str)
        assert dumped["parameters"]["date"] == "2025-10-24"

    def test_nested_datetime_parameter_serialization(self):
        """Nested datetime objects should also be serialized"""
        dt = datetime.datetime(2025, 10, 24, 11, 5, 30)
        date = datetime.date(2025, 10, 24)

        flow_run_create = DeploymentFlowRunCreate(
            parameters={"config": {"start_time": dt, "end_date": date, "count": 42}}
        )
        dumped = flow_run_create.model_dump(mode="json")

        # Nested datetime should be ISO string
        assert isinstance(dumped["parameters"]["config"]["start_time"], str)
        assert dumped["parameters"]["config"]["start_time"] == "2025-10-24T11:05:30"
        assert isinstance(dumped["parameters"]["config"]["end_date"], str)
        assert dumped["parameters"]["config"]["end_date"] == "2025-10-24"
        # Other values should be unchanged
        assert dumped["parameters"]["config"]["count"] == 42

    def test_list_datetime_parameter_serialization(self):
        """List of datetime objects should be serialized"""
        dates = [
            datetime.date(2025, 10, 24),
            datetime.date(2025, 10, 25),
        ]

        flow_run_create = DeploymentFlowRunCreate(parameters={"dates": dates})
        dumped = flow_run_create.model_dump(mode="json")

        # List items should be ISO strings
        assert isinstance(dumped["parameters"]["dates"], list)
        assert len(dumped["parameters"]["dates"]) == 2
        assert dumped["parameters"]["dates"][0] == "2025-10-24"
        assert dumped["parameters"]["dates"][1] == "2025-10-25"


class TestRRuleScheduleFromRRule:
    """Verify that from_rrule() preserves IANA timezone names across DST."""

    # dtstart before 2024 spring-forward (Mar 10 02:00 ET)
    _DTSTART_BEFORE_DST = datetime.datetime(2024, 3, 1, 9, 0, 0)

    def _assert_daily_9am_across_dst(
        self, schedule: RRuleSchedule, tz_name: str
    ) -> None:
        """Shared assertions for timezone preservation and DST correctness."""
        assert schedule.timezone == tz_name
        rrule_out = schedule.to_rrule()
        tz = ZoneInfo(tz_name)
        # Generate enough occurrences to span the DST transition
        occurrences = list(rrule_out[:20])
        assert len(occurrences) >= 15
        for dt in occurrences:
            local = dt.astimezone(tz)
            assert local.hour == 9, (
                f"Expected 9 AM {tz_name}, got {local.hour}:00 on {local.date()}"
            )

    @pytest.mark.parametrize(
        "tz_factory,tz_name",
        [
            pytest.param(
                lambda: ZoneInfo("America/New_York"),
                "America/New_York",
                id="zoneinfo",
            ),
            pytest.param(
                lambda: dateutil.tz.gettz("America/New_York"),
                "America/New_York",
                id="dateutil",
            ),
            pytest.param(
                lambda: pytz.timezone("America/New_York"),
                "America/New_York",
                id="pytz",
            ),
        ],
    )
    def test_single_rrule_preserves_iana_timezone(
        self, tz_factory: object, tz_name: str
    ) -> None:
        tz = tz_factory()  # type: ignore[operator]
        rule = dateutil.rrule.rrule(
            freq=dateutil.rrule.DAILY,
            dtstart=self._DTSTART_BEFORE_DST.replace(tzinfo=tz),
        )
        schedule = RRuleSchedule.from_rrule(rule)
        self._assert_daily_9am_across_dst(schedule, tz_name)

    @pytest.mark.parametrize(
        "tz_factory,tz_name",
        [
            pytest.param(
                lambda: ZoneInfo("America/New_York"),
                "America/New_York",
                id="zoneinfo",
            ),
            pytest.param(
                lambda: dateutil.tz.gettz("America/New_York"),
                "America/New_York",
                id="dateutil",
            ),
            pytest.param(
                lambda: pytz.timezone("America/New_York"),
                "America/New_York",
                id="pytz",
            ),
        ],
    )
    def test_rruleset_preserves_iana_timezone(
        self, tz_factory: object, tz_name: str
    ) -> None:
        tz = tz_factory()  # type: ignore[operator]
        rule = dateutil.rrule.rrule(
            freq=dateutil.rrule.DAILY,
            dtstart=self._DTSTART_BEFORE_DST.replace(tzinfo=tz),
        )
        rset = dateutil.rrule.rruleset()
        rset.rrule(rule)
        schedule = RRuleSchedule.from_rrule(rset)
        self._assert_daily_9am_across_dst(schedule, tz_name)

    def test_single_rrule_preserves_pytz_localized_timezone(self) -> None:
        tz = pytz.timezone("America/New_York")
        rule = dateutil.rrule.rrule(
            freq=dateutil.rrule.DAILY,
            dtstart=tz.localize(self._DTSTART_BEFORE_DST),
        )
        schedule = RRuleSchedule.from_rrule(rule)
        self._assert_daily_9am_across_dst(schedule, "America/New_York")

    def test_rruleset_preserves_pytz_localized_timezone(self) -> None:
        tz = pytz.timezone("America/New_York")
        rule = dateutil.rrule.rrule(
            freq=dateutil.rrule.DAILY,
            dtstart=tz.localize(self._DTSTART_BEFORE_DST),
        )
        rset = dateutil.rrule.rruleset()
        rset.rrule(rule)
        schedule = RRuleSchedule.from_rrule(rset)
        self._assert_daily_9am_across_dst(schedule, "America/New_York")

    @pytest.mark.parametrize(
        "tzinfo,expected",
        [
            pytest.param(pytz.timezone("Europe/London"), "Europe/London", id="named"),
            pytest.param(pytz.utc, "UTC", id="utc"),
            pytest.param(pytz.FixedOffset(-300), "UTC", id="fixed-offset"),
        ],
    )
    def test_iana_timezone_name_pytz(
        self, tzinfo: datetime.tzinfo, expected: str
    ) -> None:
        assert _iana_timezone_name(tzinfo) == expected

    def test_single_rrule_preserves_name_bearing_tzinfo(self) -> None:
        """Regression: tzinfo with a public .name attribute (e.g. pendulum)."""

        class _NameTZ(datetime.tzinfo):
            """Minimal tzinfo stub that exposes .name like pendulum zones."""

            name = "America/New_York"

            def utcoffset(self, dt: datetime.datetime | None) -> datetime.timedelta:
                return datetime.timedelta(hours=-5)

            def tzname(self, dt: datetime.datetime | None) -> str:
                return "EST"

            def dst(self, dt: datetime.datetime | None) -> datetime.timedelta:
                return datetime.timedelta(0)

        rule = dateutil.rrule.rrule(
            freq=dateutil.rrule.DAILY,
            dtstart=self._DTSTART_BEFORE_DST.replace(tzinfo=_NameTZ()),
        )
        schedule = RRuleSchedule.from_rrule(rule)
        assert schedule.timezone == "America/New_York"
