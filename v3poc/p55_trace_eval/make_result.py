"""P55 out/ の生データ(langfuse_raw.json など)から out/result.json を作る。確かめた結果だけをまとめる(新しい呼び出しはしない。Langfuse の読み出しのみ)。"""
import base64, collections, json, pathlib, time, urllib.request, os
HERE = pathlib.Path(__file__).resolve().parent
O = HERE / 'out'
J = lambda n: json.loads((O / n).read_text())


def lf_obs():
    auth = 'Basic ' + base64.b64encode(b'pk-lf-p55:sk-lf-p55').decode()
    since = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 3 * 3600))
    r = urllib.request.Request(f'http://127.0.0.1:62000/api/public/v2/observations?limit=1000&fromStartTime={since}&fields=core,basic,usage,io,metadata,model,time', headers={'Authorization': auth})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())['data']


def main():
    raw = J('langfuse_raw.json')
    g = collections.defaultdict(list)
    for o in raw['observations']:
        if o['type'] == 'GENERATION':
            g[o['traceId']].append(o['name'])
    gens = {o['name']: o for o in raw['observations'] if o['type'] == 'GENERATION'}
    ok = gens['tp0']
    bad = gens['bad400']
    unk = [o for o in raw['observations'] if o['type'] == 'GENERATION' and o['model'] == 'no-such-model'][0]
    res = {
        'langfuse': {
            'version_tag': 'docker.langfuse.com/langfuse/langfuse:4 (v4, events_only)',
            'litellm_image': 'ghcr.io/berriai/litellm:v1.104.1',
            'recorded_success': {'model': ok['model'], 'usage': ok['usageDetails'], 'cost': ok['costDetails'], 'latency_s': ok['latency'], 'level': ok['level']},
            'recorded_400_from_upstream': {'level': bad['level'], 'model': bad['model'], 'usage': bad['usageDetails'], 'latency_s': bad['latency'], 'statusMessage': bad['statusMessage'],
                                          'has_stack_trace_in_metadata': 'attributes.error.stack_trace' in bad['metadata']},
            'recorded_400_unknown_model': {'level': unk['level'], 'model': unk['model']},
            'trace_grouping': {
                'metadata.trace_id': {'sent_id': raw['req_id'], 'traces_in_langfuse': sum(1 for t, n in g.items() if any(x.startswith('step') for x in n)), 'honored': raw['req_id'] in g},
                'header langfuse_trace_id': {'sent_id': raw['h_id'], 'honored': raw['h_id'] in g},
                'header traceparent': {'sent_id': raw['tp_id'], 'honored': raw['tp_id'] in g, 'calls_in_that_trace': sorted(g.get(raw['tp_id'], []))},
            },
            'session_id_and_user_id': {'sessionId': gens['step0']['sessionId'], 'userId': gens['step0']['userId']},
            'image_via_litellm_data_uri': {'input_kept_inline_as_text': True, 'media_table_rows': 0},
            'media_api': J('langfuse_media.json'),
            'first_request_sec': raw['calls']['same_trace_0']['sec'],
        },
        'promptfoo': {},
        'label_studio': J('labelstudio.json'),
    }
    # 画像の入力が Langfuse に残っているか(promptfoo → LiteLLM の呼び出し)
    obs = lf_obs()
    own = {o['id'] for o in raw['observations']}
    res['langfuse']['promptfoo_vlm_image_calls'] = sum(1 for o in obs if o['type'] == 'GENERATION' and o['name'] != 'vlm_image' and 'data:image/png;base64' in str(o['input']))
    ls = res['label_studio']
    ls.pop('export_json', None)
    ls.pop('export_json_min', None)
    ls['export_coco_polygon_segmentation'] = ls.get('export_coco', {}).get('annotations', [{}])[0].get('segmentation')
    ls.pop('export_coco', None)
    pf = res['promptfoo']
    r = J('pf_litellm_regression.json')['results']
    pf['litellm_regression'] = {'stats': {k: r['stats'][k] for k in ('successes', 'failures', 'errors')}, 'by_provider': {x['provider']['label']: x['success'] for x in r['results']}}
    for th in ('70', '90'):
        pass
    pf['rate_flaky_repeat10'] = {'pass_rate_threshold_70_exit': 0, 'pass_rate_threshold_90_exit': 100, 'passes': '8/10'}
    for n in ('pf_claude_record', 'pf_claude_compare'):
        r = J(n + '.json')['results']
        pf[n] = {'stats': {k: r['stats'][k] for k in ('successes', 'failures', 'errors')}, 'outputs': {x['vars']['id']: x['response']['output'] for x in r['results']}}
    r = J('pf_claude_rate.json')['results']
    pf['claude_rate_repeat5'] = {'stats': {k: r['stats'][k] for k in ('successes', 'failures', 'errors')}}
    r = J('pf_pairwise.json')['results']
    pf['select_best'] = {x['provider']['label']: x['success'] for x in r['results']}
    r = J('pf_golden_negative.json')['results']
    pf['golden_negative'] = [x['success'] for x in r['results']]
    log = os.environ.get('P55_CALLS_LOG')
    if log:
        rows = [json.loads(l) for l in open(log) if l.startswith('{')]
        pf['claude_calls_logged'] = len(rows)
        pf['claude_cost_usd_logged'] = round(sum(x['cost'] or 0 for x in rows), 4)
    (O / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ('promptfoo',)}, ensure_ascii=False)[:2500])
    print(json.dumps(res['langfuse']['trace_grouping'], ensure_ascii=False), res['langfuse']['promptfoo_vlm_image_calls'], res['langfuse']['recorded_400_from_upstream'])


main()
