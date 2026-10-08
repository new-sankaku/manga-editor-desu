"""画像生成の処理の中身（つなぎ先と処理の組ごと）と、候補を却下した印

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-08 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0008'
down_revision: str | Sequence[str] | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('service_processes', sa.Column(
        'comfy_graph_settings', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
        nullable=True))
    op.add_column('image_files', sa.Column('discarded', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('image_files', 'discarded')
    op.drop_column('service_processes', 'comfy_graph_settings')
