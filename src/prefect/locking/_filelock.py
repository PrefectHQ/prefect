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
import sys
import tempfile
import time
from pathlib import Path


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is still running.

    Uses `os.kill(pid, 0)` on Unix (harmless signal-0 probe).  On Windows
    `os.kill` terminates the target process, so we use
    `kernel32.OpenProcess` instead.
    """
    if sys.platform == "win32":
        import ctypes

        _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
            _PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
            return True
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        # PermissionError means the process exists but we can't signal it
        return True
    return True


_STALE_EMPTY_THRESHOLD = 5  # seconds before an empty/malformed lock is stale


def _remove_stale_lock(path: Path) -> None:
    """Remove the lock file if the owning process is no longer alive.

    For empty or malformed lock files (e.g. from a writer that crashed
    between creating the file and writing the PID), the file's mtime is
    checked: if it was last modified more than _STALE_EMPTY_THRESHOLD
    seconds ago the writer must have crashed, so the file is removed.
    If the mtime is recent the writer may still be running, so the file
    is left alone and the poll loop will retry.

    To avoid a TOCTOU race where another waiter removes the stale file
    and acquires a new lock between our read and our unlink, we record
    the file's inode before deciding it is stale and verify it has not
    changed before unlinking.
    """
    try:
        st = os.stat(str(path))
        contents = path.read_text().strip()
    except (FileNotFoundError, OSError):
        return

    original_ino = st.st_ino

    if not contents:
        # Empty file -- check mtime to decide if the writer crashed.
        _remove_if_same(path, original_ino, st.st_mtime)
        return

    try:
        pid = int(contents)
    except ValueError:
        # Malformed content -- check mtime to decide if the writer crashed.
        _remove_if_same(path, original_ino, st.st_mtime)
        return

    if not _is_pid_alive(pid):
        _unlink_if_same_inode(path, original_ino)


def _remove_if_same(path: Path, original_ino: int, mtime: float) -> None:
    """Remove *path* if mtime is stale and the inode has not changed."""
    if time.time() - mtime > _STALE_EMPTY_THRESHOLD:
        _unlink_if_same_inode(path, original_ino)


def _unlink_if_same_inode(path: Path, expected_ino: int) -> None:
    """Unlink *path* only if its current inode matches *expected_ino*.

    This prevents removing a fresh lock file that was created by another
    process between our staleness check and the unlink call.
    """
    try:
        current_st = os.stat(str(path))
    except (FileNotFoundError, OSError):
        return
    if current_st.st_ino == expected_ino:
        path.unlink(missing_ok=True)


def _write_lock(path: Path) -> None:
    """Atomically create the lock file with the current PID.

    Writes the PID to a temporary file in the same directory and then
    uses `os.rename` (atomic on POSIX, atomic on Windows for same
    volume) to move it into place.  This guarantees the lock file is
    never visible in an empty or partial state, which prevents a
    concurrent `_remove_stale_lock` from falsely treating it as stale.

    Raises `FileExistsError` if the lock file already exists (via
    `os.link` on POSIX for true atomic create-or-fail, or
    `os.open(O_CREAT | O_EXCL)` as a fallback on filesystems without
    hard-link support).
    """
    # Ensure the parent directory exists so that mkstemp and the lock
    # file can be created even when the storage base path is fresh.
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write PID to a temp file in the same directory so rename stays
    # on the same filesystem.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".lock_")
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        fd = -1  # mark as closed
        # Use os.link (hard link) to atomically claim the lock path.
        # If the target already exists, this raises FileExistsError.
        try:
            os.link(tmp, str(path))
        except FileExistsError:
            raise
        except OSError:
            # Fallback for filesystems that don't support hard links
            # (e.g. some Windows or network mounts): use O_CREAT|O_EXCL
            # which is atomic on all POSIX and Windows filesystems.
            try:
                excl_fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                raise
            try:
                os.write(excl_fd, str(os.getpid()).encode())
            finally:
                os.close(excl_fd)
            return
    finally:
        if fd >= 0:
            os.close(fd)
        # Always clean up the temp file (link created a second entry)
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


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
