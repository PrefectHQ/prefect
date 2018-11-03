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
        interval=datetime.timedelta(hours=1), start_date=datetime.datetime(2020, 1, 1)
    )


@pytest.fixture()
def cron_schedule():
    return schedules.CronSchedule(cron="0 0 * * *")


@pytest.fixture()
def date_schedule():
    return schedules.DateSchedule(
        dates=[datetime.datetime(2020, 1, 1), datetime.datetime(2021, 1, 1)]
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


def test_no_schedule_serialization():
    schedule = schedules.NoSchedule()
    serialized = schemas.ScheduleSchema().dump(schedule)
    assert serialized == {"type": "NoSchedule", "__version__": __version__}


def test_no_schedule_deserialization():
    schedule = schedules.NoSchedule()
    serialized = schemas.ScheduleSchema().dump(schedule)
    deserialized = schemas.ScheduleSchema().load(serialized)
    assert isinstance(deserialized, schedules.NoSchedule)


def test_serialize_no_schedule():
    schema = schemas.NoScheduleSchema()
    assert schema.dump(schedules.NoSchedule()) == {"__version__": __version__}


def test_serialize_cron_schedule(cron_schedule):
    schema = schemas.CronScheduleSchema()
    assert schema.dump(cron_schedule) == {
        "cron": cron_schedule.cron,
        "__version__": __version__,
    }


def test_serialize_interval_schedule(interval_schedule):
    schema = schemas.IntervalScheduleSchema()
    assert schema.dump(interval_schedule) == {
        "start_date": interval_schedule.start_date.isoformat() + "+00:00",
        "interval": interval_schedule.interval.total_seconds(),
        "__version__": __version__,
    }


def test_serialize_date_schedule(date_schedule):
    schema = schemas.DateScheduleSchema()
    assert schema.dump(date_schedule) == {
        "dates": [d.isoformat() + "+00:00" for d in date_schedule.dates],
        "__version__": __version__,
    }
