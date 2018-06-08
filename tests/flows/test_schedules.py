import json
import datetime
from prefect import schedules


def test_date_schedule():

    dates = ["2017-01-01", "2018-01-01", "1/1/2019", "3/30/2020 13:03:12"]
    after = "2018-06-30"
    expected_dates = [
        datetime.datetime(2019, 1, 1),
        datetime.datetime(2020, 3, 30, 13, 3, 12),
    ]

    s = schedules.DateSchedule(dates)
    assert expected_dates == s.next_n(2, on_or_after=after)


def test_cron_schedule():
    # 22:00 every weekday
    cron = "0 22 * * 1-5"
    # Friday Jan 6
    after = "2017-01-06"
    expected_dates = [
        datetime.datetime(2017, 1, 6, 22),
        datetime.datetime(2017, 1, 9, 22),
    ]

    s = schedules.CronSchedule(cron)
    assert expected_dates == s.next_n(2, on_or_after=after)


def test_interval_schedule():
    after = "2017-09-25"
    expected_dates = [datetime.datetime(2017, 9, 28), datetime.datetime(2017, 10, 8)]
    s = schedules.IntervalSchedule(
        start_date="2017-01-01", interval=datetime.timedelta(days=10)
    )
    assert expected_dates == s.next_n(2, on_or_after=after)


def test_serialize_and_deserialize():
    s1 = schedules.NoSchedule()
    s2 = json.loads(s1.serialize())
    assert s1.next_n(2) == s2.next_n(2)

    s1 = schedules.DateSchedule(dates=["20{}-01-01".format(i) for i in range(20, 30)])
    s2 = json.loads(s1.serialize())
    assert s1.next_n(2) == s2.next_n(2)

    s1 = schedules.CronSchedule("0 22 * * 1-5")
    s2 = json.loads(s1.serialize())
    assert s1.next_n(2) == s2.next_n(2)

    s1 = schedules.IntervalSchedule(
        start_date="2017-01-01", interval=datetime.timedelta(days=20)
    )
    s2 = json.loads(s1.serialize())
    assert s1.next_n(2) == s2.next_n(2)
