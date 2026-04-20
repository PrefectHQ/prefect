"""
Union type utilities for SDK generation.

This module provides bracket and quote-aware union type handling.
"""


def split_union_top_level(type_str: str) -> list[str]:
    """
    Split a union type string on " | " only at the top level.

    This is bracket and quote-aware, so it won't split inside:
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


def flatten_union(types: list[str]) -> str:
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
        parts = split_union_top_level(t)
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
