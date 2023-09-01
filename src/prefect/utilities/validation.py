import jsonschema


def validate_values_conform_to_schema(values: dict, schema: dict):
    """
    Validate that the parameters conform to the parameter schema.

    Raises:
        ValueError: If the parameters do not conform to the schema.
    """
    try:
        if schema is not None and values is not None:
            jsonschema.validate(values, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            "The parameters provided do not conform to the deployment parameter"
            f" schema. Validation error: {exc.message}"
        ) from exc
