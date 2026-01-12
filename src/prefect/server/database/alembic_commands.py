import warnings
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Callable, Iterator, Optional, Union

from sqlalchemy.exc import SAWarning
from typing_extensions import ParamSpec, TypeVar

import prefect.server.database
from prefect.server.utilities.database import get_dialect
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL

if TYPE_CHECKING:
    from alembic.config import Config


P = ParamSpec("P")
R = TypeVar("R", infer_variance=True)

# Thread-level lock for SQLite (single process)
ALEMBIC_LOCK = Lock()

# Advisory lock keys for PostgreSQL (cross-process)
# Using fixed integer keys for the advisory locks
ALEMBIC_ADVISORY_LOCK_KEY = 0x50524546  # "PREF" in hex - for migrations
BLOCK_REGISTRATION_ADVISORY_LOCK_KEY = (
    0x424C4B52  # "BLKR" in hex - for block registration
)


@contextmanager
def postgres_advisory_lock(lock_key: int) -> Iterator[None]:
    """
    Acquire a PostgreSQL advisory lock to coordinate operations across processes.

    This uses pg_advisory_lock which blocks until the lock is acquired,
    ensuring only one process runs the protected operation at a time.

    Args:
        lock_key: A unique integer key identifying the lock to acquire.
    """
    import asyncio

    import asyncpg

    async def acquire_and_hold_lock() -> asyncpg.Connection:
        connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
        # Convert SQLAlchemy URL to asyncpg format
        # postgresql+asyncpg://user:pass@host/db -> postgresql://user:pass@host/db
        dsn = connection_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        await conn.execute(f"SELECT pg_advisory_lock({lock_key})")
        return conn

    async def release_lock(conn: asyncpg.Connection) -> None:
        try:
            await conn.execute(f"SELECT pg_advisory_unlock({lock_key})")
        finally:
            await conn.close()

    # Get or create event loop for running async code
    try:
        asyncio.get_running_loop()
        # If we're in an async context, we need to run in a thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            conn = executor.submit(asyncio.run, acquire_and_hold_lock()).result()
            try:
                yield
            finally:
                executor.submit(asyncio.run, release_lock(conn)).result()
    except RuntimeError:
        # No running event loop, we can use asyncio.run directly
        conn = asyncio.run(acquire_and_hold_lock())
        try:
            yield
        finally:
            asyncio.run(release_lock(conn))


def with_alembic_lock(fn: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator that prevents alembic commands from running concurrently.
    This is necessary because alembic uses a global configuration object
    that is not thread-safe.

    For SQLite, uses a threading.Lock() which works within a single process.
    For PostgreSQL, uses advisory locks which work across multiple processes,
    enabling safe concurrent startup of multi-worker servers.

    This issue occurred in https://github.com/PrefectHQ/prefect-dask/pull/50, where
    dask threads were simultaneously performing alembic upgrades, and causing
    cryptic `KeyError: 'config'` when `del globals_[attr_name]`.
    """

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
        dialect = get_dialect(connection_url)

        if dialect.name == "postgresql":
            # Use PostgreSQL advisory locks for cross-process coordination
            with postgres_advisory_lock(ALEMBIC_ADVISORY_LOCK_KEY):
                with ALEMBIC_LOCK:
                    return fn(*args, **kwargs)
        else:
            # Use threading lock for SQLite (single process only)
            with ALEMBIC_LOCK:
                return fn(*args, **kwargs)

    return wrapper


def alembic_config() -> "Config":
    from alembic.config import Config

    alembic_dir = Path(prefect.server.database.__file__).parent
    if not alembic_dir.joinpath("alembic.ini").exists():
        raise ValueError(f"Couldn't find alembic.ini at {alembic_dir}/alembic.ini")

    alembic_cfg = Config(alembic_dir / "alembic.ini")

    return alembic_cfg


@with_alembic_lock
def alembic_upgrade(revision: str = "head", dry_run: bool = False) -> None:
    """
    Run alembic upgrades on Prefect REST API database

    Args:
        revision: The revision passed to `alembic downgrade`. Defaults to 'head', upgrading all revisions.
        dry_run: Show what migrations would be made without applying them. Will emit sql statements to stdout.
    """
    # lazy import for performance
    import alembic.command

    # don't display reflection warnings that pop up during schema migrations
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipped unsupported reflection of expression-based index",
            category=SAWarning,
        )
        alembic.command.upgrade(alembic_config(), revision, sql=dry_run)


@with_alembic_lock
def alembic_downgrade(revision: str = "-1", dry_run: bool = False) -> None:
    """
    Run alembic downgrades on Prefect REST API database

    Args:
        revision: The revision passed to `alembic downgrade`. Defaults to 'base', downgrading all revisions.
        dry_run: Show what migrations would be made without applying them. Will emit sql statements to stdout.
    """
    # lazy import for performance
    import alembic.command

    alembic.command.downgrade(alembic_config(), revision, sql=dry_run)


@with_alembic_lock
def alembic_revision(
    message: Optional[str] = None, autogenerate: bool = False, **kwargs: Any
) -> None:
    """
    Create a new revision file for the database.

    Args:
        message: string message to apply to the revision.
        autogenerate: whether or not to autogenerate the script from the database.
    """
    # lazy import for performance
    import alembic.command

    alembic.command.revision(
        alembic_config(), message=message, autogenerate=autogenerate, **kwargs
    )


@with_alembic_lock
def alembic_stamp(revision: Union[str, list[str], tuple[str, ...]]) -> None:
    """
    Stamp the revision table with the given revision; don't run any migrations

    Args:
        revision: The revision passed to `alembic stamp`.
    """
    # lazy import for performance
    import alembic.command

    alembic.command.stamp(alembic_config(), revision=revision)
