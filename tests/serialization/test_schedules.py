import pendulum
import marshmallow
import datetime
import prefect
import pytest
import marshmallow
from prefect import schedules, __version__
from prefect.serialization import schedule as schemas


all_schedule_classes = set(
    cls
    for cls in schedules.__dict__.values()
    if isinstance(cls, type)
    and issubclass(cls, schedules.Schedule)
    and cls is not schedules.Schedule
)


@pytest.fixture()
def interval_schedule():
    return schedules.IntervalSchedule(
        interval=datetime.timedelta(hours=1),
        start_date=datetime.datetime(2020, 1, 1),
        end_date=datetime.datetime(2020, 5, 1),
    )


@pytest.fixture()
def cron_schedule():
    return schedules.CronSchedule(
        cron="0 0 * * *",
        start_date=datetime.datetime(2020, 1, 1),
        end_date=datetime.datetime(2020, 5, 1),
    )


def test_all_schedules_have_serialization_schemas():
    """
    Tests that all Schedule subclasses in prefect.schedules have corresponding schemas
    in prefect.serialization.schedule
    """

    assert set(s.__name__ for s in all_schedule_classes) == set(
        schemas.ScheduleSchema.type_schemas.keys()
    ), "Not every schedule class has an associated schema"


def test_all_schedules_have_deserialization_schemas():
    """
    Tests that all Schedule subclasses in prefect.schedules have corresponding schemas
    in prefect.serialization.schedule with the correct deserialization class
    """

    assert all_schedule_classes == set(
        s.Meta.object_class for s in schemas.ScheduleSchema.type_schemas.values()
    ), "Not every schedule class has an associated schema"


def test_deserialize_without_type_fails():
    with pytest.raises(marshmallow.exceptions.ValidationError):
        schemas.ScheduleSchema().load({})


def test_deserialize_bad_type_fails():
    with pytest.raises(marshmallow.exceptions.ValidationError):
        schemas.ScheduleSchema().load({"type": "BadSchedule"})


def test_serialize_cron_schedule(cron_schedule):
    schema = schemas.CronScheduleSchema()
    assert schema.dump(cron_schedule) == {
        "cron": cron_schedule.cron,
        "__version__": __version__,
        "start_date": cron_schedule.start_date.isoformat(),
        "end_date": cron_schedule.end_date.isoformat(),
    }


def test_serialize_interval_schedule(interval_schedule):
    schema = schemas.IntervalScheduleSchema()
    assert schema.dump(interval_schedule) == {
        "start_date": interval_schedule.start_date.isoformat(),
        "end_date": interval_schedule.end_date.isoformat(),
        "interval": int(interval_schedule.interval.total_seconds()) * 1000000,
        "__version__": __version__,
    }


def test_serialize_interval_at_microsecond_resolution():
    schedule = schedules.IntervalSchedule(
        start_date=pendulum.now("utc"),
        interval=datetime.timedelta(minutes=1, microseconds=1),
    )
    schema = schemas.IntervalScheduleSchema()
    serialized = schema.dump(schedule)
    assert serialized["interval"] == 60000001


def test_serialize_interval_at_annual_resolution():
    schedule = schedules.IntervalSchedule(
        start_date=pendulum.now("utc"),
        interval=datetime.timedelta(days=365, microseconds=1),
    )
    schema = schemas.IntervalScheduleSchema()
    serialized = schema.dump(schedule)
    assert serialized["interval"] == 31536000000001


def test_deserialize_schedule_with_overridden_interval():
    schedule = schedules.IntervalSchedule(
        start_date=pendulum.now("utc"), interval=datetime.timedelta(minutes=1)
    )
    schedule.interval = datetime.timedelta(microseconds=1)
    schema = schemas.IntervalScheduleSchema()
    serialized = schema.dump(schedule)
    assert serialized["interval"] == 1

    with pytest.raises(ValueError) as exc:
        schema.load(serialized)
    assert "Interval must be more than one minute." in str(exc.value)
