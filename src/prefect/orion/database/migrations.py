import alembic

from pathlib import Path

import prefect
import prefect.orion


def alembic_config():
    from alembic.config import Config

    alembic_dir = Path(prefect.__file__).parents[2]
    if not alembic_dir.joinpath("alembic.ini").exists():
        raise ValueError(f"Couldn't find alembic.ini at {alembic_dir}/alembic.ini")

    alembic_cfg = Config(alembic_dir / "alembic.ini")

    return alembic_cfg


def alembic_upgrade(n: str = None, versions_dir: str = None):
    """
    Run alembic upgrades on Orion database

    Args:
        n: The argument to `alembic upgrade`. If not provided, runs all.
        versions_dir: The path to versions directory
    """
    # lazy import for performance
    import alembic.command

    alembic.command.upgrade(
        alembic_config(),
        f"{n}" if n else "heads",
    )


def alembic_downgrade(n: str = None, versions_dir: str = None):
    """
    Run alembic downgrades on Orion database

    Args:
        n: The argument to `alembic downgrade`. If not provided, runs all.
    """
    # lazy import for performance
    import alembic.command

    alembic.command.downgrade(
        alembic_config(),
        f"{n}" if n else "base",
    )
