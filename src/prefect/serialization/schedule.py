import typing
from typing import Any

from dateutil import rrule
from marshmallow import fields, post_dump, post_load
from marshmallow.fields import Field

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


class _WeekdayField(Field):
    """
    Marshmallow serializer for rrule weekday objects.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        if value is not None:
            if isinstance(value, int):
                return {"weekday": value, "n": None}
            elif isinstance(value, rrule.weekday):
                return {"weekday": value.weekday, "n": value.n}

    def _deserialize(self, value, attr, data, **kwargs):
        if value is not None:
            return rrule.weekday(value["weekday"], value.get("n"))


class _RRuleField(fields.List):
    """
    Marshmallow serializer for special rrule members.

    The rrule constructor manipulates many of its args and overwrites them so the instance value
    can be wildly different than what was originally passed in.
    However, when it does this it also stores the original values in an '_original_rule' dict field.
    So we pull the values from that dict. If it's not there then we know the attribute was not
    actually passed in and we should use None.
    """

    def __init__(self, cls_or_instance: typing.Union[Field, type] = fields.Integer):
        super().__init__(cls_or_instance, allow_none=True)

    def _serialize(
        self, value, attr, obj, **kwargs
    ) -> typing.Optional[typing.List[typing.Any]]:
        if value is not None:
            # This turns e.g '_bymonth' into 'bymonth'
            attr_no_underscore = attr[1:]
            # Note we use get() here not [] b/c we want the value to be None if it doesn't exist
            val = obj._original_rule.get(attr_no_underscore)
            return super()._serialize(val, attr, obj, **kwargs)


class RRuleSchema(ObjectSchema):
    class Meta:
        object_class = rrule.rrule

    _freq = fields.Integer(required=True)
    _dtstart = DateTimeTZ(allow_none=True)
    _interval = fields.Integer(allow_none=True)
    _wkst = fields.Integer(allow_none=True)
    _count = fields.Integer(allow_none=True)
    _until = DateTimeTZ(allow_none=True)

    _bysetpos = _RRuleField()
    _bymonth = _RRuleField()
    _bymonthday = _RRuleField()
    _byyearday = _RRuleField()
    _byeaster = _RRuleField()
    _byweekday = _RRuleField(_WeekdayField)
    _byweekno = _RRuleField()
    _byhour = _RRuleField()
    _byminute = _RRuleField()
    _bysecond = _RRuleField()

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> rrule.rrule:
        data["freq"] = data.pop("_freq")
        data["dtstart"] = data.pop("_dtstart", None)
        data["interval"] = data.pop("_interval", None)
        data["wkst"] = data.pop("_wkst", None)
        data["count"] = data.pop("_count", None)
        data["until"] = data.pop("_until", None)

        data["bysetpos"] = data.pop("_bysetpos", None)
        data["bymonth"] = data.pop("_bymonth", None)
        data["bymonthday"] = data.pop("_bymonthday", None)
        data["byyearday"] = data.pop("_byyearday", None)
        data["byeaster"] = data.pop("_byeaster", None)
        data["byweekno"] = data.pop("_byweekno", None)
        data["byweekday"] = data.pop("_byweekday", None)
        data["byhour"] = data.pop("_byhour", None)
        data["byminute"] = data.pop("_byminute", None)
        data["bysecond"] = data.pop("_bysecond", None)

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
