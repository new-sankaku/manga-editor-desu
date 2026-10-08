"""comfy_graphs の試験。組んだ辞書の、どの出力がどの入力に入るかを確かめる。"""
import numpy as np
import pytest

from v3server.comfy_graphs.character_prompt_words import CharacterSheetWords, ShotTarget, character_words, shot_negative, shot_prompt
from v3server.comfy_graphs.comfy_node_graph import ComfyNodeGraph, NodeOutput
from v3server.comfy_graphs.controlnet_nodes import ControlKind, ControlSettings, insert_control
from v3server.comfy_graphs.line_extract_graph import build_line_extract
from v3server.comfy_graphs.pose_skeleton_image import FigureBox, draw_standing_pose, figure_box_pixels
from v3server.comfy_graphs.protected_redraw_graph import build_protected_redraw
from v3server.comfy_graphs.regional_prompt_nodes import RegionPrompt, apply_regional_prompts, left_right_regions
from v3server.comfy_graphs.text_to_image_graph import SamplerSettings, build_text_to_image
from v3server.comfy_graphs.upscale_graph import build_upscale

SETTINGS = SamplerSettings(checkpoint_name='ckpt-a', steps=10, cfg=4.0, sampler_name='s-a', scheduler='sch-a')


def _of(prompt, class_type):
    return {i: n for i, n in prompt.items() if n['class_type'] == class_type}


def _only(prompt, class_type):
    found = _of(prompt, class_type)
    assert len(found) == 1, f'{class_type} が {len(found)} 個'
    return next(iter(found.items()))


def _all_links_exist(prompt):
    for n in prompt.values():
        for v in n['inputs'].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                assert v[0] in prompt


def _t2i():
    return build_text_to_image(SETTINGS, 'pos', 'neg', 7, 832, 1216, 'pre')


# ---- 道具 ----

def test_node_graph_rejects_missing_link():
    g = ComfyNodeGraph()
    with pytest.raises(KeyError):
        g.add('VAEDecode', samples=NodeOutput('99', 0))


def test_node_graph_rejects_node_without_index():
    g = ComfyNodeGraph()
    a = g.add('LoadImage', image='x.png')
    with pytest.raises(TypeError):
        g.add('ImageInvert', image=a)


def test_node_graph_to_prompt_is_copy():
    g = ComfyNodeGraph()
    a = g.add('LoadImage', image='x.png')
    p = g.to_prompt()
    p[a.node_id]['inputs']['image'] = 'changed'
    assert g.to_prompt()[a.node_id]['inputs']['image'] == 'x.png'


def test_connect_unknown_input_raises():
    g = ComfyNodeGraph()
    a = g.add('LoadImage', image='x.png')
    with pytest.raises(KeyError):
        g.connect(a, 'nothing', 1)


# ---- 文から絵 ----

def test_text_to_image_links():
    t = _t2i()
    p = t.graph.to_prompt()
    _all_links_exist(p)
    ck_id, ck = _only(p, 'CheckpointLoaderSimple')
    assert ck['inputs']['ckpt_name'] == 'ckpt-a'
    ks_id, ks = _only(p, 'KSampler')
    assert ks['inputs']['model'] == [ck_id, 0]
    assert p[ks['inputs']['positive'][0]]['inputs']['text'] == 'pos'
    assert p[ks['inputs']['negative'][0]]['inputs']['text'] == 'neg'
    for enc in _of(p, 'CLIPTextEncode').values():
        assert enc['inputs']['clip'] == [ck_id, 1]
    assert ks['inputs']['steps'] == 10 and ks['inputs']['seed'] == 7
    assert p[ks['inputs']['latent_image'][0]]['inputs'] == {'width': 832, 'height': 1216, 'batch_size': 1}
    dec_id, dec = _only(p, 'VAEDecode')
    assert dec['inputs'] == {'samples': [ks_id, 0], 'vae': [ck_id, 2]}
    _, save = _only(p, 'SaveImage')
    assert save['inputs']['images'] == [dec_id, 0]


# ---- 制御 ----

def _control(kind, union, invert):
    return ControlSettings(kind=kind, controlnet_name='cn-' + kind.value, union_type=union,
                           strength=0.8, start_percent=0.0, end_percent=0.7, invert_image=invert)


def test_control_rewires_sampler():
    t = _t2i()
    apply = insert_control(t.graph, t.sampler, _control(ControlKind.DEPTH, 'depth', False), 'depth.png')
    p = t.graph.to_prompt()
    _all_links_exist(p)
    ks = p[t.sampler.node_id]['inputs']
    assert ks['positive'] == [apply.node_id, 0]
    assert ks['negative'] == [apply.node_id, 1]
    ap = p[apply.node_id]['inputs']
    assert ap['positive'] == [t.positive.node_id, 0]
    assert ap['negative'] == [t.negative.node_id, 0]
    assert ap['strength'] == 0.8 and ap['end_percent'] == 0.7
    # 多用途版の種類 → 読み込み
    union = p[ap['control_net'][0]]
    assert union['class_type'] == 'SetUnionControlNetType' and union['inputs']['type'] == 'depth'
    assert p[union['inputs']['control_net'][0]]['inputs']['control_net_name'] == 'cn-depth'
    # 反転しないので画像はそのまま
    assert p[ap['image'][0]] == {'class_type': 'LoadImage', 'inputs': {'image': 'depth.png'}}
    assert not _of(p, 'ImageInvert')


