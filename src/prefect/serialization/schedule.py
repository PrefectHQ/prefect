from typing import Any

from dateutil import rrule
from marshmallow import fields, post_dump, post_load

import prefect
from prefect.utilities.serialization import (
    DateTimeTZ,
    JSONCompatible,
    ObjectSchema,
    OneOfSchema,
    StatefulFunctionReference,
)

FILTERS = [
    prefect.schedules.filters.on_datetime,
    prefect.schedules.filters.on_date,
    prefect.schedules.filters.at_time,
    prefect.schedules.filters.between_datetimes,
    prefect.schedules.filters.between_dates,
    prefect.schedules.filters.between_times,
    prefect.schedules.filters.is_weekday,
    prefect.schedules.filters.is_weekend,
    prefect.schedules.filters.is_month_end,
    prefect.schedules.filters.is_day_of_week,
    prefect.schedules.filters.is_month_start,
]

ADJUSTMENTS = [
    prefect.schedules.adjustments.add,
    prefect.schedules.adjustments.next_weekday,
]


class IntervalClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.IntervalClock

    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    interval = fields.TimeDelta(precision="microseconds", required=True)
    parameter_defaults = fields.Dict(
        key=fields.Str(), values=JSONCompatible(), allow_none=True
    )
    labels = fields.List(fields.Str(), allow_none=True)

    @post_dump
    def _interval_validation(self, data: dict, **kwargs: Any) -> dict:
        """
        Ensures interval is at least one minute in length
        """
        if data["interval"] / 1e6 < 60:
            raise ValueError(
                "Interval can not be less than one minute when deploying to Prefect Cloud."
            )
        return data

    @post_load
    def create_object(self, data: dict, **kwargs: Any):
        if data["interval"].total_seconds() < 60:
            raise ValueError(
                "Interval can not be less than one minute when deploying to Prefect Cloud."
            )
        base_obj = super().create_object(data)
        return base_obj


class CronClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.CronClock

    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    cron = fields.String(required=True)
    parameter_defaults = fields.Dict(
        key=fields.Str(), values=JSONCompatible(), allow_none=True
    )
    labels = fields.List(fields.Str(), allow_none=True)
    day_or = fields.Boolean(allow_none=True)


class DatesClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.DatesClock

    dates = fields.List(DateTimeTZ(), required=True)
    parameter_defaults = fields.Dict(
        key=fields.Str(), values=JSONCompatible(), allow_none=True
    )
    labels = fields.List(fields.Str(), allow_none=True)


class RRuleSchema(ObjectSchema):
    class Meta:
        object_class = rrule.rrule

    _freq = fields.Integer(required=True)
    _dtstart = DateTimeTZ(allow_none=True)
    _interval = fields.Integer(allow_none=True)
    _wkst = fields.Integer(allow_none=True)
    _count = fields.Integer(allow_none=True)
    _until = DateTimeTZ(allow_none=True)

    _bysetpos = fields.List(fields.Integer, allow_none=True)
    _bymonth = fields.List(fields.Integer, allow_none=True)
    _bymonthday = fields.List(fields.Integer, allow_none=True)
    _byyearday = fields.List(fields.Integer, allow_none=True)
    _byeaster = fields.List(fields.Integer, allow_none=True)
    _byweekno = fields.List(fields.Integer, allow_none=True)
    # _byweekno = ???
    _byhour = fields.List(fields.Integer, allow_none=True)
    _byminute = fields.List(fields.Integer, allow_none=True)
    _bysecond = fields.List(fields.Integer, allow_none=True)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> rrule.rrule:
        data["freq"] = data.pop("_freq")
        data["dtstart"] = data.pop("_dtstart")
        data["interval"] = data.pop("_interval")
        data["wkst"] = data.pop("_wkst")
        data["count"] = data.pop("_count")
        data["until"] = data.pop("_until")

        data["bysetpos"] = data.pop("_bysetpos")
        data["bymonth"] = data.pop("_bymonth")
        data["bymonthday"] = data.pop("_bymonthday")
        data["byyearday"] = data.pop("_byyearday")
        data["byeaster"] = data.pop("_byeaster")
        data["byweekno"] = data.pop("_byweekno")
        data["byhour"] = data.pop("_byhour")
        data["byminute"] = data.pop("_byminute")
        data["bysecond"] = data.pop("_bysecond")
        base_obj = super().create_object(data, **kwargs)
        return base_obj


class RRuleSetSchema(ObjectSchema):
    class Meta:
        object_class = rrule.rruleset

    _rrule = fields.List(fields.Nested(RRuleSchema))
    _rdate = fields.List(DateTimeTZ)
    _exrule = fields.List(fields.Nested(RRuleSchema))
    _exdate = fields.List(DateTimeTZ)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> rrule.rruleset:
        rrs = rrule.rruleset()
        for rr in data["_rrule"]:
            rrs.rrule(rr)
        for dt in data["_rdate"]:
            rrs.rdate(dt)
        for exrr in data["_exrule"]:
            rrs.exrule(exrr)
        for exdt in data["_exdate"]:
            rrs.exdate(exdt)
        return rrs


class RRuleBaseSchema(OneOfSchema):
    # map class name to schema
    type_schemas = {
        "rrule": RRuleSchema,
        "rruleset": RRuleSetSchema,
    }


class RRuleClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.RRuleClock

    rrule_obj = fields.Nested(RRuleBaseSchema, required=True)
    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    parameter_defaults = fields.Dict(
        key=fields.Str(), values=JSONCompatible(), allow_none=True
    )
    labels = fields.List(fields.Str(), allow_none=True)


class ClockSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "IntervalClock": IntervalClockSchema,
        "CronClock": CronClockSchema,
        "DatesClock": DatesClockSchema,
        "RRuleClock": RRuleClockSchema,
    }


class ScheduleSchema(ObjectSchema):
    """
    The serialization schema for Schedule types
    """

    class Meta:
        object_class = prefect.schedules.Schedule

    clocks = fields.Nested(ClockSchema, required=True, many=True)
    filters = fields.List(
        StatefulFunctionReference(
            valid_functions=FILTERS, reject_invalid=True, allow_none=True
        )
    )
    or_filters = fields.List(
        StatefulFunctionReference(
            valid_functions=FILTERS, reject_invalid=True, allow_none=True
        )
    )
    not_filters = fields.List(
        StatefulFunctionReference(
            valid_functions=FILTERS, reject_invalid=True, allow_none=True
        )
    )
    adjustments = fields.List(
        StatefulFunctionReference(
            valid_functions=ADJUSTMENTS, reject_invalid=True, allow_none=True
        )
    )
