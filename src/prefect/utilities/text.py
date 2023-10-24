from typing import Optional


def truncated_to(length: int, value: Optional[str]) -> str:
    if not value:
        return ""

    if len(value) <= length:
        return value

    help_text = "...[truncated]..."

    truncated = value[: length - len(help_text)]

    return truncated + help_text if len(truncated) < len(help_text) else value[:length]
