"""ComfyUIのAPIに依頼を送り、出来た画像を受け取る小さな部品（V3検証用）。"""
import json
import time
import uuid
import urllib.parse
import urllib.request

HOST = 'http://127.0.0.1:8188'
CKPT = 'illustrious\\waiIllustriousSDXL_v160.safetensors'
NEG = 'lowres, bad anatomy, bad hands, extra digits, fewer digits, worst quality, low quality, jpeg artifacts, signature, watermark, username, blurry'


def _req(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(HOST + path, data=body, headers={'Content-Type': 'application/json'} if body else {})
    with urllib.request.urlopen(r, timeout=600) as f:
        return f.read()


def queue(graph):
    cid = uuid.uuid4().hex
    res = json.loads(_req('/prompt', {'prompt': graph, 'client_id': cid}))
    return res['prompt_id']


def wait(pid, poll=0.5, limit=1800):
    t0 = time.time()
    while time.time() - t0 < limit:
        h = json.loads(_req('/history/' + pid))
        if pid in h:
            st = h[pid].get('status', {})
            if st.get('status_str') == 'error':
                raise RuntimeError(json.dumps(st, ensure_ascii=False)[:2000])
            if st.get('completed'):
                return h[pid]
        time.sleep(poll)
    raise TimeoutError(pid)


def images(hist):
    out = []
    for node in hist['outputs'].values():
        for im in node.get('images', []):
            q = urllib.parse.urlencode({'filename': im['filename'], 'subfolder': im['subfolder'], 'type': im['type']})
            out.append(_req('/view?' + q))
    return out


def run(graph):
    """依頼を送り、終わるまで待ち、(画像のバイト列の一覧, かかった秒数) を返す。"""
    t0 = time.time()
    h = wait(queue(graph))
    return images(h), time.time() - t0


def upload(path, name=None):
    """画像をComfyUIのinputフォルダに送る。"""
    import mimetypes
    name = name or path.replace('\\', '/').split('/')[-1]
    boundary = uuid.uuid4().hex
    data = open(path, 'rb').read()
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f'Content-Type: {mimetypes.guess_type(name)[0] or "image/png"}\r\n\r\n').encode() + data + \
           f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{boundary}--\r\n'.encode()
    r = urllib.request.Request(HOST + '/upload/image', data=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urllib.request.urlopen(r) as f:
        return json.loads(f.read())['name']


def t2i(pos, seed, w=832, h=1216, steps=25, cfg=5.0, neg=NEG, sampler='euler_ancestral', scheduler='normal', prefix='v3poc'):
    """文字から絵を作る基本の手順（SDXL）。"""
    return {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': CKPT}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': pos, 'clip': ['1', 1]}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': neg, 'clip': ['1', 1]}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': w, 'height': h, 'batch_size': 1}},
        '5': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0], 'latent_image': ['4', 0],
                                                    'seed': seed, 'steps': steps, 'cfg': cfg, 'sampler_name': sampler, 'scheduler': scheduler, 'denoise': 1.0}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
        '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': prefix}},
    }
