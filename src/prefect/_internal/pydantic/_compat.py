import os
from typing import Any, Dict, Optional, Set, Type, Union

from typing_extensions import Literal, TypeAlias

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.logging.loggers import get_logger
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS

if HAS_PYDANTIC_V2:
    # We cannot load this setting through the normal pattern due to circular
    # imports; instead just check if its a truthy setting directly
    if os.getenv("PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS", "0").lower() in [
        "true",
        "1",
    ]:
        from pydantic import BaseModel as CurrentBaseModel
    else:
        from pydantic.v1 import BaseModel as CurrentBaseModel
    from pydantic.json_schema import GenerateJsonSchema
else:
    from pydantic import BaseModel as CurrentBaseModel

    class GenerateJsonSchema:
        pass


DEFAULT_REF_TEMPLATE = "#/$defs/{model}"
IncEx: TypeAlias = "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"
JsonSchemaMode = Literal["validation", "serialization"]

logger = get_logger("prefect._internal.pydantic")


def should_use_pydantic_v2(
    model_instance: Optional[CurrentBaseModel] = None, method_name: Optional[str] = None
) -> bool:
    """
    Determines if the current environment is compatible with Pydantic V2 features,
    based on the presence of Pydantic V2 and a global setting that enables V2 functionalities.

    This function primarily serves to facilitate conditional logic in code that needs to
    operate differently depending on the availability of Pydantic V2 features. It checks
    two conditions: whether Pydantic V2 is installed, and whether the use of V2 features
    is explicitly enabled through a global setting (`PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS`).

    Parameters:
    -----------
    model_instance : Optional[CurrentBaseModel], optional
        An instance of a Pydantic model. This parameter is used to perform a type check
        to ensure the passed object is a Pydantic model instance. If not provided or if
        the object is not a Pydantic model, a TypeError is raised. Defaults to None.

    method_name : Optional[str], optional
        The name of the function or feature for which V2 compatibility is being checked.
        This is used for logging purposes to provide more context in debug messages.
        Defaults to None.

    Returns:
    --------
    bool
        True if the current environment supports Pydantic V2 features and if the global
        setting for enabling V2 features is set to True. False otherwise.

    Raises:
    -------
    TypeError
        If `model_instance` is provided but is not an instance of a Pydantic BaseModel.
    """
    if model_instance and not isinstance(model_instance, CurrentBaseModel):
        raise TypeError(
            f"Expected a Pydantic model, but got {type(model_instance).__name__}"
        )

    should_dump_as_v2_model = (
        HAS_PYDANTIC_V2 and PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS
    )

    if should_dump_as_v2_model:
        logger.debug(
            f"Using Pydantic v2 compatibility layer for `{method_name}`. This will be removed in a future release."
        )

        return True

    elif HAS_PYDANTIC_V2:
        logger.debug(
            "Pydantic v2 compatibility layer is disabled. To enable, set `PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS` to `True`."
        )

    else:
        logger.debug("Pydantic v2 is not installed.")

    return False


def model_dump(
    model_instance: CurrentBaseModel,
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

    if should_use_pydantic_v2(model_instance=model_instance, method_name="model_dump"):
        return super(CompatBaseModel, model_instance).model_dump(
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

    return model_instance.dict(
        include=include,
        exclude=exclude,
        by_alias=by_alias,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
    )


def model_json_schema(
    model_type: Type[CurrentBaseModel],
    *,
    by_alias: bool = True,
    ref_template: str = DEFAULT_REF_TEMPLATE,
    schema_generator: Optional[Type[GenerateJsonSchema]] = None,
    mode: JsonSchemaMode = "validation",
) -> Dict[str, Any]:
    """
    Generates a JSON schema for a model class.

    Parameters
    ----------
    model_type : Type[CurrentBaseModel]
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
    Dict[str, Any]
        The JSON schema for the given model class.
    """

    if should_use_pydantic_v2(method_name="model_json_schema"):
        return super(CompatBaseModel, model_type).model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator or GenerateJsonSchema,
            mode=mode,
        )

    return model_type.schema(
        by_alias=by_alias,
        ref_template=ref_template,
    )


"""
This class serves as a compatibility layer for Pydantic v2 features.

It exposes the main methods offered by the v2 BaseModel class, such as `model_dump` and `model_json_schema`,
and switches between the v1 and v2 implementations based on the availability of Pydantic v2 and a global setting
that enables v2 features, `PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS`.
"""


class CompatBaseModel(CurrentBaseModel):
    def model_dump(
        self,
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

    @classmethod
    def model_json_schema(
        cls: Type[CurrentBaseModel],
        *,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: Optional[Type[GenerateJsonSchema]] = None,
        mode: JsonSchemaMode = "validation",
    ) -> Dict[str, Any]:
        """
        Generates a JSON schema for the model.

        Parameters
        ----------
        cls : Type[CurrentBaseModel]
        by_alias : bool, optional
            Whether to use attribute aliases or not, by default True
        ref_template : str, optional
            The reference template, by default DEFAULT_REF_TEMPLATE
        schema_generator : type[GenerateEmptySchemaForUserClasses], optional
            To override the logic used to generate the JSON schema, as a subclass of Generate
            EmptySchemaForUserClasses with your desired modifications, by default GenerateEmptySchemaForUserClasses
        mode : JsonSchemaMode, optional
            The mode in which to generate the schema, by default 'validation'

        Returns
        -------
        Dict[str, Any]
            The JSON schema for the model.
        """
        return model_json_schema(
            cls,
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
        )


BaseModel = CompatBaseModel
