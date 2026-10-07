"""試作の依頼を順に流す小さな部品。出来ている画像は作り直さない（途中で止めても続きから流せる）。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import comfy  # noqa: E402


def upload_once(path, name):
    """画像を ComfyUI の input に送り、その名前を返す。"""
    return comfy.upload(str(path), name)


def run_jobs(out, jobs, meta=None):
    """jobs: [{'file': 出力名, 'graph': 手順, ...記録したい値}]。gen.json に条件と時間を残す。"""
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rec_path = out / 'gen.json'
    old = json.loads(rec_path.read_text(encoding='utf-8')) if rec_path.exists() else {}
    done = {r['file']: r for r in old.get('runs', [])}
    runs = []
    for j in jobs:
        f = j['file']
        row = {k: v for k, v in j.items() if k != 'graph'}
        if (out / f).exists() and f in done:
            runs.append(done[f])
            continue
        imgs, sec = comfy.run(j['graph'])
        (out / f).write_bytes(imgs[-1])
        row['sec'] = round(sec, 1)
        runs.append(row)
        print(f, row['sec'], flush=True)
        rec_path.write_text(json.dumps({**(meta or {}), 'ckpt': comfy.CKPT, 'runs': runs + [done[k] for k in done if k not in {r['file'] for r in runs}]},
                                       ensure_ascii=False, indent=1), encoding='utf-8')
    rec_path.write_text(json.dumps({**(meta or {}), 'ckpt': comfy.CKPT, 'runs': runs}, ensure_ascii=False, indent=1), encoding='utf-8')
    return runs
