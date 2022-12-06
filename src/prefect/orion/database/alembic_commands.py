from functools import wraps
from pathlib import Path
from threading import Lock

import prefect

ALEMBIC_LOCK = Lock()


def with_alembic_lock(fn):
    """
    Decorator that prevents alembic commands from running concurrently.
    This is necessary because alembic uses a global configuration object
    that is not thread-safe.

    This issue occurred in https://github.com/PrefectHQ/prefect-dask/pull/50, where
    dask threads were simultaneously performing alembic upgrades, and causing
    cryptic `KeyError: 'config'` when `del globals_[attr_name]`.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        with ALEMBIC_LOCK:
            return fn(*args, **kwargs)

    return wrapper


def alembic_config():
    from alembic.config import Config

    alembic_dir = Path(prefect.orion.database.__file__).parent
    if not alembic_dir.joinpath("alembic.ini").exists():
        raise ValueError(f"Couldn't find alembic.ini at {alembic_dir}/alembic.ini")

    alembic_cfg = Config(alembic_dir / "alembic.ini")

    return alembic_cfg


@with_alembic_lock
def alembic_upgrade(revision: str = "head", dry_run: bool = False):
    """
    Run alembic upgrades on Orion database

    Args:
        revision: The revision passed to `alembic downgrade`. Defaults to 'head', upgrading all revisions.
        dry_run: Show what migrations would be made without applying them. Will emit sql statements to stdout.
    """
    # lazy import for performance
    import alembic.command

    alembic.command.upgrade(alembic_config(), revision, sql=dry_run)


@with_alembic_lock
def alembic_downgrade(revision: str = "base", dry_run: bool = False):
    """
    Run alembic downgrades on Orion database

    Args:
        revision: The revision passed to `alembic downgrade`. Defaults to 'base', downgrading all revisions.
        dry_run: Show what migrations would be made without applying them. Will emit sql statements to stdout.
    """
    # lazy import for performance
    import alembic.command

    alembic.command.downgrade(alembic_config(), revision, sql=dry_run)


@with_alembic_lock
def alembic_revision(message: str = None, autogenerate: bool = False, **kwargs):
    """
    Create a new revision file for Orion

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
def alembic_stamp(revision):
    """
    Stamp the revision table with the given revision; don't run any migrations

    Args:
        revision: The revision passed to `alembic stamp`.
    """
    # lazy import for performance
    import alembic.command

    alembic.command.stamp(alembic_config(), revision=revision)
