"""Internal cross-platform file lock using lock file creation.

Uses the existence of a lock file to indicate the lock is held, following
the same pattern as FileSystemLockManager. The lock file is created
atomically and removed on release. No OS-specific locking primitives are
required.

The owning process's PID is written to the lock file so that stale locks
left behind by crashed processes can be detected and recovered.
"""

import asyncio
import os
import time
from pathlib import Path


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        # PermissionError means the process exists but we can't signal it
        return True
    return True


def _remove_stale_lock(path: Path) -> None:
    """Remove the lock file if the owning process is no longer alive."""
    try:
        contents = path.read_text().strip()
        pid = int(contents)
    except (FileNotFoundError, ValueError, OSError):
        return
    if not _is_pid_alive(pid):
        path.unlink(missing_ok=True)


def _write_lock(path: Path) -> None:
    """Atomically create the lock file and write the current PID."""
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
    finally:
        os.close(fd)


class FileLock:
    """A cross-platform file lock using lock file existence.

    Can be used as a synchronous context manager or with the async
    aacquire/release pair. The lock file stores the owning process's
    PID so that stale locks from crashed processes are automatically
    recovered.

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
                _write_lock(self._path)
                self._locked = True
                return
            except FileExistsError:
                _remove_stale_lock(self._path)
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
                _write_lock(self._path)
                self._locked = True
                return
            except FileExistsError:
                _remove_stale_lock(self._path)
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
