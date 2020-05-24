# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import prefect
import alembic
import subprocess

import pytest
import sqlalchemy as sa
from prefect_server import api, cli, config, database
from prefect.utilities.graphql import EnumValue, with_args

# these tests can be run with pytest -m migration_test
pytestmark = [pytest.mark.migration_test]


def test_alembic_single_head():
    """
    When multiple PRs add migrations simultaneously, we can end up in a situation where
    their `down_revisions` aren't updated, resulting in multiple alembic heads unecessarily.

    This test checks for multiple heads and alerts. It should be respected unless there is a
    true reason for double heads.
    """
    current_head = subprocess.check_output(["alembic", "current"])

    # if there's a single head, the output should contain a single 12-character hash
    # followed by `(head)\n`
    assert current_head.endswith(b"(head)\n")
    assert len(current_head) == 20


async def test_full_migration_downgrade_works_with_data_in_db():
    """
    Tests that downgrade migrations work when the database has data in it
    """
    try:
        subprocess.check_output(["prefect-server", "database", "downgrade", "-y"])
    finally:
        # upgrade DB so other tests can run
        subprocess.check_output(["prefect-server", "database", "upgrade", "-y"])


@pytest.mark.parametrize("n", [1, 2, 3])
async def test_recent_migration_upgrades_work_with_data_in_db(n):
    """
    Tests that the last N upgrades work with data in the database. Note that this isn't
    perfect as we must downgrade the database to "get" to the starting point, which could delete data.

    We repeat the test twice.
    """
    try:
        for _ in range(2):
            subprocess.check_output(
                ["prefect-server", "database", "downgrade", "-n", f"-{n}", "-y"]
            )
            subprocess.check_output(
                ["prefect-server", "database", "upgrade", "-n", f"+{n}", "-y"]
            )

    finally:
        # upgrade DB so other tests can run
        subprocess.check_output(["prefect-server", "database", "upgrade", "-y"])
