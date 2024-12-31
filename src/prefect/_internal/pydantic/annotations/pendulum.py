"""
This file contains compat code to handle pendulum.DateTime objects during jsonschema
generation and validation.
"""

from typing import Annotated, Any, Union

import pendulum
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


class _PendulumDateTimeAnnotation:
    _pendulum_type: type[
        Union[pendulum.DateTime, pendulum.Date, pendulum.Time, pendulum.Duration]
    ] = pendulum.DateTime

    _pendulum_types_to_schemas = {
        pendulum.DateTime: core_schema.datetime_schema(),
        pendulum.Date: core_schema.date_schema(),
        pendulum.Time: core_schema.time_schema(),
        pendulum.Duration: core_schema.timedelta_schema(),
    }

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        def validate_from_str(
            value: str,
        ) -> Union[pendulum.DateTime, pendulum.Date, pendulum.Time, pendulum.Duration]:
            return pendulum.parse(value)

        def to_str(
            value: Union[pendulum.DateTime, pendulum.Date, pendulum.Time],
        ) -> str:
            return value.isoformat()

        from_str_schema = core_schema.chain_schema(
            [
                cls._pendulum_types_to_schemas[cls._pendulum_type],
                core_schema.no_info_plain_validator_function(validate_from_str),
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [
                    # check if it's an instance first before doing any further work
                    core_schema.is_instance_schema(cls._pendulum_type),
                    from_str_schema,
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(to_str),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(cls._pendulum_types_to_schemas[cls._pendulum_type])


class _PendulumDateAnnotation(_PendulumDateTimeAnnotation):
    _pendulum_type = pendulum.Date


class _PendulumDurationAnnotation(_PendulumDateTimeAnnotation):
    _pendulum_type = pendulum.Duration


PydanticPendulumDateTimeType = Annotated[pendulum.DateTime, _PendulumDateTimeAnnotation]
PydanticPendulumDateType = Annotated[pendulum.Date, _PendulumDateAnnotation]
PydanticPendulumDurationType = Annotated[pendulum.Duration, _PendulumDurationAnnotation]
