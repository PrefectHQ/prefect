"""
This file contains compat code to handle pendulum.DateTime objects during jsonschema 
generation and validation. 
"""

import typing as t

import pendulum
from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from typing_extensions import Annotated


class _PendulumAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: t.Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        def validate_from_str(value: str) -> pendulum.DateTime:
            return pendulum.parse(value)

        def to_str(value: pendulum.DateTime) -> str:
            return value.isoformat()

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.datetime_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [
                    # check if it's an instance first before doing any further work
                    core_schema.is_instance_schema(pendulum.DateTime),
                    from_str_schema,
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(to_str),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.datetime_schema())


PydanticPendulumType = Annotated[pendulum.DateTime, _PendulumAnnotation]
