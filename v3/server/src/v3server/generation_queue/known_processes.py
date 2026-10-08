"""アプリが中身を知っている処理（今のアプリの機能を移したもの。V3細部の決めごと 10.4）。

処理の名前ごとに、何の作業の処理か（ai_task・ai_action）をここで決める。送り先（ProcessRoute）を決めるとき
（http_routes/service_routes.py の put_route）と、依頼を受けるとき（job_start_and_control.enqueue）に、ここと合うかを確かめる
（作業のAIの関与で止めるべき処理を、別の作業の名前で通さないため）。

答えを正本に入れる処理は、ここで答えを読む（service_call_activity.py が呼ぶ）。入れるのは、依頼した人の代わりのAIとして
操作の窓口を通す（AIの関与・権限・ロック・人の手の印が同じにかかる）。
- change_angle（絵の角度を変える）・remove_background（背景を消す）：生成の処理。出た絵は依頼の register で登録する（案）
- read_prompt（絵から指示文を読む）：答えを読んで job.result に置くだけ（人が写して使う）
- extract_characters（企画から人物を抜き出す）：答えの人物を、AIの案として設定資料に足す（人が採るまで使わない）
"""

from typing import Any

from v3server.generation_queue.image_process_registry import SPECS
from v3server.llm_questions.extract_characters_question import parse_extract_characters_answer
from v3server.llm_questions.read_prompt_question import parse_read_prompt_answer
from v3server.v3_error_types import Invalid

KNOWN_PROCESSES: dict[str, tuple[str, str]] = {
    "change_angle": ("drawing", "propose"),
    "remove_background": ("drawing", "propose"),
    "read_prompt": ("drawing", "propose"),
    "extract_characters": ("settings_material", "propose"),
    # 画像生成の処理（文から絵・囲んで直すなど）は一覧の側で決める
    **{s.name: (s.ai_task, s.ai_action) for s in SPECS.values()},
}


def check_process_task(process: str, ai_task: str | None, ai_action: str | None) -> None:
    want = KNOWN_PROCESSES.get(process)
    if want is not None and (ai_task, ai_action) != want:
        raise Invalid(f"{process} は ai_task={want[0]}・ai_action={want[1]} の処理（今は {ai_task}・{ai_action}）")


async def handle_known_result(session, job, actor, authz, output: dict[str, Any]) -> dict[str, Any]:
    """答えを読み、要るものは操作の窓口を通して正本に入れる。足した物の id などを output に足して返す。
    答えの形が崩れていれば BrokenAnswerError（呼ぶ側で broken_response として止める）。"""
    from v3server.operations.material_and_plan_operations import AddMaterialEntry
    from v3server.operations.operation_submit_and_undo import submit

    if job.process == "read_prompt":
        return {**output, "read": parse_read_prompt_answer(output["text"]).model_dump()}
    if job.process == "extract_characters":
        added = []
        for c in parse_extract_characters_answer(output["text"]):
            op = AddMaterialEntry(kind="character", name=c.name, traits=c.traits, notes=c.notes, job_id=job.id)
            await submit(session, authz, actor, job.work_id, op)
            added.append(op.id)
        return {**output, "material_entry_ids": added}
    return output
