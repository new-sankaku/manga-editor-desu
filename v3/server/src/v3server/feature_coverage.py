"""V3細部の決めごと 10.1 の道具と 10.4 の各行を、サーバーのどの操作・口で受けるかの一覧。
tests/unit/test_feature_coverage.py が、決めごとの文書の行を全部読み、どの行もここに載っていて、
載せた操作と口が本当にあることを確かめる（文書に行を足したのにサーバーに無い、を見落とさないため）。

- "screen"：画面だけの物（サーバーの値も操作も要らない）
- "excluded"：入れないと決めた物（統計の一覧。決めごと 8章）
- ops：POST /works/{id}/ops に送る操作の type。routes：「方法 道」
"""

SCREEN = "screen"
EXCLUDED = "excluded"

# 10.1 の道具（帯に並ぶ物と、その右の物）
TOOLS_10_1: dict[str, object] = {
    "選ぶ": SCREEN,
    "囲んで頼む": {"routes": ["POST /works/{work_id}/jobs"]},  # input_images の purpose=mask に region_px
    "赤入れ": {"ops": ["add_annotation", "update_annotation", "set_removed"],
               "routes": ["POST /works/{work_id}/annotations/{annotation_id}/job"]},
    "ペン": {"ops": ["add_pen_strokes", "update_pen_strokes", "remove_pen_strokes", "set_stroke_cache"],
             "routes": ["POST /works/{work_id}/layers/{layer_id}/stroke-cache"]},
    "消しゴム": {"ops": ["erase_pen_strokes", "erase_pixels"],
                 "routes": ["POST /works/{work_id}/panels/{panel_id}/erase-pixels"]},
    "ペン・消しゴム": {"ops": ["add_pen_strokes", "erase_pen_strokes", "erase_pixels"]},
    "文字": {"ops": ["add_text_item", "update_text_item"]},
    "コマ枠": {"ops": ["update_panel", "split_panel", "merge_panels"]},
    "ナイフ": {"ops": ["split_panel"]},
    "フキダシ": {"ops": ["update_text_item"]},
    "トーン": {"ops": ["add_page_item", "update_page_item"]},
    "図形": {"ops": ["add_page_item", "update_page_item"]},
    "手のひら": SCREEN,
    "読む順": {"ops": ["update_panel", "update_text_item"]},
    "表示するもの": SCREEN,
    "取り消す": {"routes": ["POST /works/{work_id}/events/{event_id}/undo"]},
    "やり直す": {"routes": ["POST /works/{work_id}/events/{event_id}/undo"]},
    "拡大縮小": SCREEN,
}

# 10.4 の表の各行（左の列の文字そのまま）
ROWS_10_4: dict[str, object] = {
    "コマの型・図形のコマ・コマの間・枠の線と塗り・ばらばらに割る": {
        "ops": ["save_panel_template", "apply_panel_template", "add_shape_panel", "set_work_settings", "update_panel",
                "random_split_panel"]},
    "ナイフ": {"ops": ["split_panel"]},
    "フキダシの型・自分で描くフキダシ": {"ops": ["add_text_item", "update_text_item"]},
    "文字・文字の飾り・書体を足す": {"ops": ["add_text_item", "update_text_item", "set_work_settings"]},
    "ペンの種類・消しゴム": {"ops": ["add_pen_strokes", "update_pen_strokes", "erase_pen_strokes", "erase_pixels"]},
    "トーン・集中線・スピード線": {"ops": ["add_page_item", "update_page_item"]},
    "絵記号": {"ops": ["add_page_item", "update_page_item"]},
    "位置・角度・拡大・傾き・反転・不透明度": {
        "ops": ["update_panel", "update_panel_layer", "update_text_item", "update_page_item"]},
    "白黒化・明るさ・ぼかし・重ね方・まとめて戻す": {
        "ops": ["update_panel", "update_panel_layer", "update_text_item", "update_page_item", "reset_adjustments"]},
    "層の一覧（見せる・動かさない・順番）": {"ops": ["update_panel_layer", "update_page_item", "set_fixed"]},
    "絵を作る・絵から作り直す・囲んで直す・角度を変える・拡大・背景を抜く・絵から指示を読む": {
        "routes": ["POST /works/{work_id}/jobs", "POST /works/{work_id}/images/{image_id}/read-prompt"]},
    "手順・モデル・シード・参照": {"ops": ["add_material_entry", "update_material_entry"],
                                   "routes": ["PUT /services/{service_id}/processes/{process}", "POST /works/{work_id}/jobs"]},
    "設定資料（人物・小物・背景・その他）": {
        "ops": ["add_material_entry", "update_material_entry", "decide_material_proposal", "set_removed"]},
    "あらすじ・読者・人物を抜き出す・入れないもの": {
        "ops": ["set_work_plan"], "routes": ["POST /works/{work_id}/plan/extract-characters"]},
    "ページを足す・画像から足す・取り込む": {
        "ops": ["add_page"], "routes": ["POST /works/{work_id}/images",
                                        "POST /works/{work_id}/episodes/{episode_id}/name-imports"]},
    "画像の書き出し・コピー・解像度・紙の大きさ": {
        "routes": ["POST /works/{work_id}/exports", "GET /works/{work_id}/exports/{run_id}",
                   "GET /works/{work_id}/exports/{run_id}/files/{name}",
                   "POST /works/{work_id}/exports/{run_id}/pages/{page_id}/psd"]},
    "マス目・基本枠・印の表示": SCREEN,
    "言語・自動保存・設定": {"ops": ["set_work_settings"], "routes": ["GET /me/settings", "PUT /me/settings"]},
    "探す・置き換え": {"ops": ["replace_text"], "routes": ["GET /works/{work_id}/search"]},
    "統計の一覧": EXCLUDED,
}
