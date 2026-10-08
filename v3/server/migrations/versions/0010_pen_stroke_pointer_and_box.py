"""ペンの線に、描いた機器（pointer_type）と外接の箱（消しゴムの索引）を足す

筆圧は点の中の値なので、表の形は変えない（null を許すのは hand_tools/vector_strokes.py の確かめ）。
前からある線の pointer_type は分からないので null のまま（記録なし）。外接の箱は点と太さから埋める。

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-08 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BOX = ('box_x0_mm', 'box_y0_mm', 'box_x1_mm', 'box_y1_mm')


def upgrade() -> None:
    op.add_column('pen_strokes', sa.Column('pointer_type', sa.String(length=8), nullable=True))
    for name in BOX:
        op.add_column('pen_strokes', sa.Column(name, sa.Float(), nullable=True))
    # 点 [x, y, 筆圧, ms] の x・y の最小・最大に、太さの半分を足す
    op.execute("""
        UPDATE pen_strokes s SET
          box_x0_mm = b.x0 - s.width_mm / 2, box_y0_mm = b.y0 - s.width_mm / 2,
          box_x1_mm = b.x1 + s.width_mm / 2, box_y1_mm = b.y1 + s.width_mm / 2
        FROM (
          SELECT id, min((p->>0)::float) AS x0, min((p->>1)::float) AS y0,
                     max((p->>0)::float) AS x1, max((p->>1)::float) AS y1
          FROM pen_strokes, jsonb_array_elements(points::jsonb) AS p GROUP BY id
        ) b WHERE b.id = s.id
    """)
    for name in BOX:
        op.alter_column('pen_strokes', name, nullable=False)
    op.execute("CREATE INDEX ix_pen_strokes_box ON pen_strokes USING gist "
               "(box(point(box_x0_mm, box_y0_mm), point(box_x1_mm, box_y1_mm)))")
    op.create_index('ix_pen_strokes_layer_order', 'pen_strokes', ['layer_id', 'stack_order'])


def downgrade() -> None:
    op.drop_index('ix_pen_strokes_layer_order', table_name='pen_strokes')
    op.execute("DROP INDEX ix_pen_strokes_box")
    for name in reversed(BOX):
        op.drop_column('pen_strokes', name)
    op.drop_column('pen_strokes', 'pointer_type')
