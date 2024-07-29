from collections import defaultdict, deque
from copy import deepcopy
from typing import Any, Dict, List

import jsonschema
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
from jsonschema.validators import Draft202012Validator, create

from prefect.utilities.collections import remove_nested_keys
from prefect.utilities.schema_tools.hydration import HydrationError, Placeholder


class CircularSchemaRefError(Exception):
    pass


class ValidationError(Exception):
    pass


PLACEHOLDERS_VALIDATOR_NAME = "_placeholders"


def _build_validator():
    def _applicable_validators(schema):
        # the default implementation returns `schema.items()`
        return {**schema, PLACEHOLDERS_VALIDATOR_NAME: None}.items()

    def _placeholders(validator, _, instance, schema):
        if isinstance(instance, HydrationError):
            yield JSONSchemaValidationError(instance.message)

    validators = dict(Draft202012Validator.VALIDATORS)
    validators.update({PLACEHOLDERS_VALIDATOR_NAME: _placeholders})

    # It is necessary to `create` a new validator instead of using `extend` because
    # the `extend` method does not accept an `application_validators` parameter.
    # We want `_placeholders` to be applicable always, without needing to modify
    # the schema itself.
    return create(
        meta_schema=Draft202012Validator.META_SCHEMA,
        validators=validators,
        version="prefect",
        type_checker=Draft202012Validator.TYPE_CHECKER,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
        id_of=Draft202012Validator.ID_OF,
        applicable_validators=_applicable_validators,
    )


_VALIDATOR = _build_validator()


def is_valid_schema(schema: Dict, preprocess: bool = True):
    if preprocess:
        schema = preprocess_schema(schema)
    try:
        if schema is not None:
            _VALIDATOR.check_schema(schema, format_checker=_VALIDATOR.FORMAT_CHECKER)
    except jsonschema.SchemaError as exc:
        raise ValueError(f"Invalid schema: {exc.message}") from exc


def validate(
    obj: Dict,
    schema: Dict,
    raise_on_error: bool = False,
    preprocess: bool = True,
    ignore_required: bool = False,
    allow_none_with_default: bool = False,
) -> List[JSONSchemaValidationError]:
    if preprocess:
        schema = preprocess_schema(schema, allow_none_with_default)

    if ignore_required:
        schema = remove_nested_keys(["required"], schema)

    if raise_on_error:
        try:
            jsonschema.validate(obj, schema, _VALIDATOR)
        except RecursionError:
            raise CircularSchemaRefError
        except JSONSchemaValidationError as exc:
            if exc.json_path == "$":
                error_message = "Validation failed."
            else:
                error_message = (
                    f"Validation failed for field {exc.json_path.replace('$.', '')!r}."
                )
            error_message += f" Failure reason: {exc.message}"
            raise ValidationError(error_message) from exc
        return []
    else:
        try:
            validator = _VALIDATOR(schema, format_checker=_VALIDATOR.FORMAT_CHECKER)
            errors = list(validator.iter_errors(obj))
        except RecursionError:
            raise CircularSchemaRefError
        return errors


def is_valid(
    obj: Dict,
    schema: Dict,
) -> bool:
    errors = validate(obj, schema)
    return len(errors) == 0


def prioritize_placeholder_errors(errors):
    errors_by_path = defaultdict(list)
    for error in errors:
        path_str = "->".join(str(p) for p in error.relative_path)
        errors_by_path[path_str].append(error)

    filtered_errors = []
    for path, grouped_errors in errors_by_path.items():
        placeholders_errors = [
            error
            for error in grouped_errors
            if error.validator == PLACEHOLDERS_VALIDATOR_NAME
        ]

        if placeholders_errors:
            filtered_errors.extend(placeholders_errors)
        else:
            filtered_errors.extend(grouped_errors)

    return filtered_errors


