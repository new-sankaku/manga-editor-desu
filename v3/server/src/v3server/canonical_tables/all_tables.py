"""正本の表を全部読み込む。Base.metadata に全部の表が載る（alembic とデータベースの準備が使う）。"""

from v3server.canonical_tables import (  # noqa: F401
    check_result_tables,
    event_and_lock_tables,
    harness_tables,
    image_file_tables,
    material_and_setting_tables,
    name_proposal_tables,
    page_item_tables,
    service_and_job_tables,
    text_and_layer_tables,
    threshold_and_finding_tables,
    work_tree_tables,
)
from v3server.canonical_tables.table_base import Base

metadata = Base.metadata
