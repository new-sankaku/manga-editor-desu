"""ハーネス：候補の中身と直させた元・1話の構成の正本・知らせ（アプリの中の一覧・外への送り先・届けた記録）

Revision ID: 0030
Revises: 0013
Create Date: 2026-10-08 20:00:00

番号は並行して作っている 0020 番台（残りのサーバーの口）の後に置く。0020 番台と合わせるときは、down_revision を
その最後の番号へ付け替える（ここで足す表と列は 0020 番台と重ならない）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0030'
down_revision: Union[str, Sequence[str], None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

J = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    # 文の候補（企画・構成・設定資料・総合の作業）の中身と、作画の候補の作り方（使った入力・依頼）と直させた元
    op.add_column('harness_candidates', sa.Column('content', J))
    op.add_column('harness_candidates', sa.Column('made_with', J))
    op.add_column('harness_candidates', sa.Column('fixed_from', sa.String(32), sa.ForeignKey('harness_candidates.id')))
    op.add_column('harness_candidates', sa.Column('fix_round', sa.Integer(), nullable=False, server_default='0'))

    # 1話の構成（S1 の正本）。ページの割り当てと見せ場
    op.create_table(
        'episode_outlines',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('work_id', sa.String(32), sa.ForeignKey('works.id'), nullable=False, index=True),
        sa.Column('episode_id', sa.String(32), sa.ForeignKey('episodes.id'), nullable=False, unique=True),
        sa.Column('outline', J, nullable=False),
        sa.Column('made_by_kind', sa.String(8), nullable=False),
        sa.Column('made_by_id', sa.String(128), nullable=False),
        sa.Column('human_hand_fields', J, nullable=False, server_default='[]'),
        sa.Column('removed', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('updated_at', TS, server_default=sa.func.now(), nullable=False),
    )

    # 知らせ（決めごと 17章）。アプリの中の一覧の行
    op.create_table(
        'harness_notifications',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('work_id', sa.String(32), sa.ForeignKey('works.id'), nullable=False, index=True),
        sa.Column('kind', sa.String(32), nullable=False),
        sa.Column('level', sa.String(16), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', J, nullable=False),
        sa.Column('stage_run_id', sa.String(32), sa.ForeignKey('harness_stage_runs.id')),
        sa.Column('unit_id', sa.String(32), sa.ForeignKey('harness_units.id')),
        sa.Column('event_id', sa.BigInteger()),
        sa.Column('dedupe_key', sa.String(160), unique=True),
        sa.Column('read_at', TS),
        sa.Column('read_by', sa.String(128)),
        sa.Column('created_at', TS, server_default=sa.func.now(), nullable=False),
    )
    # 作品ごとの知らせの決まり（どの種類を出すか・外への送り先・判断待ちを上げる回数）
    op.create_table(
        'harness_notification_settings',
        sa.Column('work_id', sa.String(32), sa.ForeignKey('works.id'), primary_key=True),
        sa.Column('kinds', J, nullable=False),
        sa.Column('webhooks', J, nullable=False, server_default='[]'),
        sa.Column('escalate_after_notices', sa.Integer()),
        sa.Column('budget_near_ratio', sa.Float()),
        sa.Column('updated_by', sa.String(128), nullable=False),
        sa.Column('updated_at', TS, server_default=sa.func.now(), nullable=False),
    )
    # 外へ届けた記録（送り先ごと）
    op.create_table(
        'harness_notification_deliveries',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('notification_id', sa.String(32), sa.ForeignKey('harness_notifications.id'), nullable=False,
                  index=True),
        sa.Column('channel', sa.String(16), nullable=False),
        sa.Column('target', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text()),
        sa.Column('next_at', TS, server_default=sa.func.now(), nullable=False),
        sa.Column('sent_at', TS),
        sa.Column('created_at', TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_harness_notification_deliveries_pending', 'harness_notification_deliveries',
                    ['status', 'next_at'])


def downgrade() -> None:
    op.drop_index('ix_harness_notification_deliveries_pending', 'harness_notification_deliveries')
    for t in ('harness_notification_deliveries', 'harness_notification_settings', 'harness_notifications',
              'episode_outlines'):
        op.drop_table(t)
    for c in ('fix_round', 'fixed_from', 'made_with', 'content'):
        op.drop_column('harness_candidates', c)
