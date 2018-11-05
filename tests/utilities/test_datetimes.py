import datetime
import pendulum
import prefect.utilities.datetimes as dts


def test_ensure_tz_aware():
    dt = datetime.datetime(2018, 1, 1)
    converted = dts.ensure_tz_aware(dt)

    assert not dt.tzinfo
    assert converted.tzinfo is pendulum.timezone("utc")
    assert (converted.year, converted.month, converted.day) == (2018, 1, 1)


def test_ensure_tz_aware_doesnt_change_tz():
    dt = datetime.datetime(2018, 1, 1, tzinfo=pendulum.timezone("EST"))
    converted = dts.ensure_tz_aware(dt)

    assert converted.tzinfo is pendulum.timezone("EST")
    assert converted is dt


def test_ensure_tz_aware_with_non_datetimes():
    assert dts.ensure_tz_aware(None) is None
    td = datetime.timedelta(seconds=3)
    assert dts.ensure_tz_aware(td) is td
