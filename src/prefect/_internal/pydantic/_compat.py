import typing

from typing_extensions import Self

from ._base_model import BaseModel as PydanticBaseModel
from ._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2
from ._types import DEFAULT_REF_TEMPLATE
from .utilities.model_construct import model_construct
from .utilities.model_copy import model_copy
from .utilities.model_dump import model_dump
from .utilities.model_dump_json import model_dump_json
from .utilities.model_json_schema import model_json_schema
from .utilities.model_validate import model_validate
from .utilities.model_validate_json import model_validate_json
from .utilities.type_adapter import TypeAdapter, validate_python

if typing.TYPE_CHECKING:
    from ._types import IncEx, JsonSchemaMode

if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    # In this case, there's no functionality to add, so we just alias the Pydantic v2 BaseModel
    class BaseModel(PydanticBaseModel):  # type: ignore
        pass

else:
    # In this case, we're working with a Pydantic v1 model, so we need to add Pydantic v2 functionality
    # TODO: Find a smarter way of attaching these methods so that they don't need to be redefined
    class BaseModel(PydanticBaseModel):
        def model_dump(
            self: "BaseModel",
            *,
            mode: str = "python",
            include: "IncEx" = None,
            exclude: "IncEx" = None,
            by_alias: bool = False,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool = True,
        ) -> typing.Dict[str, typing.Any]:
            return model_dump(
                self,
                mode=mode,
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                round_trip=round_trip,
                warnings=warnings,
            )

        def model_dump_json(
            self,
            *,
            indent: typing.Optional[int] = None,
            include: typing.Optional["IncEx"] = None,
            exclude: typing.Optional["IncEx"] = None,
            by_alias: bool = False,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool = True,
        ) -> str:
            return model_dump_json(
                model_instance=self,
                indent=indent,
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                round_trip=round_trip,
                warnings=warnings,
            )

        def model_copy(
            self: "Self",
            *,
            update: typing.Optional[typing.Dict[str, typing.Any]] = None,
            deep: bool = False,
        ) -> "Self":
            return model_copy(self, update=update, deep=deep)

        @classmethod
        def model_json_schema(
            cls,
            by_alias: bool = True,
            ref_template: str = DEFAULT_REF_TEMPLATE,
            schema_generator: typing.Any = None,
            mode: "JsonSchemaMode" = "validation",
        ) -> typing.Dict[str, typing.Any]:
            return model_json_schema(
                cls,
                by_alias=by_alias,
                ref_template=ref_template,
                schema_generator=schema_generator,
                mode=mode,
            )

        @classmethod
        def model_validate(
            cls: typing.Type["Self"],
            obj: typing.Any,
            *,
            strict: typing.Optional[bool] = False,
            from_attributes: typing.Optional[bool] = False,
            context: typing.Optional[typing.Dict[str, typing.Any]] = None,
        ) -> "Self":
            return model_validate(
                cls,
                obj,
                strict=strict,
                from_attributes=from_attributes,
                context=context,
            )

        @classmethod
        def model_validate_json(
            cls: typing.Type["Self"],
            json_data: typing.Union[str, bytes, bytearray],
            *,
            strict: typing.Optional[bool] = False,
            context: typing.Optional[typing.Dict[str, typing.Any]] = None,
        ) -> "Self":
            return model_validate_json(
                cls,
                json_data,
                strict=strict,
                context=context,
            )


__all__ = [
    "model_construct",
    "model_copy",
    "model_dump",
    "model_dump_json",
    "model_json_schema",
    "model_validate",
    "model_validate_json",
    "TypeAdapter",
    "validate_python",
    "BaseModel",
]
