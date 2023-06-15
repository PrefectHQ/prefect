"""Add infra_overrides to FlowRun table

Revision ID: 18eb8aa2afa8
Revises: 15f5083c16bd
Create Date: 2023-06-15 17:34:35.672335

"""
from alembic import op
import sqlalchemy as sa
import prefect
from sqlalchemy import Text

# revision identifiers, used by Alembic.
revision = '18eb8aa2afa8'
down_revision = '15f5083c16bd'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('flow_run', sa.Column('infra_overrides', prefect.server.utilities.database.JSON(astext_type=Text()), server_default="{}", nullable=False))

def downgrade():
    op.drop_column('flow_run', 'infra_overrides')
