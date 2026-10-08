"""ComfyUI の待ちの上限（秒）と、送る前の選択肢の確認の切り替え

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('service_processes', sa.Column('comfy_wait_seconds', sa.Integer(), nullable=True))
    op.add_column('service_processes', sa.Column('comfy_check_choices', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('service_processes', 'comfy_check_choices')
    op.drop_column('service_processes', 'comfy_wait_seconds')
