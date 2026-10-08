"""P55 その1 Langfuse(自前で立てる版)に LiteLLM の呼び出しが記録されるか。
確かめること:
 - LiteLLM(v3/server と同じ版 v1.104.1)の langfuse_otel 連携で、モデル・トークン数・費用・時間・失敗が残るか
 - metadata の trace_id で複数の呼び出しを1つの trace にまとめられるか
 - 画像(入力の絵)を付けられるか
前提: compose.yaml を `docker compose -p p55 up -d` で立ててある。結果は out/langfuse_raw.json
"""
import base64, json, time, uuid, urllib.request, urllib.error, pathlib
HERE = pathlib.Path(__file__).resolve().parent
LL = 'http://127.0.0.1:62400'
LF = 'http://127.0.0.1:62000'
AUTH_LF = 'Basic ' + base64.b64encode(b'pk-lf-p55:sk-lf-p55').decode()


def http(method, url, body=None, headers=None):
    h = {'Content-Type': 'application/json'}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'null'), time.time() - t
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw), time.time() - t
        except Exception:
            return e.code, raw.decode()[:500], time.time() - t


def chat(model, content, meta=None, extra=None, hdr=None):
    body = {'model': model, 'messages': [{'role': 'user', 'content': content}]}
    if meta:
        body['metadata'] = meta
    body.update(extra or {})
    return http('POST', LL + '/v1/chat/completions', body, dict({'Authorization': 'Bearer sk-p55'}, **(hdr or {})))


def lf(path):
    return http('GET', LF + path, headers={'Authorization': AUTH_LF})


def main():
    t_start = time.time()
    tag = uuid.uuid4().hex[:8]
    out = {'tag': tag, 'calls': {}}
    req_id = uuid.uuid4().hex  # 32桁の16進 = trace の ID の形
    # 1) 同じ依頼に属する3つの呼び出し(trace_id を metadata で渡す)
    for i in range(3):
        s, b, dt = chat('mock-vlm', f'質問{i} {tag}', {'trace_id': req_id, 'generation_name': f'step{i}', 'session_id': 'req-' + tag, 'trace_user_id': 'u1', 'tags': ['p55', tag]})
        out['calls'][f'same_trace_{i}'] = {'status': s, 'body': b, 'sec': dt}
    # 1b) W3C の traceparent ヘッダで依頼を渡す(OpenTelemetry の標準の方法)
    tp_id = uuid.uuid4().hex
    out['tp_id'] = tp_id
    out['req_id'] = req_id
    for i in range(3):
        s, b, dt = chat('mock-vlm', f'tp質問{i} {tag}', {'generation_name': f'tp{i}', 'tags': ['p55', tag, 'tp']},
                        hdr={'traceparent': f'00-{tp_id}-{uuid.uuid4().hex[:16]}-01'})
        out['calls'][f'traceparent_{i}'] = {'status': s, 'body': b, 'sec': dt}
    # 1c) langfuse_trace_id ヘッダ(LiteLLM の langfuse_* ヘッダ)
    h_id = uuid.uuid4().hex
    out['h_id'] = h_id
    for i in range(2):
        s, b, dt = chat('mock-vlm', f'h質問{i} {tag}', {'generation_name': f'h{i}', 'tags': ['p55', tag, 'hdr']}, hdr={'langfuse_trace_id': h_id})
        out['calls'][f'header_{i}'] = {'status': s, 'body': b, 'sec': dt}
    # 2) 依頼の指定なし(別の trace になるはず)
    s, b, dt = chat('mock-vlm', f'単独 {tag}', {'tags': ['p55', tag]})
    out['calls']['single'] = {'status': s, 'body': b, 'sec': dt}
    # 3) 画像つき(data URI)
    img = base64.b64encode((HERE / 'out/page1.png').read_bytes()).decode()
    content = [{'type': 'text', 'text': f'この絵を評価 {tag}'}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + img}}]
    s, b, dt = chat('mock-vlm', content, {'trace_id': uuid.uuid4().hex, 'generation_name': 'vlm_image', 'tags': ['p55', tag]})
    out['calls']['image'] = {'status': s, 'body': b, 'sec': dt}
    out['image_trace_id'] = None
    # 4) 失敗: 呼び先が400を返す
    s, b, dt = chat('mock-bad', f'失敗 {tag}', {'generation_name': 'bad400', 'tags': ['p55', tag]})
    out['calls']['bad_upstream'] = {'status': s, 'body': b, 'sec': dt}
    # 5) 失敗: 無いモデル名
    s, b, dt = chat('no-such-model', f'無い {tag}', {'tags': ['p55', tag]})
    out['calls']['unknown_model'] = {'status': s, 'body': b, 'sec': dt}
    out['wait'] = 'ingest'
    time.sleep(40)
    # Langfuse v4 は events_only 動作で、/api/public/traces と /observations は使えない。v2 の observations を使う
    obs, cur = [], None
    since = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t_start - 5))
    while True:
        q = f'/api/public/v2/observations?limit=1000&fromStartTime={since}&fields=core,basic,usage,io,metadata,model,time'
        if cur:
            q += '&cursor=' + cur
        s, page, _ = lf(q)
        if s != 200:
            out['observations_error'] = [s, page]
            break
        obs += page['data']
        cur = (page.get('meta') or {}).get('cursor')
        if not cur:
            break
    out['observations'] = obs
    (HERE / 'out/langfuse_raw.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: (v['status'] if isinstance(v, dict) and 'status' in v else None) for k, v in out['calls'].items()}))
    print('observations', len(obs))


main()
