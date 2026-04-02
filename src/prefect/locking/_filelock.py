"""Internal cross-platform file lock using lock file creation.

Uses the existence of a lock file to indicate the lock is held, following
the same pattern as FileSystemLockManager. The lock file is created
atomically and removed on release. No OS-specific locking primitives are
required.
"""

import asyncio
import time
from pathlib import Path


class FileLock:
    """A cross-platform file lock using lock file existence.

    Can be used as a synchronous context manager or with the async
    aacquire/release pair.

    Args:
        path: Path to the lock file.
        timeout: Maximum seconds to wait for lock acquisition.
            Use -1 to wait indefinitely. Defaults to -1.
        poll_interval: Seconds between lock attempts.
            Defaults to 0.1.
    """

    def __init__(
        self,
        path: str | Path,
        timeout: float = -1,
        poll_interval: float = 0.1,
    ) -> None:
        self._path = Path(path)
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._locked = False

    def acquire(self) -> None:
        """Acquire the file lock, blocking until available or timeout."""
        start = time.monotonic()
        while True:
            try:
                self._path.touch(exist_ok=False)
                self._locked = True
                return
            except FileExistsError:
                elapsed = time.monotonic() - start
                if self._timeout >= 0 and elapsed >= self._timeout:
                    raise TimeoutError(
                        f"Failed to acquire lock on {str(self._path)!r}"
                        f" within {self._timeout}s"
                    )
                time.sleep(self._poll_interval)

    async def aacquire(self) -> None:
        """Acquire the file lock without blocking the event loop."""
        start = time.monotonic()
        while True:
            try:
                self._path.touch(exist_ok=False)
                self._locked = True
                return
            except FileExistsError:
                elapsed = time.monotonic() - start
                if self._timeout >= 0 and elapsed >= self._timeout:
                    raise TimeoutError(
                        f"Failed to acquire lock on {str(self._path)!r}"
                        f" within {self._timeout}s"
                    )
                await asyncio.sleep(self._poll_interval)

    def release(self) -> None:
        """Release the file lock."""
        if self._locked:
            self._path.unlink(missing_ok=True)
            self._locked = False

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()

    def __del__(self) -> None:
        self.release()
