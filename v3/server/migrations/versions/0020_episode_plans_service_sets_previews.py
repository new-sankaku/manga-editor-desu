"""話ごとの構成と伏線・生成サービスの組と比べ・ページの下見の絵の控え・書き出し終えたページ

Revision ID: 0020
Revises: 0013
Create Date: 2026-10-08 07:17:14.212133

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0020'
down_revision: str | Sequence[str] | None = '0013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('service_sets',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('routes', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('created_by', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('episode_plans',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('work_id', sa.String(length=32), nullable=False),
    sa.Column('episode_id', sa.String(length=32), nullable=False),
    sa.Column('synopsis', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('cast_entry_ids', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('generation_defaults', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('carried_from_episode_id', sa.String(length=32), nullable=True),
    sa.Column('human_hand_fields', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['carried_from_episode_id'], ['episodes.id'], ),
    sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ),
    sa.ForeignKeyConstraint(['work_id'], ['works.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('episode_id')
    )
    op.create_index(op.f('ix_episode_plans_work_id'), 'episode_plans', ['work_id'], unique=False)
    op.create_table('foreshadowings',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('work_id', sa.String(length=32), nullable=False),
    sa.Column('planted_episode_id', sa.String(length=32), nullable=False),
    sa.Column('payoff_episode_id', sa.String(length=32), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('human_hand_fields', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('removed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['payoff_episode_id'], ['episodes.id'], ),
    sa.ForeignKeyConstraint(['planted_episode_id'], ['episodes.id'], ),
    sa.ForeignKeyConstraint(['work_id'], ['works.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_foreshadowings_planted_episode_id'), 'foreshadowings', ['planted_episode_id'], unique=False)
    op.create_index(op.f('ix_foreshadowings_work_id'), 'foreshadowings', ['work_id'], unique=False)
    op.create_table('page_previews',
    sa.Column('page_id', sa.String(length=32), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('work_id', sa.String(length=32), nullable=False),
    sa.Column('content_key', sa.String(length=64), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['page_id'], ['pages.id'], ),
    sa.ForeignKeyConstraint(['work_id'], ['works.id'], ),
    sa.PrimaryKeyConstraint('page_id', 'size')
    )
    op.create_index(op.f('ix_page_previews_work_id'), 'page_previews', ['work_id'], unique=False)
    op.create_table('service_comparisons',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('work_id', sa.String(length=32), nullable=False),
    sa.Column('process', sa.String(length=64), nullable=False),
    sa.Column('page_id', sa.String(length=32), nullable=True),
    sa.Column('request', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('jobs', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('requested_by', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['page_id'], ['pages.id'], ),
    sa.ForeignKeyConstraint(['work_id'], ['works.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_service_comparisons_work_id'), 'service_comparisons', ['work_id'], unique=False)
    op.add_column('export_runs', sa.Column('done_page_ids', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default='[]', nullable=False))


def downgrade() -> None:
    op.drop_column('export_runs', 'done_page_ids')
    op.drop_index(op.f('ix_service_comparisons_work_id'), table_name='service_comparisons')
    op.drop_table('service_comparisons')
    op.drop_index(op.f('ix_page_previews_work_id'), table_name='page_previews')
    op.drop_table('page_previews')
    op.drop_index(op.f('ix_foreshadowings_work_id'), table_name='foreshadowings')
    op.drop_index(op.f('ix_foreshadowings_planted_episode_id'), table_name='foreshadowings')
    op.drop_table('foreshadowings')
    op.drop_index(op.f('ix_episode_plans_work_id'), table_name='episode_plans')
    op.drop_table('episode_plans')
    op.drop_table('service_sets')
