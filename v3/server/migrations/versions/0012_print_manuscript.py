"""原稿として出す形：見開き、ページの種類・色の種類・解像度・ノンブルの出し方、文字の一部の書式と組版、書き出しの見開きの出し方

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-08 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0012'
down_revision: Union[str, Sequence[str], None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.add_column('pages', sa.Column('page_kind', sa.String(length=16), nullable=True))
    op.add_column('pages', sa.Column('color_mode', sa.String(length=16), nullable=True))
    op.add_column('pages', sa.Column('dpi', sa.Integer(), nullable=True))
    op.add_column('pages', sa.Column('nombre_display', sa.String(length=16), nullable=True))
    op.create_table(
        'spreads',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('work_id', sa.String(length=32), nullable=False),
        sa.Column('episode_id', sa.String(length=32), nullable=False),
        sa.Column('first_page_id', sa.String(length=32), nullable=False),
        sa.Column('second_page_id', sa.String(length=32), nullable=False),
        sa.Column('image_id', sa.String(length=32), nullable=True),
        sa.Column('image_placement', JSON, nullable=True),
        sa.Column('adjustments', JSON, nullable=False),
        sa.Column('human_hand_fields', JSON, nullable=False),
        sa.Column('removed', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['work_id'], ['works.id']),
        sa.ForeignKeyConstraint(['episode_id'], ['episodes.id']),
        sa.ForeignKeyConstraint(['first_page_id'], ['pages.id']),
        sa.ForeignKeyConstraint(['second_page_id'], ['pages.id']),
        sa.ForeignKeyConstraint(['image_id'], ['image_files.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_spreads_work_id'), 'spreads', ['work_id'], unique=False)
    op.create_index(op.f('ix_spreads_episode_id'), 'spreads', ['episode_id'], unique=False)
    op.create_index(op.f('ix_spreads_first_page_id'), 'spreads', ['first_page_id'], unique=False)
    op.create_index(op.f('ix_spreads_second_page_id'), 'spreads', ['second_page_id'], unique=False)
    op.add_column('text_items', sa.Column('spans', JSON, nullable=False, server_default=sa.text("'[]'")))
    op.alter_column('text_items', 'spans', server_default=None)
    op.add_column('text_items', sa.Column('typesetting', JSON, nullable=True))
    op.alter_column('export_runs', 'dpi', existing_type=sa.Integer(), nullable=True)
    op.add_column('export_runs', sa.Column('spread_output', sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column('export_runs', 'spread_output')
    op.execute("DELETE FROM export_runs WHERE dpi IS NULL")
    op.alter_column('export_runs', 'dpi', existing_type=sa.Integer(), nullable=False)
    op.drop_column('text_items', 'typesetting')
    op.drop_column('text_items', 'spans')
    op.drop_index(op.f('ix_spreads_second_page_id'), table_name='spreads')
    op.drop_index(op.f('ix_spreads_first_page_id'), table_name='spreads')
    op.drop_index(op.f('ix_spreads_episode_id'), table_name='spreads')
    op.drop_index(op.f('ix_spreads_work_id'), table_name='spreads')
    op.drop_table('spreads')
    op.drop_column('pages', 'nombre_display')
    op.drop_column('pages', 'dpi')
    op.drop_column('pages', 'color_mode')
    op.drop_column('pages', 'page_kind')
