"""AIハーネス：工程の実行・作業・段・候補・出来事・古い印・見た位置・送信の進み具合

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-08 18:00:00

番号は並行して作っている 0009〜0012（取り消しの食い違いと送信の鍵・ペン・翻訳と確認・印刷の原稿）の後に置く。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0013'
down_revision: Union[str, Sequence[str], None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

J = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        'harness_stage_runs',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('work_id', sa.String(32), sa.ForeignKey('works.id'), nullable=False, index=True),
        sa.Column('episode_id', sa.String(32), sa.ForeignKey('episodes.id'), nullable=False, index=True),
        sa.Column('stage', sa.String(4), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('requested_by', sa.String(128), nullable=False),
        sa.Column('limits', J, nullable=False),
        sa.Column('spec', J, nullable=False),
        sa.Column('stage_check', J),
        sa.Column('stop_reason', sa.Text()),
        sa.Column('next_stage_run_id', sa.String(32)),
        sa.Column('workflow_id', sa.String(128)),
        sa.Column('created_at', TS, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'harness_units',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('stage_run_id', sa.String(32), sa.ForeignKey('harness_stage_runs.id'), nullable=False, index=True),
        sa.Column('work_id', sa.String(32), sa.ForeignKey('works.id'), nullable=False, index=True),
        sa.Column('stage', sa.String(4), nullable=False),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('target_kind', sa.String(16), nullable=False),
        sa.Column('target_id', sa.String(32), nullable=False),
        sa.Column('page_id', sa.String(32), sa.ForeignKey('pages.id'), index=True),
        sa.Column('completion', J, nullable=False),
        sa.Column('limits', J, nullable=False),
        sa.Column('spec', J, nullable=False),
        sa.Column('requested_by', sa.String(128), nullable=False),
        sa.Column('upstream_used', J, nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('current_step', sa.String(16)),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('cost_used', sa.Numeric(12, 4), nullable=False),
        sa.Column('seconds_used', sa.Float(), nullable=False),
        sa.Column('stop_reason', sa.Text()),
        sa.Column('review', J),
        sa.Column('result', J),
        sa.Column('live', J),
        sa.Column('rerun_of', sa.String(32)),
        sa.Column('workflow_id', sa.String(128)),
        sa.Column('created_at', TS, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', TS, server_default=sa.func.now(), nullable=False),
        sa.Column('finished_at', TS),
    )
    op.create_table(
        'harness_steps',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('unit_id', sa.String(32), sa.ForeignKey('harness_units.id'), nullable=False, index=True),
        sa.Column('step', sa.String(16), nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('started_at', TS, nullable=False),
        sa.Column('finished_at', TS),
        sa.Column('detail', J),
        sa.Column('cost', sa.Numeric(12, 4), nullable=False),
    )
    op.create_table(
        'harness_candidates',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('unit_id', sa.String(32), sa.ForeignKey('harness_units.id'), nullable=False, index=True),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('k_index', sa.Integer(), nullable=False),
        sa.Column('harness_key', sa.String(128), nullable=False, unique=True),
        sa.Column('job_id', sa.String(32), sa.ForeignKey('jobs.id')),
        sa.Column('image_id', sa.String(32), sa.ForeignKey('image_files.id')),
        sa.Column('proposal_id', sa.String(32), sa.ForeignKey('name_proposals.id')),
        sa.Column('seed', sa.BigInteger()),
        sa.Column('prompt', sa.Text()),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('check', J),
        sa.Column('check_verdict', sa.String(8)),
        sa.Column('evaluation', J),
        sa.Column('picked', sa.Boolean(), nullable=False),
        sa.Column('dropped_reason', sa.Text()),
        sa.Column('created_at', TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'harness_events',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('work_id', sa.String(32), sa.ForeignKey('works.id'), nullable=False, index=True),
        sa.Column('stage_run_id', sa.String(32), index=True),
        sa.Column('unit_id', sa.String(32), index=True),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('payload', J, nullable=False),
        sa.Column('created_at', TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'harness_stale_marks',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('work_id', sa.String(32), sa.ForeignKey('works.id'), nullable=False, index=True),
        sa.Column('unit_id', sa.String(32), sa.ForeignKey('harness_units.id'), nullable=False, index=True),
        sa.Column('upstream_key', sa.String(128), nullable=False),
        sa.Column('used_version', sa.String(64)),
        sa.Column('current_version', sa.String(64)),
        sa.Column('effect', sa.String(8), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('created_at', TS, server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', TS),
        sa.UniqueConstraint('unit_id', 'upstream_key', 'current_version'),
    )
    op.create_table(
        'harness_watch_cursors',
        sa.Column('work_id', sa.String(32), sa.ForeignKey('works.id'), primary_key=True),
        sa.Column('last_seq', sa.BigInteger(), nullable=False),
    )
    op.create_table(
        'service_call_progress',
        sa.Column('progress_key', sa.String(64), primary_key=True),
        sa.Column('prompt_id', sa.String(64)),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('value', sa.Integer()),
        sa.Column('max', sa.Integer()),
        sa.Column('preview_media_type', sa.String(32)),
        sa.Column('preview_b64', sa.Text()),
        sa.Column('updated_at', TS, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    for t in ('service_call_progress', 'harness_watch_cursors', 'harness_stale_marks', 'harness_events',
              'harness_candidates', 'harness_steps', 'harness_units', 'harness_stage_runs'):
        op.drop_table(t)
