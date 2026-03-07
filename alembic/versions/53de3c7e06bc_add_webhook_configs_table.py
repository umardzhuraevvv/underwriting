"""Add webhook_configs table

Revision ID: 53de3c7e06bc
Revises: 1661ef4ba508
Create Date: 2026-03-07 17:20:43.773333

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53de3c7e06bc'
down_revision: Union[str, Sequence[str], None] = '1661ef4ba508'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('webhook_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('secret', sa.String(length=200), nullable=True),
    sa.Column('events', sa.String(length=500), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_webhook_configs_id'), 'webhook_configs', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_webhook_configs_id'), table_name='webhook_configs')
    op.drop_table('webhook_configs')
