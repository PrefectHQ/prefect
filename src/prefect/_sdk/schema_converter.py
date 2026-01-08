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

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversionContext:
    """Context for schema conversion, tracking definitions and visited refs."""

    definitions: dict[str, Any] = field(default_factory=dict)
    """Schema definitions (from 'definitions' or '$defs' key)."""

    visited_refs: set[str] = field(default_factory=set)
    """Set of $ref paths currently being resolved (for circular detection)."""

    conversion_warnings: list[str] = field(default_factory=list)
    """Warnings accumulated during conversion."""


class CircularReferenceError(Exception):
    """Raised when a circular $ref is detected in the schema."""

    pass


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


def _split_union_top_level(type_str: str) -> list[str]:
    """
    Split a union type string on " | " only at the top level.

    This is bracket- and quote-aware, so it won't split inside:
    - Brackets: list[str | int] stays intact
    - Quotes: Literal['a | b'] stays intact

    Args:
        type_str: A type annotation string, possibly containing unions.

    Returns:
        List of individual type parts.
    """
    parts: list[str] = []
    current: list[str] = []
    bracket_depth = 0
    in_single_quote = False
    in_double_quote = False
    i = 0

    while i < len(type_str):
        char = type_str[i]

        # Handle escape sequences inside quotes
        if (in_single_quote or in_double_quote) and char == "\\":
            current.append(char)
            if i + 1 < len(type_str):
                current.append(type_str[i + 1])
                i += 2
                continue
            i += 1
            continue

        # Track quote state
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(char)
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(char)
        # Track bracket depth (only when not in quotes)
        elif char == "[" and not in_single_quote and not in_double_quote:
            bracket_depth += 1
            current.append(char)
        elif char == "]" and not in_single_quote and not in_double_quote:
            bracket_depth -= 1
            current.append(char)
        # Check for " | " at top level
        elif (
            char == " "
            and bracket_depth == 0
            and not in_single_quote
            and not in_double_quote
            and type_str[i : i + 3] == " | "
        ):
            # Found a top-level union separator
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            i += 3  # Skip " | "
            continue
        else:
            current.append(char)

        i += 1

    # Add the last part
    part = "".join(current).strip()
    if part:
        parts.append(part)

    return parts


def _flatten_union(types: list[str]) -> str:
    """
    Flatten and deduplicate union type parts.

    Handles nested unions (e.g., "str | int" combined with "str | None")
    by splitting on " | " at the top level only (bracket- and quote-aware),
    deduplicating, and placing None at the end.

    Args:
        types: List of type strings, possibly containing unions.

    Returns:
        A single union type string with duplicates removed and None at end.
    """
    # Split any nested unions and collect all parts
    all_parts: list[str] = []
    has_none = False

    for t in types:
        # Split on " | " only at top level (respecting brackets and quotes)
        parts = _split_union_top_level(t)
        for part in parts:
            if part == "None":
                has_none = True
            elif part and part not in all_parts:
                all_parts.append(part)

    # Handle edge case: only None
    if not all_parts:
        return "None"

    # Build result with None at the end if present
    if len(all_parts) == 1:
        result = all_parts[0]
    else:
        result = " | ".join(all_parts)

    if has_none:
        result = f"{result} | None"

    return result


def _convert_any_of(variants: list[dict[str, Any]], context: ConversionContext) -> str:
    """Convert anyOf/oneOf to a union type with proper flattening."""
    # Convert each variant
    types: list[str] = []

    for variant in variants:
        variant_type = json_schema_to_python_type(variant, context)
        types.append(variant_type)

    return _flatten_union(types)


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

    return _flatten_union(converted)


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


@dataclass
class FieldInfo:
    """Information about a TypedDict field."""

    name: str
    """The field name."""

    python_type: str
    """The Python type annotation string."""

    required: bool
    """Whether the field is required."""

    default: Any | None = None
    """The default value, if any."""

    has_default: bool = False
    """Whether a default value is present."""

    description: str | None = None
    """Field description from schema."""


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
