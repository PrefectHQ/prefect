"""
JSON Schema to Python type conversion for SDK generation.

This module converts JSON Schema definitions (like those from Pydantic models)
to Python type annotation strings suitable for TypedDict field definitions.

Limitations:
    - allOf: Returns the first $ref or non-Any type. Intersection semantics
      (combining constraints from multiple schemas) are not modeled.
    - Nested objects: Objects with properties return "dict[str, Any]". The
      template renderer in Phase 3 handles nested TypedDict generation.
    - External $ref: Only internal references (#/definitions/... and #/$defs/...)
      are supported. External URLs and other formats return Any with a warning.
    - Tuple constraints: prefixItems and items-as-list are converted to tuple[...],
      but minItems, maxItems, additionalItems, and unevaluatedItems are ignored.
    - patternProperties and propertyNames are not supported.

Note:
    To capture warnings during conversion, pass a ConversionContext and check
    its `conversion_warnings` list after calling json_schema_to_python_type().
"""

from typing import Any

from prefect._sdk.types import (
    CircularReferenceError,
    ConversionContext,
    FieldInfo,
)
from prefect._sdk.unions import flatten_union

# Re-export public types
__all__ = [
    "CircularReferenceError",
    "ConversionContext",
    "FieldInfo",
    "json_schema_to_python_type",
    "extract_fields_from_schema",
]


def json_schema_to_python_type(
    schema: dict[str, Any] | bool,
    context: ConversionContext | None = None,
) -> str:
    """
    Convert a JSON Schema to a Python type annotation string.

    Args:
        schema: A JSON Schema dict or boolean schema.
        context: Conversion context for tracking definitions and visited refs.
            Pass a context to capture warnings during conversion.

    Returns:
        A Python type annotation string (e.g., "str", "list[int]", "dict[str, Any]").

    Raises:
        CircularReferenceError: If a circular $ref is detected.

    Examples:
        >>> json_schema_to_python_type({"type": "string"})
        'str'
        >>> json_schema_to_python_type({"type": "array", "items": {"type": "integer"}})
        'list[int]'
        >>> json_schema_to_python_type({"anyOf": [{"type": "string"}, {"type": "null"}]})
        'str | None'
    """
    if context is None:
        context = ConversionContext()

    # Handle boolean schemas
    if isinstance(schema, bool):
        # true = accepts anything, false = accepts nothing
        # Using "Never" for false would be more accurate, but "Any" is more
        # practical since Never is rarely used and may cause type checker issues.
        # In practice, boolean false schemas are extremely rare.
        return "Any"

    # Handle empty schema (accepts anything)
    if not schema:
        return "Any"

    # Handle $ref first (before type checks)
    if "$ref" in schema:
        return _resolve_ref(schema["$ref"], context)

    # Handle anyOf / oneOf (union types)
    if "anyOf" in schema:
        return _convert_any_of(schema["anyOf"], context)
    if "oneOf" in schema:
        return _convert_any_of(schema["oneOf"], context)

    # Handle allOf (intersection - we just use the first one with useful info)
    if "allOf" in schema:
        return _convert_all_of(schema["allOf"], context)

    # Handle enum types
    if "enum" in schema:
        return _convert_enum(schema["enum"])

    # Handle const (single-value enum)
    if "const" in schema:
        return _convert_const(schema["const"])

    # Get the type field
    # Note: prefixItems (tuples) are handled by _convert_array when type is "array"
    schema_type = schema.get("type")

    # No type field - could be a complex schema or missing type
    if schema_type is None:
        # Check if it has properties (object without explicit type)
        if "properties" in schema:
            return "dict[str, Any]"
        # Check if it has items (array without explicit type)
        if "items" in schema:
            items_schema: dict[str, Any] = schema["items"]
            items_type = json_schema_to_python_type(items_schema, context)
            return f"list[{items_type}]"
        # Unknown schema structure
        return "Any"

    # Handle type arrays (e.g., ["string", "null"])
    if isinstance(schema_type, list):
        type_list: list[str] = schema_type
        return _convert_type_array(type_list, schema, context)

    # Handle single type
    return _convert_single_type(schema_type, schema, context)


