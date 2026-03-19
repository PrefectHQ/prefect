import difflib
import sys
from collections.abc import Iterable
from typing import IO, Any, Optional, cast

from rich.console import Console


class _SafeFileWrapper:
    """A thin wrapper around a text stream that replaces unencodable chars.

    pywin32 can monkey-patch ``sys.stdout`` with a tee writer whose internal
    file uses cp1252, while the outer stream still reports
    ``encoding='utf-8'``.  Rich trusts the reported encoding, renders Unicode
    box-drawing characters, and then the tee's write raises
    ``UnicodeEncodeError``.

    This wrapper catches that error and retries the write with
    ``errors='replace'`` re-encoding so the output degrades gracefully
    instead of crashing the caller.
    """

    def __init__(self, wrapped: IO[str]):
        self._wrapped = wrapped

    # Forward every attribute Rich (or anything else) might inspect.
    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def write(self, s: str) -> int:
        try:
            return self._wrapped.write(s)
        except UnicodeEncodeError as exc:
            # Use the encoding from the exception (the one that actually
            # failed) rather than the stream's declared encoding.  In the
            # pywin32 scenario the stream says 'utf-8' but the real codec
            # is cp1252, so re-encoding through the *declared* encoding
            # would be a no-op.
            fallback: str = exc.encoding or "ascii"
            safe = s.encode(fallback, errors="replace").decode(fallback)
            return self._wrapped.write(safe)

    def flush(self) -> None:
        self._wrapped.flush()

    @property
    def encoding(self) -> str:
        result: str = getattr(self._wrapped, "encoding", "utf-8") or "utf-8"
        return result

    def fileno(self) -> int:
        return self._wrapped.fileno()

    def isatty(self) -> bool:
        return self._wrapped.isatty()

    @property
    def closed(self) -> bool:
        return self._wrapped.closed

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False


def get_console() -> Console:
    """Create a Rich Console that gracefully handles Unicode encoding issues.

    On some Windows environments, pywin32 wraps stdout with a tee writer that
    internally encodes via cp1252 while still reporting ``encoding='utf-8'``.
    This causes Rich to skip its ASCII box-character fallback, resulting in a
    ``UnicodeEncodeError`` when printing tables or other decorated output.

    This function wraps stdout with a safety layer that catches
    ``UnicodeEncodeError`` on write and degrades gracefully, so that
    Rich console output never crashes the caller.
    """
    return Console(file=cast(IO[str], _SafeFileWrapper(sys.stdout)))


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