def test_control_dedicated_model_and_invert():
    t = _t2i()
    apply = insert_control(t.graph, t.sampler, _control(ControlKind.LINE, None, True), 'line.png')
    p = t.graph.to_prompt()
    ap = p[apply.node_id]['inputs']
    assert p[ap['control_net'][0]]['class_type'] == 'ControlNetLoader'
    assert not _of(p, 'SetUnionControlNetType')
    inv = p[ap['image'][0]]
    assert inv['class_type'] == 'ImageInvert'
    assert p[inv['inputs']['image'][0]]['inputs']['image'] == 'line.png'


def test_two_controls_chain():
    t = _t2i()
    first = insert_control(t.graph, t.sampler, _control(ControlKind.POSE, None, False), 'pose.png')
    second = insert_control(t.graph, t.sampler, _control(ControlKind.DEPTH, 'depth', False), 'depth.png')
    p = t.graph.to_prompt()
    assert p[second.node_id]['inputs']['positive'] == [first.node_id, 0]
    assert p[second.node_id]['inputs']['negative'] == [first.node_id, 1]
    assert p[t.sampler.node_id]['inputs']['positive'] == [second.node_id, 0]


# ---- 範囲ごとの文 ----

def test_regional_left_right():
    t = _t2i()
    regions = left_right_regions(832, 1216, 'left words', 'right words', 1.0)
    whole = apply_regional_prompts(t.graph, t.sampler, t.checkpoint, regions)
    p = t.graph.to_prompt()
    _all_links_exist(p)
    assert p[t.sampler.node_id]['inputs']['positive'] == [whole.node_id, 0]
    w = p[whole.node_id]['inputs']
    assert w['conditioning_1'] == [t.positive.node_id, 0]
    pair = p[w['conditioning_2'][0]]
    assert pair['class_type'] == 'ConditioningCombine'
    areas = [p[pair['inputs'][k][0]] for k in ('conditioning_1', 'conditioning_2')]
    assert [a['inputs']['x'] for a in areas] == [0, 416]
    assert [a['inputs']['width'] for a in areas] == [416, 416]
    texts = [p[a['inputs']['conditioning'][0]]['inputs']['text'] for a in areas]
    assert texts == ['left words', 'right words']
    for a in areas:
        assert p[a['inputs']['conditioning'][0]]['inputs']['clip'] == [t.checkpoint.node_id, 1]


def test_regional_after_control_keeps_control():
    t = _t2i()
    apply = insert_control(t.graph, t.sampler, _control(ControlKind.POSE, None, False), 'pose.png')
    whole = apply_regional_prompts(t.graph, t.sampler, t.checkpoint, [RegionPrompt('a', 0, 0, 64, 64, 1.0)])
    p = t.graph.to_prompt()
    assert p[whole.node_id]['inputs']['conditioning_1'] == [apply.node_id, 0]
    assert p[t.sampler.node_id]['inputs']['negative'] == [apply.node_id, 1]


def test_regional_rejects_off_grid():
    t = _t2i()
    with pytest.raises(ValueError):
        apply_regional_prompts(t.graph, t.sampler, t.checkpoint, [RegionPrompt('a', 3, 0, 64, 64, 1.0)])
    with pytest.raises(ValueError):
        apply_regional_prompts(t.graph, t.sampler, t.checkpoint, [])


# ---- 描き直しと貼り戻し ----

@pytest.mark.parametrize('protected', [None, 'human.png'])
def test_protected_redraw_always_pastes_back(protected):
    r = build_protected_redraw(SETTINGS, 'src.png', 'redraw.png', protected, 'pos', 'neg', 5, 0.85, 'pre')
    p = r.graph.to_prompt()
    _all_links_exist(p)
    src_id = next(i for i, n in _of(p, 'LoadImage').items() if n['inputs']['image'] == 'src.png')
    paste_id, paste = _only(p, 'ImageCompositeMasked')
    dec_id, _ = _only(p, 'VAEDecode')
    assert paste['inputs']['destination'] == [src_id, 0]
    assert paste['inputs']['source'] == [dec_id, 0]
    # 保存されるのは貼り戻した絵だけ
    _, save = _only(p, 'SaveImage')
    assert save['inputs']['images'] == [paste_id, 0]
    # 雑音のマスクと貼り戻しのマスクは同じもの
    _, noise = _only(p, 'SetLatentNoiseMask')
    assert noise['inputs']['mask'] == paste['inputs']['mask'] == [r.redraw_mask.node_id, 0]
    _, ks = _only(p, 'KSampler')
    assert ks['inputs']['denoise'] == 0.85
    assert p[noise['inputs']['samples'][0]]['inputs']['pixels'] == [src_id, 0]