def _resolve_ref(ref: str, context: ConversionContext) -> str:
    """Resolve a $ref pointer to its type."""
    # Check for circular reference
    if ref in context.visited_refs:
        raise CircularReferenceError(f"Circular reference detected: {ref}")

    # Extract definition name from ref
    # Handles both "#/definitions/Foo" and "#/$defs/Foo"
    if ref.startswith("#/definitions/"):
        def_name = ref[len("#/definitions/") :]
    elif ref.startswith("#/$defs/"):
        def_name = ref[len("#/$defs/") :]
    else:
        # Unknown ref format (external URLs, OpenAPI-style, etc.)
        context.conversion_warnings.append(f"Unknown $ref format: {ref}")
        return "Any"

    # Look up in definitions
    definition = context.definitions.get(def_name)
    if definition is None:
        context.conversion_warnings.append(f"Definition not found: {def_name}")
        return "Any"

    # Mark as visited and recurse
    context.visited_refs.add(ref)
    try:
        return json_schema_to_python_type(definition, context)
    finally:
        context.visited_refs.discard(ref)


def _convert_any_of(variants: list[dict[str, Any]], context: ConversionContext) -> str:
    """Convert anyOf/oneOf to a union type with proper flattening."""
    types: list[str] = []

    for variant in variants:
        variant_type = json_schema_to_python_type(variant, context)
        types.append(variant_type)

    return flatten_union(types)


def _convert_all_of(variants: list[dict[str, Any]], context: ConversionContext) -> str:
    """
    Convert allOf to a type.

    Note: This does not model true intersection semantics. It returns the first
    $ref found, or the first non-Any variant. This is typically sufficient for
    Pydantic schemas where allOf is used to wrap a $ref with additional metadata.
    """
    # allOf is often used to wrap a $ref
    # Try to find the most specific type
    for variant in variants:
        if "$ref" in variant:
            return _resolve_ref(variant["$ref"], context)

    # Otherwise convert the first variant with useful type info
    for variant in variants:
        result = json_schema_to_python_type(variant, context)
        if result != "Any":
            return result

    return "Any"


def _format_literal_value(value: Any) -> str | None:
    """
    Format a value for use in a Literal type annotation.

    Args:
        value: The value to format.

    Returns:
        A string representation suitable for Literal[], or None if unsupported.
    """
    if isinstance(value, str):
        # Use repr() for proper escaping of all special characters
        # (newlines, tabs, quotes, backslashes, etc.)
        return repr(value)
    elif isinstance(value, bool):
        # Must check bool before int since bool is subclass of int
        return str(value)
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, float):
        # Support float literals
        return repr(value)
    elif value is None:
        return "None"
    else:
        # Unsupported type (dict, list, etc.)
        return None


def _convert_enum(values: list[Any]) -> str:
    """Convert enum to Literal type."""
    if not values:
        return "Any"

    literals: list[str] = []
    for value in values:
        formatted = _format_literal_value(value)
        if formatted is None:
            # Unsupported enum value type - fall back to Any
            return "Any"
        literals.append(formatted)

    return f"Literal[{', '.join(literals)}]"


def _convert_const(value: Any) -> str:
    """Convert const to Literal type."""
    return _convert_enum([value])


def _convert_tuple(
    prefix_items: list[dict[str, Any]], context: ConversionContext
) -> str:
    """
    Convert prefixItems to tuple type.

    Note: Constraints like minItems, maxItems, additionalItems are not
    validated here - we generate the tuple type based solely on prefixItems.
    """
    if not prefix_items:
        return "tuple[()]"

    item_types = [json_schema_to_python_type(item, context) for item in prefix_items]
    return f"tuple[{', '.join(item_types)}]"


def _convert_type_array(
    types: list[str], schema: dict[str, Any], context: ConversionContext
) -> str:
    """Convert a type array (e.g., ["string", "null"]) to union type."""
    # Deduplicate types first
    unique_types: list[str] = []
    for t in types:
        if t not in unique_types:
            unique_types.append(t)

    # Filter out null and convert rest
    non_null_types = [t for t in unique_types if t != "null"]
    has_null = "null" in unique_types

    if not non_null_types:
        return "None"

    # Convert each type
    converted: list[str] = []
    for t in non_null_types:
        # Create a schema copy with single type for conversion
        type_schema = {k: v for k, v in schema.items() if k != "type"}
        type_schema["type"] = t
        converted.append(_convert_single_type(t, type_schema, context))

    # Use flatten_union to handle deduplication
    if has_null:
        converted.append("None")

    return flatten_union(converted)


