from typing import Any, Dict, Generic, Literal, Optional, Set, Type, TypeVar, Union

from typing_extensions import Self, TypeAlias

from prefect._internal.pydantic._flags import (
    HAS_PYDANTIC_V2,
    USE_PYDANTIC_V2,
)
from prefect.logging.loggers import get_logger

from ._base_model import BaseModel as PydanticBaseModel

IncEx: TypeAlias = "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"
logger = get_logger("prefect._internal.pydantic")

T = TypeVar("T")
B = TypeVar("B", bound=PydanticBaseModel)

if HAS_PYDANTIC_V2:
    from pydantic import (
        TypeAdapter as BaseTypeAdapter,
    )
    from pydantic import (
        parse_obj_as,  # type: ignore
    )
    from pydantic.json_schema import GenerateJsonSchema  # type: ignore
else:
    from pydantic import parse_obj_as  # type: ignore

if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    TypeAdapter = BaseTypeAdapter  # type: ignore

else:

    class TypeAdapter(Generic[T]):
        def __init__(self, type_: Union[T, Type[T]]) -> None:
            self.type_ = type_

        def validate_python(
            self,
            __object: Any,
            /,
            *,
            strict: Optional[bool] = None,
            from_attributes: Optional[bool] = None,
            context: Optional[Dict[str, Any]] = None,
        ) -> Any:
            return parse_obj_as(self.type_, __object)  # type: ignore


# BaseModel methods and definitions


def model_copy(
    model_instance: PydanticBaseModel,
    *,
    update: Optional[Dict[str, Any]] = None,
    deep: bool = False,
) -> PydanticBaseModel:
    """Usage docs: https://docs.pydantic.dev/2.7/concepts/serialization/#model_copy

    Returns a copy of the model.

    Args:
        update: Values to change/add in the new model. Note: the data is not validated
            before creating the new model. You should trust this data.
        deep: Set to `True` to make a deep copy of the model.

    Returns:
        New model instance.
    """
    if not hasattr(model_instance, "copy") and not hasattr(
        model_instance, "model_copy"
    ):
        raise TypeError("Expected a Pydantic model instance")

    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return model_instance.model_copy(update=update, deep=deep)

    return model_instance.copy(update=update, deep=deep)  # type: ignore


