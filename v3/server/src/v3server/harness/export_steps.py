"""書き出し（S7）の作業の段。対象は話。プログラムだけの工程で、提出は人が決める（設計 5 の表）。

- 生成：spec.export.formats の形ごとに、話の全ページを書き出す（書き出しの依頼 ExportRun を作り、書き出しの流れと
  同じ run_export をこの段で行う）。候補は1つ（同じ原稿を同じ形で書き出しても同じ物になるため）
- 検査（プログラム）：入稿前の確かめ（preflight。解像度・裁ち落とし・色・安全線・文字の組み）。重さが error の問題は
  指摘にする。候補は落とさない（直すのは人。落としても同じ物を書き出し直すだけ）
- 人が書き出した物を見て採る（提出）。採っても外へは送らない（入稿先へ送る口は無い。人が持ち出す）
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from v3server.canonical_tables.harness_tables import HarnessUnit
from v3server.canonical_tables.material_and_setting_tables import ExportRun
from v3server.canonical_tables.work_tree_tables import Work
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.harness import stage_steps_common as c
from v3server.operations.text_translation_operations import LANGUAGE_PATTERN
from v3server.print_export.book_layout import episode_pages
from v3server.print_export.export_runner import ExportRefused, run_export
from v3server.print_export.preflight_checks import issues_json, run_preflight
from v3server.print_export.text_render import font_path, measure_texts
from v3server.server_settings import get_settings


class ExportFormat(BaseModel):
    """1つの書き出しの形（POST /works/{id}/exports の値のうち、ページ以外）。"""

    model_config = ConfigDict(extra="forbid")
    format: Literal["png", "pdf", "psd"]
    dpi: int | None = Field(gt=0, le=2400)
    spread_output: Literal["split", "joined", "both"] | None
    paper_mm: tuple[float, float] | None
    language: str | None = Field(pattern=LANGUAGE_PATTERN)


class ExportSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formats: list[ExportFormat] = Field(min_length=1)


cut_out = c.cut_out_episode


async def context(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    c.spec_of(unit, "export", ExportSpec)
    async with get_sessionmaker()() as session:
        if not await episode_pages(session, unit.target_id):
            raise q.blocked("話にページが無い")
    return {"cost": 0, "job_ids": []}


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    spec = c.spec_of(unit, "export", ExportSpec)

    async def export() -> dict[str, Any]:
        runs = []
        async with get_sessionmaker()() as session:
            page_ids = [p.id for p in await episode_pages(session, unit.target_id)]
            for f in spec.formats:
                key = f"{unit.id}:a{args['attempt']}:{f.format}:{f.dpi}:{f.spread_output}:{f.language}"
                run = (await session.execute(select(ExportRun).where(
                    ExportRun.work_id == unit.work_id, ExportRun.workflow_id == key))).scalar_one_or_none()
                if run is None:
                    run = ExportRun(work_id=unit.work_id, requested_by=unit.requested_by, format=f.format,
                                    page_ids=page_ids, dpi=f.dpi, spread_output=f.spread_output,
                                    paper_mm=list(f.paper_mm) if f.paper_mm else None, language=f.language,
                                    status="running", outputs=[], workflow_id=key)
                    session.add(run)
                    await session.commit()
                if run.status != "done":
                    try:
                        run.outputs, run.status = await run_export(session, run), "done"
                    except ExportRefused as e:
                        await session.rollback()
                        run = await session.get(ExportRun, run.id)
                        run.status, run.detail = "failed", str(e)
                        await session.commit()
                        raise q.blocked(f"{f.format} を書き出せない: {e}") from e
                    await session.commit()
                runs.append({"run_id": run.id, "format": f.format, "files": [o["file"] for o in run.outputs
                                                                             if "file" in o]})
        return {"exports": runs, "by": "プログラム（書き出し）"}

    return await c.one_candidate(unit, args, export, "同じ原稿を同じ形で書き出すので候補は1つ")


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()

    def measure(items):
        if not s.text_render_script:
            raise q.blocked("V3_TEXT_RENDER_SCRIPT が無い。文字の組み方を確かめられない")
        return measure_texts(items, s.node_executable, s.text_render_script)

    async def judge(cand) -> list[dict[str, Any]]:
        async with get_sessionmaker()() as session:
            work = await session.get(Work, unit.work_id)
            page_ids = [p.id for p in await episode_pages(session, unit.target_id)]
            report = issues_json(await run_preflight(session, work, page_ids, measure,
                                                     lambda family: font_path(s.font_dir, family)))
        out = [c.finding("入稿前の確かめ", report["ok"], False,
                         f"error {report['errors']}・warning {report['warnings']}",
                         issues=report["issues"][:50])]
        out += [c.finding(f"書き出し（{e['format']}）", bool(e["files"]), False,
                          f"{len(e['files'])} ファイル（{e['run_id']}）") for e in cand.content["exports"]]
        return out

    return await c.check_candidates(unit, args, judge)


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.pick_fewest_flags(unit, args, "書き出した物は1つ")


async def finalize(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        cand = await c.picked_content(session, args)
        return {"candidate_id": cand.id, "exports": [e["run_id"] for e in cand.content["exports"]],
                "note": "人が提出すると決めた。入稿先へ送る口は無い（人が持ち出す）"}


async def discard_round(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.discard_candidates(unit, args)
