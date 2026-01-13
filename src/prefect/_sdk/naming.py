"""
Naming utilities for SDK generation.

This module converts arbitrary names (deployment names, flow names, work pool names)
to valid Python identifiers and class names.

Conversion rules for identifiers:
1. Normalize Unicode to ASCII where possible (é -> e via NFKD decomposition)
2. Treat Unicode separators/punctuation (em-dash, non-breaking space, etc.) as word boundaries
3. Replace ASCII hyphens, spaces, and punctuation with underscores
4. Drop remaining non-ASCII characters
5. Collapse consecutive underscores
6. Strip leading/trailing underscores
7. Prefix with underscore if starts with digit
8. Append underscore if Python keyword (class -> class_)
9. Return "_unnamed" if result is empty

Conversion rules for class names:
1. Same Unicode handling as identifiers
2. Split on separators/punctuation to get word parts
3. Capitalize first letter of each part (PascalCase)
4. Prefix with underscore if starts with digit
5. Return "_Unnamed" if result is empty
"""

import keyword
import re
import unicodedata
from typing import Literal

# Python keywords that need underscore suffix
PYTHON_KEYWORDS = frozenset(keyword.kwlist)

# Names reserved in specific contexts - these conflict with generated SDK surface
# IMPORTANT: These must be in NORMALIZED form (as returned by to_identifier)
# because safe_identifier() normalizes the input before checking reserved names.

# Flow identifiers that would shadow the root namespace
RESERVED_FLOW_IDENTIFIERS = frozenset({"flows", "deployments", "DeploymentName"})

# Deployment identifiers that would break method signatures
# Note: Method names (run, run_async, etc.) don't need to be reserved because
# parameters are kwargs to run(), not attributes on the class.
# Template locals now use _sdk_ prefix to avoid collisions.
RESERVED_DEPLOYMENT_IDENTIFIERS = frozenset(
    {
        # Python built-in that would break method signatures
        "self",
    }
)

# Module-level names that should be avoided
# Note: "__all__" normalizes to "all" (underscores stripped)
RESERVED_MODULE_IDENTIFIERS = frozenset({"all"})


def _is_separator(char: str) -> bool:
    """
    Check if a character should be treated as a word separator.

    Handles both ASCII separators and Unicode separators/punctuation.
    """
    # Common ASCII separators
    if char in "-_ \t\n\r":
        return True

    # Check Unicode category for separators and punctuation
    # Z* = separators (space, line, paragraph)
    # P* = punctuation (connector, dash, open, close, etc.)
    # S* = symbols (math, currency, modifier, other)
    category = unicodedata.category(char)
    if category.startswith(("Z", "P", "S")):
        return True

    return False


def to_identifier(name: str) -> str:
    """
    Convert an arbitrary name to a valid Python identifier.

    Args:
        name: Any string (deployment name, flow name, etc.)

    Returns:
        A valid Python identifier.

    Examples:
        >>> to_identifier("my-flow")
        'my_flow'
        >>> to_identifier("123-start")
        '_123_start'
        >>> to_identifier("class")
        'class_'
        >>> to_identifier("café-data")
        'cafe_data'
        >>> to_identifier("🚀-deploy")
        'deploy'
        >>> to_identifier("a]b")
        'a_b'
    """
    if not name:
        return "_unnamed"

    # Normalize unicode to ASCII where possible (é -> e, etc.)
    normalized = unicodedata.normalize("NFKD", name)

    # Build result keeping only ASCII alphanumeric and converting separators
    result: list[str] = []
    for char in normalized:
        if char.isascii() and char.isalnum():
            result.append(char)
        elif _is_separator(char):
            # Separators (including Unicode dashes, spaces, punctuation) become underscore
            result.append("_")
        elif char.isascii():
            # Other ASCII becomes underscore (shouldn't hit often after separator check)
            result.append("_")
        # Non-ASCII non-separator characters are dropped

    identifier = "".join(result)

    # Collapse consecutive underscores
    identifier = re.sub(r"_+", "_", identifier)

    # Strip leading/trailing underscores (we'll add prefix if needed)
    identifier = identifier.strip("_")

    # Handle empty result
    if not identifier:
        return "_unnamed"

    # Prefix with underscore if starts with digit
    if identifier[0].isdigit():
        identifier = f"_{identifier}"

    # Append underscore if Python keyword
    if identifier in PYTHON_KEYWORDS:
        identifier = f"{identifier}_"

    return identifier


