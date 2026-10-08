"""AIの関与（V3ハーネス設計 4.2・5章）。作業ごとに4つから選ぶ。AIの手が正本に入る所は、どこもここの規則で止める。

作業（TASKS）と、AIの関与（MODES）
- ai_auto：AIに任せる。AIが作り、そのまま正本に入れてよい
- ai_proposes：AIが案を出し、人が選ぶ。AIは案（ネームの案・絵の候補）を出せるが、正本の値は変えられない
- human_makes_ai_checks：人が作り、AIは検査だけする。AIは作れない。検査の依頼だけ受ける
- no_ai：AIを使わない

AIの手の種類（ACTIONS）
- propose：案や候補を出す（ネームの案を出す・生成した絵を登録する・作る依頼）
- decide：正本の値を変える（コマ・ページ・文字・層の項目を変える、案を採用する）
- check：検査する（検査の依頼）

人の操作はここで止めない。人の手の印（human_hand_guard.py）と同じく、AIの操作だけを見る。
プログラムの計算（コマ割りの計算など）も、人の手の印を付けず人の手を上書きしないために、AIの側として扱う（私の判断）。
"""

from typing import Literal, get_args

from v3server.canonical_tables.work_tree_tables import Work
from v3server.request_actor import Actor
from v3server.v3_error_types import AiInvolvementRefused, Invalid

Task = Literal["plan", "structure", "settings_material", "name", "panel_layout", "drawing", "finishing", "translation"]
Mode = Literal["ai_auto", "ai_proposes", "human_makes_ai_checks", "no_ai"]
Action = Literal["propose", "decide", "check"]

TASKS: tuple[str, ...] = get_args(Task)
MODES: tuple[str, ...] = get_args(Mode)

TASK_TITLES = {
    "plan": "企画（S0）",
    "structure": "構成（S1）",
    "settings_material": "設定資料（S2）",
    "name": "ネームの中身（S3。場面・人物・セリフ）",
    "panel_layout": "コマ割り（S3。枠・読む順・段の割り）",
    "drawing": "作画（S4。コマの絵・層・絵の置き方）",
    "finishing": "仕上げ（S5。文字の置き場・書体と飾り・しっぽ・フキダシの形・トーン・図形・絵の仕上げ）",
    "translation": "翻訳（元の言語のほかの言語の文字）",
}

_ALLOWED: dict[str, frozenset[str]] = {
    "ai_auto": frozenset({"propose", "decide", "check"}),
    "ai_proposes": frozenset({"propose", "check"}),
    "human_makes_ai_checks": frozenset({"check"}),
    "no_ai": frozenset(),
}

# 作品がまだ選んでいない作業の関与。設計 5章「人の確認は既定値」に合わせ、AIは案までにする。
# 作品の値が無いことを隠さないよう、読む口（GET /works/{id}/ai-involvement）は既定かどうかも返す
DESIGN_DEFAULT_MODE: Mode = "ai_proposes"

# 行の about_task を作業とする印（赤入れ）
ABOUT_TASK = "@about_task"

