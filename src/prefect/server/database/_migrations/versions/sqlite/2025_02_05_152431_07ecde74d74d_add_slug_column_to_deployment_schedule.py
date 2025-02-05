"""Add slug column to deployment_schedule

Revision ID: 07ecde74d74d
Revises: 67f886da208e
Create Date: 2025-02-05 15:24:31.503016

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "07ecde74d74d"
down_revision = "67f886da208e"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.add_column(
            "deployment_schedule",
            sa.Column("slug", sa.String, nullable=True),
        )

        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_deployment_schedule__slug
            ON deployment_schedule(slug)
            """
        )

        op.execute(
            """
            CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS
            ix_deployment_schedule__deployment_id__slug
            ON deployment_schedule(deployment_id, slug)
            WHERE slug IS NOT NULL;
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS ix_deployment_schedule__deployment_id__slug
            """
        )

        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS ix_deployment_schedule__slug
            """
        )

        op.drop_column("deployment_schedule", "slug")