def to_class_name(name: str) -> str:
    """
    Convert an arbitrary name to a valid PascalCase class name.

    Args:
        name: Any string (deployment name, flow name, etc.)

    Returns:
        A valid Python class name in PascalCase.

    Examples:
        >>> to_class_name("my-flow")
        'MyFlow'
        >>> to_class_name("123-start")
        '_123Start'
        >>> to_class_name("class")
        'Class'
        >>> to_class_name("my_flow")
        'MyFlow'
        >>> to_class_name("café-data")
        'CafeData'
        >>> to_class_name("🚀-deploy")
        'Deploy'
        >>> to_class_name("a]b")
        'AB'
    """
    if not name:
        return "_Unnamed"

    # Normalize unicode to ASCII where possible
    normalized = unicodedata.normalize("NFKD", name)

    # Build parts for PascalCase by splitting on separators
    parts: list[str] = []
    current_part: list[str] = []

    for char in normalized:
        if char.isascii() and char.isalnum():
            current_part.append(char)
        elif _is_separator(char):
            # Separator - save current part and start new one
            if current_part:
                parts.append("".join(current_part))
                current_part = []
        elif char.isascii():
            # Other ASCII - treat as separator
            if current_part:
                parts.append("".join(current_part))
                current_part = []
        # Non-ASCII non-separator characters are dropped

    # Don't forget the last part
    if current_part:
        parts.append("".join(current_part))

    # Handle empty result
    if not parts:
        return "_Unnamed"

    # Convert to PascalCase
    result_parts: list[str] = []
    for part in parts:
        if part:
            # Capitalize first letter, preserve rest
            result_parts.append(part[0].upper() + part[1:])

    class_name = "".join(result_parts)

    # Handle empty result after joining (shouldn't happen, but be safe)
    if not class_name:
        return "_Unnamed"

    # Prefix with underscore if starts with digit
    if class_name[0].isdigit():
        class_name = f"_{class_name}"

    # Note: We don't append underscore for keywords here because:
    # 1. Python is case-sensitive, so "Class" is valid (not a keyword)
    # 2. PascalCase naturally avoids most keywords (e.g., "class" -> "Class")
    # 3. Lowercase keywords as input would become "Class", "For", etc. which are valid

    return class_name


def make_unique_identifier(
    base: str,
    existing: set[str],
    reserved: frozenset[str] | None = None,
) -> str:
    """
    Make an identifier unique by appending numeric suffix if needed.

    Args:
        base: The base identifier (already converted via to_identifier).
        existing: Set of already-used identifiers.
        reserved: Optional set of reserved names to avoid.

    Returns:
        A unique identifier, possibly with _2, _3, etc. suffix.

    Examples:
        >>> make_unique_identifier("my_flow", {"my_flow"})
        'my_flow_2'
        >>> make_unique_identifier("my_flow", {"my_flow", "my_flow_2"})
        'my_flow_3'
        >>> make_unique_identifier("run", set(), RESERVED_DEPLOYMENT_IDENTIFIERS)
        'run_2'
    """
    reserved = reserved or frozenset()

    # Check if base is available
    if base not in existing and base not in reserved:
        return base

    # Find the next available suffix
    suffix = 2
    while True:
        candidate = f"{base}_{suffix}"
        if candidate not in existing and candidate not in reserved:
            return candidate
        suffix += 1


def make_unique_class_name(
    base: str,
    existing: set[str],
) -> str:
    """
    Make a class name unique by appending numeric suffix if needed.

    Args:
        base: The base class name (already converted via to_class_name).
        existing: Set of already-used class names.

    Returns:
        A unique class name, possibly with 2, 3, etc. suffix.

    Examples:
        >>> make_unique_class_name("MyFlow", {"MyFlow"})
        'MyFlow2'
        >>> make_unique_class_name("MyFlow", {"MyFlow", "MyFlow2"})
        'MyFlow3'
    """
    if base not in existing:
        return base

    # Find the next available suffix
    suffix = 2
    while True:
        candidate = f"{base}{suffix}"
        if candidate not in existing:
            return candidate
        suffix += 1


NameContext = Literal["flow", "deployment", "work_pool", "module", "general"]


def get_reserved_names(context: NameContext) -> frozenset[str]:
    """
    Get the reserved names for a given context.

    These names would conflict with the generated SDK surface and must be avoided.

    Args:
        context: The naming context.

    Returns:
        A frozenset of reserved names.
    """
    if context == "flow":
        return RESERVED_FLOW_IDENTIFIERS
    elif context == "deployment":
        return RESERVED_DEPLOYMENT_IDENTIFIERS
    elif context == "module":
        return RESERVED_MODULE_IDENTIFIERS
    else:
        return frozenset()


def safe_identifier(
    name: str,
    existing: set[str],
    context: NameContext = "general",
) -> str:
    """
    Convert a name to a unique, safe Python identifier.

    This is the main entry point for identifier generation.

    Args:
        name: The original name.
        existing: Set of already-used identifiers.
        context: The naming context (affects reserved names).

    Returns:
        A unique, valid Python identifier.
    """
    base = to_identifier(name)
    reserved = get_reserved_names(context)
    return make_unique_identifier(base, existing, reserved)


def safe_class_name(
    name: str,
    existing: set[str],
) -> str:
    """
    Convert a name to a unique, safe Python class name.

    This is the main entry point for class name generation.

    Args:
        name: The original name.
        existing: Set of already-used class names.

    Returns:
        A unique, valid PascalCase class name.
    """
    base = to_class_name(name)
    return make_unique_class_name(base, existing)
