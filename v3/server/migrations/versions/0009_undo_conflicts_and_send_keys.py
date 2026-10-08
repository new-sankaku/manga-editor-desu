"""出来事に変えた項目を残す・取り消しのぶつかりの記録・送る前に残す呼び出しの鍵と受け取った答え

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-08 18:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0009'
down_revision: str | Sequence[str] | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.add_column('events', sa.Column('field_changes', _json(), nullable=True))
    op.create_table(
        'undo_conflicts',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('work_id', sa.String(length=32), nullable=False),
        sa.Column('event_id', sa.String(length=32), nullable=False),
        sa.Column('actor_kind', sa.String(length=8), nullable=False),
        sa.Column('actor_id', sa.String(length=128), nullable=False),
        sa.Column('conflicts', _json(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['work_id'], ['works.id']),
        sa.ForeignKeyConstraint(['event_id'], ['events.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_undo_conflicts_work_id', 'undo_conflicts', ['work_id'])
    op.create_index('ix_undo_conflicts_event_id', 'undo_conflicts', ['event_id'])
    op.add_column('call_logs', sa.Column('idempotency_key', sa.String(length=80), nullable=True))
    op.create_unique_constraint('uq_call_logs_idempotency_key', 'call_logs', ['idempotency_key'])
    op.add_column('call_logs', sa.Column('result', _json(), nullable=True))


def downgrade() -> None:
    op.drop_column('call_logs', 'result')
    op.drop_constraint('uq_call_logs_idempotency_key', 'call_logs', type_='unique')
    op.drop_column('call_logs', 'idempotency_key')
    op.drop_index('ix_undo_conflicts_event_id', table_name='undo_conflicts')
    op.drop_index('ix_undo_conflicts_work_id', table_name='undo_conflicts')
    op.drop_table('undo_conflicts')
    op.drop_column('events', 'field_changes')
