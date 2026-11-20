"""Companion to SQLite observed state covering indexes.

Revision ID: 91e2b8f3d6a4
Revises: e7f54680bce3
Create Date: 2026-10-20 00:00:00.000000

PostgreSQL's existing indexes and parallel aggregation already serve this query.
"""

revision = "91e2b8f3d6a4"
down_revision = "e7f54680bce3"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