def build_error_obj(errors: List[JSONSchemaValidationError]) -> Dict:
    error_response: Dict[str, Any] = {"errors": []}

    # If multiple errors are present for the same path and one of them
    # is a placeholder error, we want only want to use the placeholder error.
    errors = prioritize_placeholder_errors(errors)

    for error in errors:
        # If the Placeholder is not representing an error, we can skip it
        if isinstance(error.instance, Placeholder) and not error.instance.is_error:
            continue

        path = deque(error.relative_path)

        # Required errors should be moved one level down to the property
        # they're associated with, so we add an extra level to the path.
        if error.validator == "required":
            required_field = error.message.split(" ")[0].strip("'")
            path.append(required_field)

        current = error_response["errors"]

        # error at the root, just append the error message
        if not path:
            current.append(error.message)

        while path:
            part = path.popleft()
            if isinstance(part, int):
                if not path:
                    current.append({"index": part, "errors": [error.message]})
                else:
                    for entry in current:
                        if entry.get("index") == part:
                            current = entry["errors"]
                            break
                    else:
                        new_entry = {"index": part, "errors": []}
                        current.append(new_entry)
                        current = new_entry["errors"]
            else:
                if not path:
                    current.append({"property": part, "errors": [error.message]})
                else:
                    for entry in current:
                        if entry.get("property") == part:
                            current = entry.get("errors", [])
                            break
                    else:
                        new_entry = {"property": part, "errors": []}
                        current.append(new_entry)
                        current = new_entry["errors"]

    valid = len(error_response["errors"]) == 0
    error_response["valid"] = valid

    return error_response


def _fix_null_typing(
    key: str,
    schema: Dict,
    required_fields: List[str],
    allow_none_with_default: bool = False,
):
    """
    Pydantic V1 does not generate a valid Draft2020-12 schema for null types.
    """
    if (
        key not in required_fields
        and "type" in schema
        and schema.get("type") != "null"
        and ("default" not in schema or allow_none_with_default)
    ):
        schema["anyOf"] = [{"type": schema["type"]}, {"type": "null"}]
        del schema["type"]


def _fix_tuple_items(schema: Dict):
    """
    Pydantic V1 does not generate a valid Draft2020-12 schema for tuples.
    """
    if (
        schema.get("items")
        and isinstance(schema["items"], list)
        and not schema.get("prefixItems")
    ):
        schema["prefixItems"] = deepcopy(schema["items"])
        del schema["items"]


def process_properties(
    properties: Dict,
    required_fields: List[str],
    allow_none_with_default: bool = False,
):
    for key, schema in properties.items():
        _fix_null_typing(key, schema, required_fields, allow_none_with_default)
        _fix_tuple_items(schema)

        if "properties" in schema:
            required_fields = schema.get("required", [])
            process_properties(schema["properties"], required_fields)


def preprocess_schema(
    schema: Dict,
    allow_none_with_default: bool = False,
):
    schema = deepcopy(schema)

    if "properties" in schema:
        required_fields = schema.get("required", [])
        process_properties(
            schema["properties"], required_fields, allow_none_with_default
        )

    if "definitions" in schema:  # Also process definitions for reused models
        for definition in (schema["definitions"] or {}).values():
            if "properties" in definition:
                required_fields = definition.get("required", [])
                process_properties(
                    definition["properties"], required_fields, allow_none_with_default
                )
            # Allow block types to be referenced by their id
            if "block_type_slug" in definition:
                schema["definitions"][definition["title"]] = {
                    "oneOf": [
                        definition,
                        {
                            "type": "object",
                            "properties": {
                                "$ref": {
                                    "oneOf": [
                                        {
                                            "type": "string",
                                            "format": "uuid",
                                        },
                                        {
                                            "type": "object",
                                            "additionalProperties": {
                                                "type": "string",
                                            },
                                            "minProperties": 1,
                                        },
                                    ]
                                }
                            },
                            "required": [
                                "$ref",
                            ],
                        },
                    ]
                }

    return schema
