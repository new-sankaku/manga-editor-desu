"""出来事に、その操作で置いた判断待ちを残す

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-08 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: str | Sequence[str] | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('events', sa.Column('held_changes', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()),
                                                                             'postgresql'), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('events', 'held_changes')
