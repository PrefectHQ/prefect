from typing import Optional
from uuid import UUID

def truncated_to(length: int, value: Optional[str]) -> str:
    if not value:
        return ""

    if len(value) <= length:
        return value

    half = length // 2

    beginning = value[:half]
    end = value[-half:]
    omitted = len(value) - (len(beginning) + len(end))

    proposed = f"{beginning}...{omitted} additional characters...{end}"

    return proposed if len(proposed) < len(value) else value

def is_valid_uuid(uuid_str: str, version=4) -> bool:
    try:
        uuid_obj = UUID(uuid_str, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_str