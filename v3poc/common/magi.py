"""MagiV2（ragavsachdeva/magiv2）でコマ・人物・文字を検出する（V3検証用）。
使い方: <MagiV2の仮想環境のpython> magi.py <出力JSON> <画像ファイルまたはフォルダ>...
transformers 5.x で読むための手当ては、別リポジトリ manga-scenario-builder の
src/manga_analyzer/compat/transformers_shim.py と同じ内容を写したもの。"""
import json
import pathlib
import re
import sys
import time

import numpy as np
from PIL import Image

MODEL = 'ragavsachdeva/magiv2'
_RULES = [
    ('.backbone.conv_encoder.model.', '.backbone.model.'),
    ('.ca_kcontent_proj.', '.encoder_attn.k_content_proj.'), ('.ca_kpos_proj.', '.encoder_attn.k_pos_proj.'),
    ('.ca_qcontent_proj.', '.encoder_attn.q_content_proj.'), ('.ca_qpos_sine_proj.', '.encoder_attn.q_pos_sine_proj.'),
    ('.ca_qpos_proj.', '.encoder_attn.q_pos_proj.'), ('.ca_v_proj.', '.encoder_attn.v_proj.'),
    ('.sa_kcontent_proj.', '.self_attn.k_content_proj.'), ('.sa_kpos_proj.', '.self_attn.k_pos_proj.'),
    ('.sa_qcontent_proj.', '.self_attn.q_content_proj.'), ('.sa_qpos_proj.', '.self_attn.q_pos_proj.'),
    ('.sa_v_proj.', '.self_attn.v_proj.'),
    ('.encoder_attn.out_proj.', '.encoder_attn.o_proj.'), ('.self_attn.out_proj.', '.self_attn.o_proj.'),
]
_FC = re.compile(r'(\.layers\.\d+)\.fc(\d)')
# 人物の見た目を比べる部分（ViT）の重みの名前。transformers 5.17 で付け替わった（manga-scenario-builder の直しには無い）
_VIT = [('.encoder.layer.', '.layers.'), ('.attention.attention.query.', '.attention.q_proj.'),
        ('.attention.attention.key.', '.attention.k_proj.'), ('.attention.attention.value.', '.attention.v_proj.'),
        ('.attention.output.dense.', '.attention.o_proj.'), ('.intermediate.dense.', '.mlp.fc1.'), ('.output.dense.', '.mlp.fc2.')]


def load():
    import torch
    from huggingface_hub import hf_hub_download
    from transformers import AutoConfig, TimmBackboneConfig
    from transformers.dynamic_module_utils import get_class_from_dynamic_module
    cfg = AutoConfig.from_pretrained(MODEL, trust_remote_code=True)
    cfg.disable_ocr = True  # 文字読み取り（TrOCR）は使わない。この環境では文字分割の部品が読み込めず止まる
    cfg.detection_model_config.backbone_config = TimmBackboneConfig(backbone='resnet50', use_pretrained_backbone=False, out_indices=[1, 2, 3, 4])
    model = get_class_from_dynamic_module('modelling_magiv2.Magiv2Model', MODEL)(cfg)
    if not hasattr(model, 'all_tied_weights_keys'):
        model.all_tied_weights_keys = set()
    sd = torch.load(hf_hub_download(MODEL, 'pytorch_model.bin'), map_location='cpu', weights_only=True)
    out = {}
    for k, v in sd.items():
        if k.startswith('ocr_model.'):
            continue
        if k.startswith('detection_transformer.'):
            for a, b in _RULES:
                k = k.replace(a, b)
            k = _FC.sub(r'\1.mlp.fc\2', k)
        elif k.startswith('crop_embedding_model.'):
            for a, b in _VIT:
                k = k.replace(a, b)
        out[k] = v
    model.load_state_dict(out, strict=True, assign=True)
    return model.cuda().float().eval()


def main(out, paths):
    import torch
    files = []
    for p in map(pathlib.Path, paths):
        files += sorted(p.glob('*.png')) + sorted(p.glob('*.jpg')) if p.is_dir() else [p]
    t0 = time.time()
    model = load()
    res = []
    for f in files:
        im = np.array(Image.open(f).convert('L').convert('RGB'))
        with torch.no_grad():
            r = model.predict_detections_and_associations([im])[0]
        h, w = im.shape[:2]
        res.append({'file': str(f), 'w': w, 'h': h,
                    'panels': [[round(float(x)) for x in b] for b in r.get('panels', [])],
                    'characters': [[round(float(x)) for x in b] for b in r.get('characters', [])],
                    'texts': [[round(float(x)) for x in b] for b in r.get('texts', [])]})
        torch.cuda.empty_cache()
    pathlib.Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(res), 'images', round(time.time() - t0, 1), 's')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
