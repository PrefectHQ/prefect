import difflib
from typing import Iterable, Optional


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


def fuzzy_match_string(
    word: str,
    possibilities: Iterable[str],
    *,
    n: int = 1,
    cutoff: float = 0.6,
) -> Optional[str]:
    match = difflib.get_close_matches(word, possibilities, n=n, cutoff=cutoff)
    return match[0] if match else None