def model_dump_json(
    model_instance: PydanticBaseModel,
    *,
    indent: Optional[int] = None,
    include: IncEx = None,
    exclude: IncEx = None,
    by_alias: bool = False,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    round_trip: bool = False,
    warnings: bool = True,
) -> str:
    """
    Generate a JSON representation of the model, optionally specifying which fields to include or exclude.

    Args:
        indent: If provided, the number of spaces to indent the JSON output.
        include: A list of fields to include in the output.
        exclude: A list of fields to exclude from the output.
        by_alias: Whether to use the field's alias in the dictionary key if defined.
        exclude_unset: Whether to exclude fields that have not been explicitly set.
        exclude_defaults: Whether to exclude fields that are set to their default value.
        exclude_none: Whether to exclude fields that have a value of `None`.
        round_trip: If True, dumped values should be valid as input for non-idempotent types such as Json[T].
        warnings: Whether to log warnings when invalid fields are encountered.

    Returns:
        A JSON representation of the model.
    """
    if not hasattr(model_instance, "json") and not hasattr(
        model_instance, "model_dump_json"
    ):
        raise TypeError("Expected a Pydantic model instance")

    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return model_instance.model_dump_json(
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

    return model_instance.json(  # type: ignore
        include=include,
        exclude=exclude,
        by_alias=by_alias,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
    )


def model_dump(
    model_instance: PydanticBaseModel,
    *,
    mode: Union[Literal["json", "python"], str] = "python",
    include: IncEx = None,
    exclude: IncEx = None,
    by_alias: bool = False,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    round_trip: bool = False,
    warnings: bool = True,
) -> Dict[str, Any]:
    """
    Generate a dictionary representation of the model, optionally specifying which fields to include or exclude.

    Args:
        mode: The mode in which `to_python` should run.
            If mode is 'json', the output will only contain JSON serializable types.
            If mode is 'python', the output may contain non-JSON-serializable Python objects.
        include: A list of fields to include in the output.
        exclude: A list of fields to exclude from the output.
        by_alias: Whether to use the field's alias in the dictionary key if defined.
        exclude_unset: Whether to exclude fields that have not been explicitly set.
        exclude_defaults: Whether to exclude fields that are set to their default value.
        exclude_none: Whether to exclude fields that have a value of `None`.
        round_trip: If True, dumped values should be valid as input for non-idempotent types such as Json[T].
        warnings: Whether to log warnings when invalid fields are encountered.

    Returns:
        A dictionary representation of the model.
    """
    if not hasattr(model_instance, "dict") and not hasattr(
        model_instance, "model_dump"
    ):
        raise TypeError("Expected a Pydantic model instance")

    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return model_instance.model_dump(
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

    return getattr(model_instance, "dict")(
        include=include,
        exclude=exclude,
        by_alias=by_alias,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
    )


DEFAULT_REF_TEMPLATE = "#/$defs/{model}"
JsonSchemaMode = Literal["validation", "serialization"]


def model_json_schema(
    model: Type[PydanticBaseModel],
    *,
    by_alias: bool = True,
    ref_template: str = DEFAULT_REF_TEMPLATE,
    schema_generator: Any = None,
    mode: JsonSchemaMode = "validation",
) -> Dict[str, Any]:
    """
    Generates a JSON schema for a model class.

    Parameters
    ----------
    by_alias : bool, optional
        Whether to use attribute aliases or not, by default True
    ref_template : str, optional
        The reference template, by default DEFAULT_REF_TEMPLATE
    schema_generator : type[GenerateEmptySchemaForUserClasses], optional
        To override the logic used to generate the JSON schema, as a subclass of GenerateEmptySchemaForUserClasses with your desired modifications, by default GenerateEmptySchemaForUserClasses
    mode : JsonSchemaMode, optional
        The mode in which to generate the schema, by default 'validation'

    Returns
    -------
    dict[str, Any]
        The JSON schema for the given model class.
    """
    if not hasattr(model, "schema") and not hasattr(model, "model_json_schema"):
        raise TypeError("Expected a Pydantic model type")

    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        schema_generator = GenerateJsonSchema  # type: ignore
        return model.model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
        )

    return model.schema(  # type: ignore
        by_alias=by_alias,
        ref_template=ref_template,
    )


def model_validate(
    model: Type[B],
    obj: Any,
    *,
    strict: Optional[bool] = False,
    from_attributes: Optional[bool] = False,
    context: Optional[Dict[str, Any]] = None,
) -> B:
    """Validate a pydantic model instance.

    Args:
        obj: The object to validate.
        strict: Whether to enforce types strictly.
        from_attributes: Whether to extract data from object attributes.
        context: Additional context to pass to the validator.

    Raises:
        ValidationError: If the object could not be validated.

    Returns:
        The validated model instance.
    """
    if not hasattr(model, "parse_obj") and not hasattr(model, "model_validate"):
        raise TypeError("Expected a Pydantic model type")

    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return model.model_validate(
            obj=obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )

    return getattr(model, "parse_obj")(obj)


def model_validate_json(
    model: Type[B],
    json_data: Union[str, bytes, bytearray],
    *,
    strict: Optional[bool] = False,
    context: Optional[Dict[str, Any]] = None,
) -> B:
    """Validate the given JSON data against the Pydantic model.

    Args:
        json_data: The JSON data to validate.
        strict: Whether to enforce types strictly.
        context: Extra variables to pass to the validator.

    Returns:
        The validated Pydantic model.

    Raises:
        ValueError: If `json_data` is not a JSON string.
    """
    if not hasattr(model, "parse_raw") and not hasattr(model, "model_validate_json"):
        raise TypeError("Expected a Pydantic model type")

    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return model.model_validate_json(
            json_data=json_data,
            strict=strict,
            context=context,
        )

    return getattr(model, "parse_raw")(json_data)


if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    # In this case, there's no functionality to add, so we just alias the Pydantic v2 BaseModel
    class BaseModel(PydanticBaseModel):  # type: ignore
        pass

else:
    # In this case, we're working with a Pydantic v1 model, so we need to add Pydantic v2 functionality
    class BaseModel(PydanticBaseModel):
        def model_dump(
            self: "BaseModel",
            *,
            mode: str = "python",
            include: IncEx = None,
            exclude: IncEx = None,
            by_alias: bool = False,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool = True,
        ) -> Dict[str, Any]:
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
            indent: Optional[int] = None,
            include: Optional[IncEx] = None,
            exclude: Optional[IncEx] = None,
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
            update: Optional[Dict[str, Any]] = None,
            deep: bool = False,
        ) -> "Self":
            return super().model_copy(update=update, deep=deep)

        @classmethod
        def model_json_schema(
            cls,
            by_alias: bool = True,
            ref_template: str = DEFAULT_REF_TEMPLATE,
            schema_generator: Any = None,
            mode: JsonSchemaMode = "validation",
        ) -> Dict[str, Any]:
            return model_json_schema(
                cls,
                by_alias=by_alias,
                ref_template=ref_template,
                schema_generator=schema_generator,
                mode=mode,
            )

        @classmethod
        def model_validate(
            cls: Type["Self"],
            obj: Any,
            *,
            strict: Optional[bool] = False,
            from_attributes: Optional[bool] = False,
            context: Optional[Dict[str, Any]] = None,
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
            cls: Type["Self"],
            json_data: Union[str, bytes, bytearray],
            *,
            strict: Optional[bool] = False,
            context: Optional[Dict[str, Any]] = None,
        ) -> "Self":
            return model_validate_json(
                cls,
                json_data,
                strict=strict,
                context=context,
            )


# TypeAdapter methods and definitions


def validate_python(
    type_: Union[T, Type[T]],
    __object: Any,
    /,
    *,
    strict: Optional[bool] = None,
    from_attributes: Optional[bool] = None,
    context: Optional[Dict[str, Any]] = None,
) -> T:
    """Validate a Python object against the model.

    Args:
        type_: The type to validate against.
        __object: The Python object to validate against the model.
        strict: Whether to strictly check types.
        from_attributes: Whether to extract data from object attributes.
        context: Additional context to pass to the validator.

    !!! note
        When using `TypeAdapter` with a Pydantic `dataclass`, the use of the `from_attributes`
        argument is not supported.

    Returns:
        The validated object.
    """
    return TypeAdapter(type_).validate_python(__object)
