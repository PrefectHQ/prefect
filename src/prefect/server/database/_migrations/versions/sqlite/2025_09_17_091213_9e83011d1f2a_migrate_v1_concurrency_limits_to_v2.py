"""Migrate V1 concurrency limits to V2

Revision ID: 9e83011d1f2a
Revises: 8bb517bae6f9
Create Date: 2025-09-17 09:12:13.171320

"""

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9e83011d1f2a"
down_revision = "8bb517bae6f9"
branch_labels = None
depends_on = None


def upgrade():
    """Migrate V1 concurrency limits to V2.

    Creates V2 limits with 'tag:' prefix and preserves active slot counts.
    The V1 records are deleted after migration since the adapter routes
    all V1 API calls to V2.
    """

    connection = op.get_bind()

    # Read all V1 limits and create corresponding V2 limits
    v1_limits = connection.execute(
        sa.text("SELECT * FROM concurrency_limit")
    ).fetchall()

    # Get the configured lease storage to create actual leases
    from prefect.server.concurrency.lease_storage import (
        get_concurrency_lease_storage,
    )

    lease_storage = get_concurrency_lease_storage()

    for v1_limit in v1_limits:
        v2_name = f"tag:{v1_limit.tag}"

        # Check if V2 limit already exists (for idempotency)
        existing = connection.execute(
            sa.text("SELECT id FROM concurrency_limit_v2 WHERE name = :name"),
            {"name": v2_name},
        ).fetchone()

        if not existing:
            # Parse active slots from JSON
            active_slots = (
                json.loads(v1_limit.active_slots) if v1_limit.active_slots else []
            )
            active_count = len(active_slots)

            # Preserve the same ID when migrating
            v2_id = v1_limit.id

            # Create V2 limit with the same ID
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
                    "active": 1,  # SQLite uses 1/0 for boolean
                    "active_slots": active_count,
                    "denied_slots": 0,
                    "decay": 0.0,  # No decay for migrated limits
                    "avg_occupancy": 600.0,  # Default 10 minutes
                    "created": v1_limit.created,
                    "updated": v1_limit.updated,
                },
            )

            # Create actual leases if we have active slots
            if active_slots:
                try:
                    from datetime import timedelta
                    from uuid import UUID

                    from prefect.server.concurrency.lease_storage import (
                        ConcurrencyLimitLeaseMetadata,
                    )

                    # Import the ConcurrencyLeaseHolder for preserving holder info
                    from prefect.types._concurrency import ConcurrencyLeaseHolder

                    async def create_leases():
                        # Create one lease for each active slot, preserving the task_run holder
                        for slot_holder_id in active_slots:
                            await lease_storage.create_lease(
                                resource_ids=[UUID(str(v2_id))],
                                ttl=timedelta(days=365 * 100),
                                metadata=ConcurrencyLimitLeaseMetadata(
                                    slots=1,
                                    holder=ConcurrencyLeaseHolder(
                                        type="task_run", id=UUID(slot_holder_id)
                                    ),
                                ),
                            )

                    # Use run_coro_as_sync to handle running async code from migration context
                    from prefect.utilities.asyncutils import run_coro_as_sync

                    run_coro_as_sync(create_leases())
                except Exception as e:
                    # Log but don't fail migration if lease creation fails
                    print(f"Warning: Could not create leases for limit {v2_id}: {e}")
                    pass

    # Delete V1 records after migration - the adapter handles all V1 API calls
    connection.execute(sa.text("DELETE FROM concurrency_limit"))


def downgrade():
    """Restore V1 limits from V2."""
    connection = op.get_bind()

    # Get all V2 limits that were migrated from V1 (have tag: prefix)
    v2_limits = connection.execute(
        sa.text("SELECT * FROM concurrency_limit_v2 WHERE name LIKE 'tag:%'")
    ).fetchall()

    # Try to get lease storage for recovering active slots
    from prefect.server.concurrency.lease_storage import (
        get_concurrency_lease_storage,
    )

    lease_storage = get_concurrency_lease_storage()

    for v2_limit in v2_limits:
        tag = v2_limit.name[4:]  # Remove 'tag:' prefix

        # Best effort: try to recover active slots from lease storage
        active_slots = []
        try:
            from uuid import UUID

            async def get_holders():
                holders = await lease_storage.list_holders_for_limit(
                    UUID(str(v2_limit.id))
                )
                return [
                    str(holder.id)
                    for _, holder in holders
                    if holder and holder.type == "task_run"
                ]

            from prefect.utilities.asyncutils import run_coro_as_sync

            active_slots = run_coro_as_sync(get_holders())
        except Exception as e:
            # Can't recover slots - that's OK, best effort
            print(f"Note: Could not recover active slots for {tag}: {e}")

        # Restore with the same ID and recovered active_slots (or empty if couldn't recover)
        connection.execute(
            sa.text("""
                INSERT INTO concurrency_limit
                (id, tag, concurrency_limit, active_slots, created, updated)
                VALUES (:id, :tag, :limit, :slots, :created, :updated)
            """),
            {
                "id": str(v2_limit.id),  # Preserve the same ID when downgrading
                "tag": tag,
                "limit": v2_limit.limit,
                "slots": json.dumps(active_slots),  # Best effort recovery from leases
                "created": v2_limit.created,
                "updated": v2_limit.updated,
            },
        )

    # Delete the V2 limits that were created from V1
    connection.execute(
        sa.text("DELETE FROM concurrency_limit_v2 WHERE name LIKE 'tag:%'")
    )
