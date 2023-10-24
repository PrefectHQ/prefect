from typing import Optional

HELP_TEXT = "...[truncated]..."


def truncated_to(length: int, value: Optional[str]) -> str:
    if not value:
        return ""

    if len(value) <= length:
        return value

    return (
        value[: length - len(HELP_TEXT)] + HELP_TEXT
        if len(HELP_TEXT) < length
        else value[:length]
    )
