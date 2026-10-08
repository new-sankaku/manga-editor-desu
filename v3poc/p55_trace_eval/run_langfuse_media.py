"""P55 その1b 画像を Langfuse の「メディア」として付けられるか。
LiteLLM 経由(data URI を messages に入れる)だと入力の文字列にそのまま残る(run_langfuse.py)。
ここでは Langfuse 側のメディア API(署名つきURLでMinIOに置く)で付けられるか、参照の文字列が読み戻しで解決されるかを確かめる。
結果は out/langfuse_media.json
"""
import base64, hashlib, json, pathlib, time, uuid, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
LF = 'http://127.0.0.1:62000'
AUTH = 'Basic ' + base64.b64encode(b'pk-lf-p55:sk-lf-p55').decode()


def call(method, url, body=None, headers=None, raw=None):
    h = {'Authorization': AUTH, 'Content-Type': 'application/json'}
    h.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return r.status, (json.loads(b) if b[:1] in (b'{', b'[') else b[:100])
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:400].decode()


def main():
    out = {}
    png = (HERE / 'out/page1.png').read_bytes()
    sha = base64.b64encode(hashlib.sha256(png).digest()).decode()
    trace_id = uuid.uuid4().hex
    obs_id = uuid.uuid4().hex[:16]
    ts = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    # v4 の ingestion API は score だけ。generation は OTLP で送る
    s, m = call('POST', LF + '/api/public/media', {'traceId': trace_id, 'observationId': obs_id, 'field': 'input', 'contentType': 'image/png', 'contentLength': len(png), 'sha256Hash': sha})
    out['media_create'] = [s, m]
    if s in (200, 201):
        mid = m['mediaId']
        if m.get('uploadUrl'):
            req = urllib.request.Request(m['uploadUrl'], data=png, method='PUT', headers={'Content-Type': 'image/png', 'x-amz-checksum-sha256': sha})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    out['put'] = r.status
            except urllib.error.HTTPError as e:
                out['put'] = [e.code, e.read()[:300].decode()]
        out['patch'] = call('PATCH', f'{LF}/api/public/media/{mid}', {'uploadedAt': ts, 'uploadHttpStatus': 200, 'uploadHttpError': None})
        out['get'] = call('GET', f'{LF}/api/public/media/{mid}')
        out['download'] = None
        if isinstance(out['get'][1], dict) and out['get'][1].get('url'):
            with urllib.request.urlopen(out['get'][1]['url'], timeout=30) as r:
                out['download'] = [r.status, len(r.read())]
        ref = f'@@@langfuseMedia:type=image/png|id={mid}|source=bytes@@@'
        inp = json.dumps([{'role': 'user', 'content': [{'type': 'text', 'text': 'この絵'}, {'type': 'image_url', 'image_url': {'url': ref}}]}], ensure_ascii=False)
        now = int(time.time() * 1e9)
        sv = lambda k, v: {'key': k, 'value': {'stringValue': v}}
        span = {'traceId': trace_id, 'spanId': obs_id, 'name': 'p55-media-gen', 'kind': 1, 'startTimeUnixNano': str(now), 'endTimeUnixNano': str(now + 10**9),
                'attributes': [sv('langfuse.observation.type', 'generation'), sv('langfuse.observation.input', inp), sv('langfuse.observation.output', 'ok'), sv('gen_ai.request.model', 'mock-vlm')]}
        body = {'resourceSpans': [{'resource': {'attributes': [sv('service.name', 'p55')]}, 'scopeSpans': [{'scope': {'name': 'p55'}, 'spans': [span]}]}]}
        out['otlp_post'] = call('POST', LF + '/api/public/otel/v1/traces', body)
        time.sleep(25)
        s, o = call('GET', f'{LF}/api/public/v2/observations?limit=10&fromStartTime={time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()-120))}&fields=core,basic,io')
        if s == 200:
            for x in o['data']:
                if x['traceId'] == trace_id:
                    out['readback_input'] = str(x['input'])[:400]
        else:
            out['readback_error'] = [s, o]
    (HERE / 'out/langfuse_media.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(out, ensure_ascii=False, default=str)[:1500])


main()
