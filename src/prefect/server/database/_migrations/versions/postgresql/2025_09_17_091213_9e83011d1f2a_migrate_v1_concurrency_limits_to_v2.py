"""Migrate V1 concurrency limits to V2

Revision ID: 9e83011d1f2a
Revises: 8bb517bae6f9
Create Date: 2025-09-17 09:12:13.171320

"""

import json
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "9e83011d1f2a"
down_revision = "3b86c5ea017a"
branch_labels = None
depends_on = None


def upgrade():
    """Migrate V1 concurrency limits to V2.

    In OSS, V1 limits store active_slots directly in the database as JSON.
    We migrate these to V2 limits with 'tag:' prefix. Active slots information
    is preserved in a temporary table for potential runtime lease creation.
    """

    connection = op.get_bind()

    # Create temporary table to preserve active slots for runtime lease creation
    op.create_table(
        "concurrency_limit_v1_active_slots",
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("active_slots", sa.JSON(), nullable=False),
        sa.Column(
            "v2_limit_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
    )

    # Read all V1 limits and create corresponding V2 limits
    v1_limits = connection.execute(
        sa.text("SELECT * FROM concurrency_limit")
    ).fetchall()

    for v1_limit in v1_limits:
        v2_name = f"tag:{v1_limit.tag}"
        v2_id = uuid4()

        # Check if V2 limit already exists (for idempotency)
        existing = connection.execute(
            sa.text("SELECT id FROM concurrency_limit_v2 WHERE name = :name"),
            {"name": v2_name},
        ).fetchone()

        if not existing:
            # Active slots in PostgreSQL are already a list/array
            active_slots = v1_limit.active_slots if v1_limit.active_slots else []
            active_count = len(active_slots)

            # Create V2 limit
            connection.execute(
                sa.text("""
                    INSERT INTO concurrency_limit_v2 
                    (id, name, "limit", active, active_slots, denied_slots,
                     slot_decay_per_second, avg_slot_occupancy_seconds, 
                     created, updated)
                    VALUES 
                    (:id, :name, :limit, :active, :active_slots, :denied_slots,
                     :decay, :avg_occupancy, :created, :updated)
                """),
                {
                    "id": str(v2_id),
                    "name": v2_name,
                    "limit": v1_limit.concurrency_limit,
                    "active": True,  # PostgreSQL uses true/false for boolean
                    "active_slots": active_count,
                    "denied_slots": 0,
                    "decay": 0.0,  # No decay for migrated limits
                    "avg_occupancy": 600.0,  # Default 10 minutes
                    "created": v1_limit.created,
                    "updated": v1_limit.updated,
                },
            )

            # Store active slots for potential runtime lease creation
            if active_slots:
                connection.execute(
                    sa.text("""
                        INSERT INTO concurrency_limit_v1_active_slots
                        (tag, active_slots, v2_limit_id)
                        VALUES (:tag, :slots, :v2_id)
                    """),
                    {
                        "tag": v1_limit.tag,
                        "slots": json.dumps(active_slots),
                        "v2_id": str(v2_id),
                    },
                )

    # Drop V1 table
    op.drop_index("uq_concurrency_limit__tag", table_name="concurrency_limit")
    op.drop_table("concurrency_limit")


def downgrade():
    """Recreate V1 table and optionally restore limits."""

    # Recreate V1 table
    op.create_table(
        "concurrency_limit",
        sa.Column("id", prefect.server.utilities.database.UUID(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False),
        sa.Column("active_slots", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create unique index
    op.create_index(
        "uq_concurrency_limit__tag", "concurrency_limit", ["tag"], unique=True
    )

    # Optionally restore V2 limits back to V1
    connection = op.get_bind()
    v2_limits = connection.execute(
        sa.text("SELECT * FROM concurrency_limit_v2 WHERE name LIKE 'tag:%'")
    ).fetchall()

    for v2_limit in v2_limits:
        tag = v2_limit.name[4:]  # Remove 'tag:' prefix

        # Try to get preserved active slots from temporary table
        preserved = connection.execute(
            sa.text(
                "SELECT active_slots FROM concurrency_limit_v1_active_slots WHERE v2_limit_id = :id"
            ),
            {"id": v2_limit.id},
        ).fetchone()

        active_slots = json.loads(preserved.active_slots) if preserved else []

        connection.execute(
            sa.text("""
                INSERT INTO concurrency_limit
                (id, tag, concurrency_limit, active_slots, created, updated)
                VALUES (:id, :tag, :limit, :slots, :created, :updated)
            """),
            {
                "id": str(uuid4()),
                "tag": tag,
                "limit": v2_limit.limit,
                "slots": json.dumps(active_slots),
                "created": v2_limit.created,
                "updated": v2_limit.updated,
            },
        )

    # Clean up temporary table
    op.drop_table("concurrency_limit_v1_active_slots")
