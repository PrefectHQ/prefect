def truncated_to(length: int, value: str | None) -> str:
    if not value:
        return ""

    if len(value) <= length:
        return value

    half = length // 2

    beginning = value[:half]
    end = value[-half:]
    omitted = len(value) - (len(beginning) + len(end))

    proposed = f"{beginning}...{omitted} additional characters...{end}"

    # So we don't look silly when truncating something that is just like length + 11
    # characters long, let's make sure the new string would actually be smaller
    return proposed if len(proposed) < len(value) else value
