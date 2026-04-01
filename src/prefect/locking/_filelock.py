"""Internal cross-platform file lock using OS-level locking primitives.

Uses fcntl.flock() on Unix and msvcrt.locking() on Windows. The lock is
automatically released when the process exits or crashes, preventing stale
lock files.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class FileLock:
    """A cross-platform file lock using OS-level locking primitives.

    Can be used as a synchronous context manager or with the async
    aacquire/release pair.

    Args:
        path: Path to the lock file.
        timeout: Maximum seconds to wait for lock acquisition.
            Use -1 to wait indefinitely. Defaults to -1.
        poll_interval: Seconds between non-blocking lock attempts.
            Defaults to 0.05.
    """

    def __init__(
        self,
        path: str | Path,
        timeout: float = -1,
        poll_interval: float = 0.05,
    ) -> None:
        self._path = str(path)
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._fd: int | None = None

    def acquire(self) -> None:
        """Acquire the file lock, blocking until available or timeout."""
        self._fd = os.open(self._path, os.O_CREAT | os.O_RDWR)
        start = time.monotonic()
        while True:
            try:
                _lock_fd(self._fd)
                return
            except OSError:
                elapsed = time.monotonic() - start
                if self._timeout >= 0 and elapsed >= self._timeout:
                    os.close(self._fd)
                    self._fd = None
                    raise TimeoutError(
                        f"Failed to acquire lock on {self._path!r}"
                        f" within {self._timeout}s"
                    )
                time.sleep(self._poll_interval)

    async def aacquire(self) -> None:
        """Acquire the file lock without blocking the event loop."""
        self._fd = os.open(self._path, os.O_CREAT | os.O_RDWR)
        start = time.monotonic()
        while True:
            try:
                _lock_fd(self._fd)
                return
            except OSError:
                elapsed = time.monotonic() - start
                if self._timeout >= 0 and elapsed >= self._timeout:
                    os.close(self._fd)
                    self._fd = None
                    raise TimeoutError(
                        f"Failed to acquire lock on {self._path!r}"
                        f" within {self._timeout}s"
                    )
                await asyncio.sleep(self._poll_interval)

    def release(self) -> None:
        """Release the file lock."""
        if self._fd is not None:
            _unlock_fd(self._fd)
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()

    def __del__(self) -> None:
        self.release()


def _lock_fd(fd: int) -> None:
    """Acquire an exclusive non-blocking lock on a file descriptor."""
    if sys.platform == "win32":
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_fd(fd: int) -> None:
    """Release the lock on a file descriptor."""
    if sys.platform == "win32":
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