def test_protected_redraw_subtracts_human_area():
    r = build_protected_redraw(SETTINGS, 'src.png', 'redraw.png', 'human.png', 'pos', 'neg', 5, 0.85, 'pre')
    p = r.graph.to_prompt()
    _, comp = _only(p, 'MaskComposite')
    assert comp['inputs']['operation'] == 'subtract'
    loads = {n['inputs']['image']: i for i, n in _of(p, 'LoadImage').items()}
    dest = p[comp['inputs']['destination'][0]]
    srcm = p[comp['inputs']['source'][0]]
    assert dest['inputs']['image'] == [loads['redraw.png'], 0]
    assert srcm['inputs']['image'] == [loads['human.png'], 0]


def test_protected_redraw_has_no_switch_to_skip_paste_back():
    import inspect
    params = inspect.signature(build_protected_redraw).parameters
    assert not any('composite' in n or 'paste' in n for n in params)


# ---- 拡大・線画を抜く ----

def test_upscale_with_and_without_model():
    p = build_upscale('in.png', 'up-model', 4300, 6070, 'pre').graph.to_prompt()
    _all_links_exist(p)
    up_id, up = _only(p, 'ImageUpscaleWithModel')
    assert p[up['inputs']['upscale_model'][0]]['inputs']['model_name'] == 'up-model'
    _, sc = _only(p, 'ImageScale')
    assert sc['inputs']['image'] == [up_id, 0] and (sc['inputs']['width'], sc['inputs']['height']) == (4300, 6070)

    p = build_upscale('in.png', None, 100, 200, 'pre').graph.to_prompt()
    assert not _of(p, 'UpscaleModelLoader')
    _, sc = _only(p, 'ImageScale')
    assert p[sc['inputs']['image'][0]]['class_type'] == 'LoadImage'


def test_line_extract_uses_given_preprocessor():
    e = build_line_extract('in.png', 'SomePreprocessor', 1216, 'pre')
    p = e.graph.to_prompt()
    _, pre = _only(p, 'SomePreprocessor')
    assert pre['inputs']['resolution'] == 1216
    _, save = _only(p, 'SaveImage')
    assert save['inputs']['images'] == [e.extract.node_id, 0]


# ---- 骨格の図 ----

def test_pose_image_inside_figure_box():
    box = FigureBox(0.66, 0.22, 0.80, 0.94)
    assert figure_box_pixels(1536, 576, box) == (1014, 127, 1229, 541)
    im = draw_standing_pose(1536, 576, box)
    assert im.size == (1536, 576) and im.mode == 'RGB'
    a = np.asarray(im).max(2)
    ys, xs = np.nonzero(a)
    x0, y0, x1, y1 = figure_box_pixels(1536, 576, box)
    margin = 10  # 関節の丸の半径ぶん
    assert xs.min() >= x0 - margin and xs.max() <= x1 + margin
    assert ys.min() >= y0 - margin and ys.max() <= y1 + margin
    assert a[:, : x0 - margin].max() == 0  # 枠の外の左は黒のまま


def test_pose_rejects_empty_box():
    with pytest.raises(ValueError):
        draw_standing_pose(100, 100, FigureBox(0.5, 0.5, 0.6, 0.5))


# ---- 文 ----

SHEET = CharacterSheetWords(count_words='1girl, solo', feature_words='white hair, twin braids, red eyes')


def test_character_words_always_full():
    assert character_words(SHEET) == '1girl, solo, white hair, twin braids, red eyes'


def test_shot_prompt_order_and_parts():
    scene = ShotTarget(add_words='wide shot', negative_words='', has_person=True, has_place=True)
    assert shot_prompt('q', 'style', scene, SHEET, 'street') == 'q, style, wide shot, 1girl, solo, white hair, twin braids, red eyes, street'
    bg = ShotTarget(add_words='scenery', negative_words='people', has_person=False, has_place=True)
    assert shot_prompt('q', 'style', bg, None, 'street') == 'q, style, scenery, street'
    assert shot_negative('base', bg) == 'base, people'
    assert shot_negative('base', scene) == 'base'


def test_shot_prompt_missing_parts_raise():
    scene = ShotTarget(add_words='wide shot', negative_words='', has_person=True, has_place=True)
    with pytest.raises(ValueError):
        shot_prompt('q', 's', scene, None, 'street')
    with pytest.raises(ValueError):
        shot_prompt('q', 's', scene, SHEET, None)
