"""P41 画風の揃いを CSD（画風の近さを測る部品。重み CC-BY-4.0、コード MIT）で見られるか（一覧 3-10・1-12、候補47）。
CSD の重み（tomg-group-umd/CSD-ViT-L の pytorch_model.bin）を、open_clip の ViT-L/14 の画像側に読み込み、
画風の向き（style）と中身の向き（content）の2つの特徴を、試作の絵ごとに out/emb_<試作>.npz にためる。
使い方: <MagiV2の仮想環境の python> embed.py <CSDの重みのファイル> <試作のフォルダ名> ...（GPU が空いていなければ CPU で動く）"""
import pathlib
import sys

import numpy as np
import open_clip
import torch
from PIL import Image
from torchvision import transforms

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
PRE = transforms.Compose([transforms.Resize(224, interpolation=transforms.InterpolationMode.BICUBIC), transforms.CenterCrop(224), transforms.ToTensor(),
                          transforms.Normalize((0.48145466, 0.4578275, 0.40821073), (0.26862954, 0.26130258, 0.27577711))])


def load(path):
    sd = torch.load(path, map_location='cpu', weights_only=False)['model_state_dict']
    visual = open_clip.create_model('ViT-L-14', pretrained=None).visual
    bb = {k[len('module.backbone.'):]: v for k, v in sd.items() if k.startswith('module.backbone.')}
    visual.proj = None
    missing, unexpected = visual.load_state_dict(bb, strict=False)
    assert not unexpected and all(k == 'proj' for k in missing), (missing, unexpected)
    return visual.eval(), sd['module.last_layer_style'].float(), sd['module.last_layer_content'].float()


@torch.no_grad()
def main(weights, names):
    visual, ps, pc = load(weights)
    dev = 'cpu'
    for name in names:
        files = sorted(p for p in (HERE.parent / name / 'out').glob('*.png') if not p.name.startswith('sheet'))
        dst = OUT / f'emb_{name}.npz'
        st, ct = [], []
        for i in range(0, len(files), 16):
            x = torch.stack([PRE(Image.open(p).convert('RGB')) for p in files[i:i + 16]]).to(dev)
            f = visual(x).float()
            st.append(torch.nn.functional.normalize(f @ ps, dim=1).numpy())
            ct.append(torch.nn.functional.normalize(f @ pc, dim=1).numpy())
        np.savez(dst, files=np.array([p.name for p in files]), style=np.concatenate(st), content=np.concatenate(ct))
        print(name, len(files), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
