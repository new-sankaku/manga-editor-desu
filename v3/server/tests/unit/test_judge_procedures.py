"""judge_procedures の試験。LLM の代わりに、問いを見て決まった答えを返す関数を渡す。"""
import json
import re
from pathlib import Path

import pytest

from v3server.judge_procedures.blind_image_copy import make_blind_copies
from v3server.judge_procedures.candidate_pick import pick_candidate
from v3server.judge_procedures.pair_comparison import ImagePair, compare_pairs
from v3server.llm_questions.answer_json_reader import BrokenAnswerError


@pytest.fixture
def images(tmp_path: Path) -> list[str]:
    src = tmp_path / "src"
    src.mkdir()
    out = []
    for name in ("joy_weak.png", "joy_mid.png", "joy_strong.png"):
        p = src / name
        p.write_bytes(name.encode())  # 中身で元が分かるようにしておく
        out.append(str(p))
    return out


def test_blind_copy_hides_names(images, tmp_path):
    b = make_blind_copies(images, str(tmp_path / "blind"), "s1")
    for x in images:
        path = b.blind_path_by_original[x]
        assert "joy" not in path.name and path.read_bytes() == Path(x).read_bytes()
        assert b.original_of(path.name) == x
    assert make_blind_copies(images, str(tmp_path / "blind2"), "s1").blind_name(images[0]) == b.blind_name(images[0])
    assert make_blind_copies(images, str(tmp_path / "blind3"), "s2").blind_name(images[0]) != b.blind_name(images[0])


def _strength_judge(calls: list):
    """画像の中身（元の名前）から強さを読み、強い方を答える評価役。問いの文には元の名前が出ないことも確かめる。"""
    rank = {"weak": 1, "mid": 2, "strong": 3}

    async def ask(prompt: str, image_paths: list[str]) -> str:
        assert "joy" not in prompt
        calls.append((prompt, image_paths))
        strength = {Path(p).name: rank[Path(p).read_bytes().decode().split("_")[1].split(".")[0]] for p in image_paths}
        out = []
        for i, a, b in re.findall(r"組(\d+)：A＝(\S+)　B＝(\S+)", prompt):
            out.append({"id": int(i), "choice": "A" if strength[a] > strength[b] else "B"})
        return json.dumps({"pairs": out})

    return ask


async def test_pair_comparison_consistent(images, tmp_path):
    calls = []
    weak, mid, strong = images
    pairs = [ImagePair(weak, mid), ImagePair(strong, mid)]
    res = await compare_pairs(_strength_judge(calls), pairs, "AとBのどちらが強いかを答えてください。", str(tmp_path / "b"), "s")
    assert [r.verdict for r in res] == ["right", "left"]
    assert all(r.consistent for r in res)
    assert len(calls) == 2  # 左右を入れ替えた2回
    # 2回とも同じ画像を同じ順に添える
    assert calls[0][1] == calls[1][1]


async def test_pair_comparison_disagreement_is_tie(images, tmp_path):
    async def always_a(prompt, image_paths):
        n = len(re.findall(r"組\d+：", prompt))
        return json.dumps({"pairs": [{"id": i, "choice": "A"} for i in range(1, n + 1)]})

    res = await compare_pairs(always_a, [ImagePair(images[0], images[1])], "AとBのどちらが強いかを答えてください。", str(tmp_path / "b"), "s")
    assert res[0].first == "left" and res[0].second == "right" and res[0].verdict == "tie" and not res[0].consistent


async def test_pair_comparison_same_is_tie(images, tmp_path):
    async def same(prompt, image_paths):
        return '{"pairs":[{"id":1,"choice":"同じ"}]}'

    res = await compare_pairs(same, [ImagePair(images[0], images[1])], "AとBのどちらが強いかを答えてください。", str(tmp_path / "b"), "s")
    assert res[0].verdict == "tie" and res[0].consistent


@pytest.mark.parametrize("answer", ["答えられません", '{"pairs":[]}', '{"pairs":[{"id":1,"choice":"左"}]}'])
async def test_pair_comparison_broken(images, tmp_path, answer):
    async def broken(prompt, image_paths):
        return answer

    with pytest.raises(BrokenAnswerError):
        await compare_pairs(broken, [ImagePair(images[0], images[1])], "AとBのどちらが強いかを答えてください。", str(tmp_path / "b"), "s")


async def test_candidate_pick(images, tmp_path):
    async def pick_strong(prompt, image_paths):
        assert "joy" not in prompt and "「なし」" in prompt
        for p in image_paths:
            if b"strong" in Path(p).read_bytes():
                # 場所ごと答えても名前で照らせる
                return json.dumps({"pick": p, "why": "狙いに合う"}, ensure_ascii=False)
        raise AssertionError

    r = await pick_candidate(pick_strong, images, "強い喜びの顔", str(tmp_path / "b"), "s")
    assert r.picked == images[2] and r.why == "狙いに合う"


async def test_candidate_pick_none(images, tmp_path):
    async def none(prompt, image_paths):
        return '{"pick":"なし","why":"どれも合わない"}'

    r = await pick_candidate(none, images, "強い喜びの顔", str(tmp_path / "b"), "s")
    assert r.picked is None and r.why == "どれも合わない"


@pytest.mark.parametrize("answer", ['{"pick":"img_0000.png","why":"x"}', '{"why":"x"}', "選べません"])
async def test_candidate_pick_broken(images, tmp_path, answer):
    async def broken(prompt, image_paths):
        return answer

    with pytest.raises(BrokenAnswerError):
        await pick_candidate(broken, images, "強い喜びの顔", str(tmp_path / "b"), "s")