def _convert_single_type(
    schema_type: str, schema: dict[str, Any], context: ConversionContext
) -> str:
    """Convert a single JSON Schema type to Python type."""
    if schema_type == "string":
        return "str"
    elif schema_type == "integer":
        return "int"
    elif schema_type == "number":
        return "float"
    elif schema_type == "boolean":
        return "bool"
    elif schema_type == "null":
        return "None"
    elif schema_type == "array":
        return _convert_array(schema, context)
    elif schema_type == "object":
        return _convert_object(schema, context)
    else:
        context.conversion_warnings.append(f"Unknown type: {schema_type}")
        return "Any"


def _convert_array(schema: dict[str, Any], context: ConversionContext) -> str:
    """Convert array schema to list or tuple type."""
    # Check for prefixItems (tuple)
    if "prefixItems" in schema:
        prefix_items: list[dict[str, Any]] = schema["prefixItems"]
        return _convert_tuple(prefix_items, context)

    # Check for items (Pydantic v1 tuple format with list of items)
    items = schema.get("items")
    if isinstance(items, list):
        # This is a tuple pattern (items as array)
        items_list: list[dict[str, Any]] = items
        return _convert_tuple(items_list, context)

    # Regular array with items schema
    if items is not None:
        items_dict: dict[str, Any] = items
        item_type = json_schema_to_python_type(items_dict, context)
        return f"list[{item_type}]"

    # No items schema - generic list
    return "list[Any]"


def _convert_object(schema: dict[str, Any], context: ConversionContext) -> str:
    """
    Convert object schema to dict type.

    Note: This always returns a dict type, not a TypedDict. Objects with
    defined properties are handled at a higher level (the template renderer)
    which generates named TypedDict classes. This converter only handles
    the type annotation for inline use.
    """
    # Check for additionalProperties
    additional = schema.get("additionalProperties")

    if additional is True or additional is None:
        # Accept any values
        return "dict[str, Any]"

    if additional is False:
        # Only defined properties allowed, but we still return dict
        return "dict[str, Any]"

    if isinstance(additional, dict):
        # Typed additional properties
        additional_dict: dict[str, Any] = additional
        value_type = json_schema_to_python_type(additional_dict, context)
        return f"dict[str, {value_type}]"

    return "dict[str, Any]"


def extract_fields_from_schema(
    schema: dict[str, Any],
    required_fields: list[str] | None = None,
) -> tuple[list[FieldInfo], list[str]]:
    """
    Extract TypedDict field information from a JSON Schema.

    Args:
        schema: A JSON Schema dict with properties.
        required_fields: List of required field names. If None, uses schema's "required".

    Returns:
        A tuple of (fields, warnings) where fields is a list of FieldInfo objects.

    Note:
        A field is considered required (no NotRequired wrapper) if:
        - It is listed in the schema's "required" array AND
        - It does NOT have a "default" key in its property definition

        This matches Prefect's server-side parameter validation.
    """
    # Build context with definitions
    context = ConversionContext(
        definitions={
            **schema.get("definitions", {}),
            **schema.get("$defs", {}),
        }
    )

    properties: dict[str, Any] = schema.get("properties", {})
    required_list: list[str] = (
        required_fields if required_fields is not None else schema.get("required", [])
    )

    fields: list[FieldInfo] = []

    for prop_name, prop_schema in properties.items():
        # Determine if field is required
        # Required means: in required list AND no default value
        is_required = prop_name in required_list and "default" not in prop_schema

        # Get type
        try:
            python_type = json_schema_to_python_type(prop_schema, context)
        except CircularReferenceError:
            context.conversion_warnings.append(
                f"Circular reference in field '{prop_name}', using Any"
            )
            python_type = "Any"

        # Extract other info
        default_value = prop_schema.get("default")
        has_default = "default" in prop_schema
        description = prop_schema.get("description") or prop_schema.get("title")

        fields.append(
            FieldInfo(
                name=prop_name,
                python_type=python_type,
                required=is_required,
                default=default_value,
                has_default=has_default,
                description=description,
            )
        )

    return fields, context.conversion_warnings
