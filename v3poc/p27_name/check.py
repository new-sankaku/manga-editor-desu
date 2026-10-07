"""P27 のネームを機械で数える（一覧 2-3〜2-16 のうち、数で見られるもの）。結果は out/check.json と、読むための out/text_*.txt。
使い方: python check.py"""
import collections
import glob
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
TALK_KINDS = {'台詞', '心の声'}


def one(d):
    pages = d['pages']
    panels = [p for pg in pages for p in pg['panels']]
    r = {'pages': len(pages), 'panels': len(panels)}
    r['panels_per_page'] = [len(pg['panels']) for pg in pages]
    # 読む順：段の中は右から、段は上から。番号が増えていくか
    breaks = 0
    for pg in pages:
        seq = [n for row in pg['rows'] for n in row]
        breaks += sum(1 for a, b in zip(seq, seq[1:]) if b != a + 1)
        if sorted(seq) != sorted(p['n'] for p in pg['panels']):
            breaks += 1
    r['order_breaks'] = breaks
    pats = [tuple(len(row) for row in pg['rows']) for pg in pages]
    r['row_patterns'] = [list(p) for p in pats]
    r['same_pattern_next_page'] = sum(1 for a, b in zip(pats, pats[1:]) if a == b)
    r['same_shot_angle_next'] = sum(1 for a, b in zip(panels, panels[1:]) if (a['shot'], a['angle']) == (b['shot'], b['angle']))
    r['size'] = dict(collections.Counter(p['size'] for p in panels))
    r['pages_without_big'] = sum(1 for pg in pages if not any(p['size'] == '大' for p in pg['panels']))
    r['shape'] = dict(collections.Counter(p['shape'] for p in panels))
    talk = [p for p in panels if p['balloons'] and all(b['kind'] in TALK_KINDS for b in p['balloons']) and not p.get('sfx')]
    r['talk_panels'] = len(talk)
    r['talk_panels_not_square'] = sum(1 for p in talk if p['shape'] not in ('四角',))
    r['shot'] = dict(collections.Counter(p['shot'] for p in panels))
    r['angle'] = dict(collections.Counter(p['angle'] for p in panels))
    r['unusual_angle_ratio'] = round(sum(1 for p in panels if p['angle'] != '目の高さ') / len(panels), 2)
    starts = []
    prev = None
    for p in panels:
        if p['scene'] != prev:
            starts.append(p['shot'])
            prev = p['scene']
    r['scene_start_shots'] = starts
    r['scene_start_wide'] = sum(1 for s in starts if s in ('遠景', '引き'))
    r['background'] = dict(collections.Counter(p['background'] for p in panels))
    r['role'] = dict(collections.Counter(p['role'] for p in panels))
    r['role_by_page'] = [''.join(p['role'] for p in pg['panels']) for pg in pages]
    # めくり：1ページ目は左。奇数ページ（左）の最後のコマの後にめくり
    r['hook_on_left_pages'] = [bool(pg['panels'][-1].get('hook')) for pg in pages if pg['page'] % 2 == 1]
    r['hook_on_right_pages'] = [bool(pg['panels'][-1].get('hook')) for pg in pages if pg['page'] % 2 == 0]
    r['spreads'] = sum(1 for pg in pages if pg.get('spread'))
    first = {}
    for p in panels:
        for x in p['people']:
            first.setdefault(x['name'], {'panel': p['n'], 'shot': p['shot'], 'face': x['face']})
    r['first_appearance'] = first
    r['people_per_panel_max'] = max(len(p['people']) for p in panels)
    bl = [b for p in panels for b in p['balloons']]
    lens = [len(b['text']) for b in bl]
    r['balloons'] = len(bl)
    r['balloon_len_mean'] = round(sum(lens) / len(lens), 1) if lens else 0
    r['balloon_len_max'] = max(lens) if lens else 0
    r['balloons_over_30'] = sum(1 for x in lens if x > 30)
    r['balloons_per_panel_max'] = max(len(p['balloons']) for p in panels)
    r['chars_per_page'] = [sum(len(b['text']) for p in pg['panels'] for b in p['balloons']) for pg in pages]
    r['sfx'] = sum(len(p.get('sfx', [])) for p in panels)
    return r


def text(d):
    lines = []
    for pg in d['pages']:
        lines.append(f'--- {pg["page"]}ページ 段{pg["rows"]} 見開き{pg.get("spread")}')
        for p in pg['panels']:
            ppl = '・'.join(f'{x["name"]}(顔{x["face"]}{x["facing"]})' for x in p['people'])
            bl = ' / '.join(f'{b["speaker"]}[{b["kind"]}]「{b["text"]}」' for b in p['balloons'])
            lines.append(f'{p["n"]} {p["size"]}{p["shape"]} {p["shot"]}{p["angle"]} 背景{p["background"]} 場面{p["scene"]} {p["role"]}'
                         f'{" 引き" if p.get("hook") else ""} | {p["content"]} | {ppl} | {bl} | {" ".join(p.get("sfx", []))}')
    return '\n'.join(lines)


def main():
    res = {}
    for f in sorted(glob.glob(str(OUT / '*_sonnet_*.json'))):
        d = json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
        key = pathlib.Path(f).stem
        res[key] = one(d['name'])
        (OUT / f'text_{key}.txt').write_text(text(d['name']), encoding='utf-8')
    (OUT / 'check.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, r in res.items():
        print(k, {x: r[x] for x in ('panels', 'order_breaks', 'same_pattern_next_page', 'same_shot_angle_next', 'pages_without_big', 'shape',
                                   'talk_panels', 'talk_panels_not_square', 'unusual_angle_ratio', 'scene_start_wide', 'hook_on_left_pages',
                                   'spreads', 'balloon_len_max', 'balloons_over_30', 'balloons_per_panel_max')})
        print('   role', r['role_by_page'], 'bg', r['background'], 'shot', r['shot'], 'starts', r['scene_start_shots'], 'first', r['first_appearance'])


if __name__ == '__main__':
    main()