# 人が直せる項目と、その項目がどの作業に入るか。表の名前 → {項目: 作業}。
# 人の手の印を付ける項目も、AIの関与で止める項目も、ここの1か所で決める（human_hand_guard.py もここを読む）
HUMAN_EDITABLE_FIELDS: dict[str, dict[str, str]] = {
    "pages": {"layout": "panel_layout"},
    "panels": {"order": "panel_layout", "frame": "panel_layout", "frame_style": "panel_layout", "role": "name",
               "content": "name", "image_id": "drawing", "image_placement": "drawing", "adjustments": "finishing"},
    "text_items": {"item_kind": "name", "panel_id": "name", "order": "name", "text": "name", "speaker": "name",
                   "balloon_kind": "name", "writing_direction": "finishing", "font_size_pt": "finishing",
                   "box_mm": "finishing", "tail_target_mm": "finishing", "joined_to_previous": "finishing",
                   "font_family": "finishing", "decoration": "finishing", "ruby": "finishing",
                   "balloon_shape": "finishing", "transform": "finishing", "opacity": "finishing",
                   "adjustments": "finishing"},
    "panel_layers": {"role": "drawing", "image_id": "drawing", "stack_order": "drawing", "visible": "drawing",
                     "opacity": "drawing", "placement": "drawing", "adjustments": "finishing"},
    "page_items": {"panel_id": "finishing", "spec": "finishing", "box_mm": "finishing", "transform": "finishing",
                   "stack_order": "finishing", "visible": "finishing", "opacity": "finishing",
                   "adjustments": "finishing"},
    # 赤入れは、指摘した作業（about_task）の検査として扱う（ROW_ACTION）
    "annotation_items": {"panel_id": ABOUT_TASK, "region_mm": ABOUT_TASK, "body": ABOUT_TASK, "status": ABOUT_TASK,
                         "about_task": ABOUT_TASK},
    "material_entries": {"kind": "settings_material", "name": "settings_material", "traits": "settings_material",
                         "clothes": "settings_material", "image_ids": "settings_material",
                         "generation": "settings_material", "notes": "settings_material",
                         "proposal_state": "settings_material"},
    "work_plans": {"synopsis": "plan", "audience": "plan", "exclusions": "plan", "notes": "plan"},
    "panel_templates": {"name": "panel_layout", "frames": "panel_layout"},
    "text_item_translations": {"text": "translation", "writing_direction": "translation",
                               "font_size_pt": "translation"},
    "element_generation_settings": {"prompt": "drawing", "negative_prompt": "drawing"},
    "pen_strokes": {k: "drawing" for k in ("points", "width_mm", "color", "opacity", "brush", "brush_options", "seed",
                                           "stack_order")},
}

# 行を抜く・足すときの作業
ROW_TASK = {"pages": "panel_layout", "panels": "panel_layout", "text_items": "name", "panel_layers": "drawing",
            "page_items": "finishing", "annotation_items": ABOUT_TASK, "material_entries": "settings_material",
            "panel_templates": "panel_layout", "pen_strokes": "drawing",
            "text_item_translations": "translation", "element_generation_settings": "drawing"}

# 行を変えるときのAIの手。書いていない表は decide（正本の値を変える）
ROW_ACTION = {"annotation_items": "check"}


def field_task(obj, task: str) -> str:
    """HUMAN_EDITABLE_FIELDS・ROW_TASK の作業を、行に合わせて決める（赤入れは行の about_task）。"""
    return obj.about_task if task == ABOUT_TASK else task


# 絵の役目 → 絵を作る作業（生成した絵を登録するとき）
IMAGE_ROLE_TASK = {"reference": "settings_material", "character_sheet": "settings_material", "tone": "finishing"}


def image_role_task(role: str) -> str:
    return IMAGE_ROLE_TASK.get(role, "drawing")


def mode_of(work: Work, task: str) -> tuple[str, bool]:
    """(関与, 作品が選んだか)。選んでいなければ設計の既定。"""
    if task not in TASKS:
        raise Invalid(f"知らない作業: {task}")
    chosen = (work.ai_involvement or {}).get(task)
    if chosen is None:
        return DESIGN_DEFAULT_MODE, False
    return chosen, True


def ai_may(work: Work, task: str, action: str) -> bool:
    mode, _ = mode_of(work, task)
    return action in _ALLOWED[mode]


def require_ai_may(work: Work, task: str, action: str) -> None:
    """AIの手（action）が、その作業（task）の関与で許されていなければ止める。"""
    if not ai_may(work, task, action):
        mode, chosen = mode_of(work, task)
        how = "作品が選んだ" if chosen else "設計の既定"
        raise AiInvolvementRefused(f"{TASK_TITLES[task]} のAIの関与は {mode}（{how}）。AIの {action} は許されていない")


def require_actor_may(actor: Actor, work: Work, task: str, action: str) -> None:
    """操作した者がAIのときだけ確かめる。"""
    if actor.kind == "ai":
        require_ai_may(work, task, action)


def require_ai_may_change_fields(actor: Actor, work: Work, table: str, fields: set[str], obj=None) -> None:
    """AIが行の項目を変えるとき。変える項目の作業ごとに、その表の手（ROW_ACTION、無ければ decide）が許されているか。
    赤入れのように作業が行で決まる表は obj を渡す。"""
    if actor.kind != "ai":
        return
    table_fields = HUMAN_EDITABLE_FIELDS[table]
    action = ROW_ACTION.get(table, "decide")
    for task in sorted({field_task(obj, table_fields[f]) for f in fields if f in table_fields}):
        require_ai_may(work, task, action)
