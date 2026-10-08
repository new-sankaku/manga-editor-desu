"""P55 その3 Label Studio(Community 1.23.2, Docker)。
確かめること:
 - 漫画のページの絵に コマの多角形・人物の枠・吹き出しの枠 を付ける labeling config が通るか
 - API で プロジェクト作成・画像の取り込み(アップロード)・付けた結果(annotation)の登録・JSON の書き出しができるか
 - 書き出しの多角形の座標が画素か割合か(original_width/height との関係)
 - 機械の下書き(predictions)を取り込めるか、COCO の書き出しの座標の単位
結果は out/labelstudio.json
"""
import json, pathlib, urllib.request, urllib.error, uuid
HERE = pathlib.Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:62080'
EMAIL, PASSWORD = 'p55@example.com', 'p55password'
AUTH = {}


def get_access_token():
    """1.23 の既定は旧式トークン(Token xxx)が無効。ログインしたセッションで個人用トークン(PAT)を作り、アクセス用トークンに換える。"""
    import http.cookiejar, os
    pat = os.environ.get('LS_PAT')
    if pat:  # 作成済みの PAT。一覧 API は署名を伏せるので、作成時に控えておく必要がある
        return refresh(pat)
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.open(BASE + '/user/login/').read()
    csrf = [c.value for c in cj if c.name == 'csrftoken'][0]
    data = f'csrfmiddlewaretoken={csrf}&email={EMAIL}&password={PASSWORD}'.encode()
    op.open(urllib.request.Request(BASE + '/user/login/', data=data, headers={'Referer': BASE + '/user/login/'})).read()
    csrf = [c.value for c in cj if c.name == 'csrftoken'][0]
    try:
        r = op.open(urllib.request.Request(BASE + '/api/token', data=b'{}', headers={'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'Referer': BASE + '/'}, method='POST'))
        pat = json.loads(r.read())['token']
    except urllib.error.HTTPError as e:
        if e.code != 409:  # 409 は作成済み。一覧から取る
            raise
        raise SystemExit('PAT は作成済み。作成時の値を環境変数 LS_PAT に入れてください(一覧は署名が伏せられる)')
    return refresh(pat)


def refresh(pat):
    r = urllib.request.urlopen(urllib.request.Request(BASE + '/api/token/refresh', data=json.dumps({'refresh': pat}).encode(), headers={'Content-Type': 'application/json'}, method='POST'))
    return json.loads(r.read())['access']

CONFIG = '''<View>
  <Image name="image" value="$image" zoom="true"/>
  <PolygonLabels name="panel" toName="image" strokeWidth="2" pointSize="small" opacity="0.3">
    <Label value="コマ" background="#2f7cf6"/>
  </PolygonLabels>
  <RectangleLabels name="box" toName="image" strokeWidth="2">
    <Label value="人物" background="#e8590c"/>
    <Label value="吹き出し" background="#2b8a3e"/>
  </RectangleLabels>
</View>'''


def req(method, path, body=None, headers=None, raw=None, ctype='application/json'):
    h = {'Authorization': 'Bearer ' + AUTH['t']}
    if raw is None and body is not None:
        h['Content-Type'] = ctype
    h.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            b = resp.read()
            try:
                return resp.status, json.loads(b)
            except Exception:
                return resp.status, b.decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:600].decode('utf-8', 'replace')


def multipart(fname, content, ctype):
    bd = uuid.uuid4().hex
    body = (f'--{bd}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n').encode() + content + f'\r\n--{bd}--\r\n'.encode()
    return body, {'Content-Type': 'multipart/form-data; boundary=' + bd}


def main():
    out = {}
    AUTH['t'] = get_access_token()
    s, p = req('POST', '/api/projects', {'title': 'p55 manga page', 'label_config': CONFIG})
    out['project_create'] = s
    pid = p['id']
    # 不正な config は弾かれるか
    out['bad_config'] = req('POST', '/api/projects/%d/validate/' % pid, {'label_config': '<View><Image name="image" value="$image"/><PolygonLabels name="p" toName="nonexist"><Label value="x"/></PolygonLabels></View>'})
    # 画像のアップロード(取り込み)
    body, hh = multipart('page1.png', (HERE / 'out/page1.png').read_bytes(), 'image/png')
    s, imp = req('POST', f'/api/projects/{pid}/import?commit_to_project=true', raw=body, headers=hh)
    out['import_upload'] = [s, imp]
    # 機械の下書き付きのタスク(JSON で取り込み)
    pred_poly = [[5, 5], [48, 5], [48, 48], [5, 48]]
    task = [{'data': {'image': '/data/upload/placeholder'}}]
    s, tasks = req('GET', f'/api/projects/{pid}/tasks?page_size=10')
    out['tasks'] = s
    tl = tasks if isinstance(tasks, list) else tasks.get('tasks', [])
    tid = tl[0]['id']
    out['task_data'] = tl[0]['data']
    # 人が付けたのと同じ形の結果(割合)を API で登録
    res = [
        {'id': 'r1', 'type': 'polygonlabels', 'from_name': 'panel', 'to_name': 'image', 'original_width': 320, 'original_height': 240, 'image_rotation': 0,
         'value': {'points': [[5, 5], [48, 5], [48, 48], [5, 48]], 'polygonlabels': ['コマ'], 'closed': True}},
        {'id': 'r2', 'type': 'rectanglelabels', 'from_name': 'box', 'to_name': 'image', 'original_width': 320, 'original_height': 240, 'image_rotation': 0,
         'value': {'x': 10, 'y': 10, 'width': 20, 'height': 30, 'rotation': 0, 'rectanglelabels': ['人物']}},
        {'id': 'r3', 'type': 'rectanglelabels', 'from_name': 'box', 'to_name': 'image', 'original_width': 320, 'original_height': 240, 'image_rotation': 0,
         'value': {'x': 30, 'y': 8, 'width': 15, 'height': 10, 'rotation': 0, 'rectanglelabels': ['吹き出し']}},
    ]
    s, ann = req('POST', f'/api/tasks/{tid}/annotations', {'result': res, 'ground_truth': False})
    out['annotation_create'] = [s, (ann if s >= 300 else {'id': ann['id']})]
    # 機械の下書き(predictions)
    s, pr = req('POST', '/api/predictions', {'task': tid, 'model_version': 'p55-mock', 'result': [
        {'type': 'polygonlabels', 'from_name': 'panel', 'to_name': 'image', 'original_width': 320, 'original_height': 240, 'value': {'points': [[52, 52], [95, 52], [95, 95], [52, 95]], 'polygonlabels': ['コマ'], 'closed': True}}]})
    out['prediction_create'] = [s, pr if s >= 300 else {'id': pr['id']}]
    # 書き出し
    s, js = req('GET', f'/api/projects/{pid}/export?exportType=JSON&download_all_tasks=true')
    out['export_json_status'] = s
    out['export_json'] = js
    s, mn = req('GET', f'/api/projects/{pid}/export?exportType=JSON_MIN')
    out['export_json_min_status'] = s
    out['export_json_min'] = mn
    import io, zipfile
    r = urllib.request.urlopen(urllib.request.Request(BASE + f'/api/projects/{pid}/export?exportType=COCO', headers={'Authorization': 'Bearer ' + AUTH['t']}))
    z = zipfile.ZipFile(io.BytesIO(r.read()))
    out['export_coco_files'] = z.namelist()
    out['export_coco'] = json.loads(z.read('result.json'))
    s, fm = req('GET', f'/api/projects/{pid}/export/formats')
    out['formats'] = [f.get('name') for f in fm] if isinstance(fm, list) else fm
    # 画素への換算の確認
    try:
        a = js[0]['annotations'][0]['result'][0]
        w, h = a['original_width'], a['original_height']
        out['pixel_from_percent'] = [[round(x * w / 100, 1), round(y * h / 100, 1)] for x, y in a['value']['points']]
    except Exception as e:
        out['pixel_error'] = repr(e)
    (HERE / 'out/labelstudio.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k in ('export_json', 'export_coco', 'pixel_from_percent', 'export_json_min')}, ensure_ascii=False, default=str)[:3500])


main()
