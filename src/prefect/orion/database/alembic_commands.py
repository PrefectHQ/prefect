from pathlib import Path

import prefect


def alembic_config():
    from alembic.config import Config

    alembic_dir = Path(prefect.orion.database.__file__).parent
    if not alembic_dir.joinpath("alembic.ini").exists():
        raise ValueError(f"Couldn't find alembic.ini at {alembic_dir}/alembic.ini")

    alembic_cfg = Config(alembic_dir / "alembic.ini")

    return alembic_cfg


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


def alembic_stamp(revision):
    """
    Stamp the revision table with the given revision; don't run any migrations

    Args:
        revision: The revision passed to `alembic stamp`.
    """
    # lazy import for performance
    import alembic.command

    alembic.command.stamp(alembic_config(), revision=revision)
