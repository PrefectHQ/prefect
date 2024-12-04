"""Migrate artifact data to artifact_collection table

Revision ID: 2dbcec43c857
Revises: 3d46e23593d6
Create Date: 2023-04-06 12:26:59.799863

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2dbcec43c857"
down_revision = "3d46e23593d6"
branch_labels = None
depends_on = None


def upgrade():
    """
    A data-only migration that populates flow_run_id, task_run_id, type, description, and metadata_ columns
    for artifact_collection table.
    """
    op.execute("PRAGMA foreign_keys=OFF")

    batch_size = 500
    offset = 0

    update_artifact_collection_table = """
        WITH artifact_collection_cte AS (
            SELECT * FROM artifact_collection WHERE id = :id
        )
        UPDATE artifact_collection
        SET data = artifact.data,
            description = artifact.description,
            flow_run_id = artifact.flow_run_id,
            task_run_id = artifact.task_run_id,
            type = artifact.type,
            metadata_ = artifact.metadata_
        FROM artifact, artifact_collection_cte
        WHERE artifact_collection.latest_id = artifact.id
        AND artifact.id = artifact_collection_cte.latest_id;
    """

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        while True:
            select_artifact_collection_cte = f"""
                SELECT * from artifact_collection ORDER BY id LIMIT {batch_size} OFFSET {offset};
            """

            # Get the next batch of rows to update
            selected_artifact_collections = conn.execute(
                sa.text(select_artifact_collection_cte)
            ).fetchall()
            if not selected_artifact_collections:
                break

            for row in selected_artifact_collections:
                id_to_update = row[0]
                conn.execute(
                    sa.text(update_artifact_collection_table), {"id": id_to_update}
                )
                offset += batch_size

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    """
    Data-only migration, no action needed.
    """
