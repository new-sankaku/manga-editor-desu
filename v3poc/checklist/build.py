"""llm_doc/V3検証の一覧.md から、メモを書ける一覧のHTML（checklist.html）を作る。
試作の結果は results.json（{"行番号": {"state": "済|一部|未実施|検証しない", "text": "...", "link": "相対パス"}}）から載せる。
使い方: python build.py"""
import html
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / 'llm_doc' / 'V3検証の一覧.md'
RES = HERE / 'results.json'


def parse():
    secs, cur, sub, head = [], None, None, None
    for line in SRC.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^## (\d+)\. (.+)', line)
        if m:
            cur = {'no': m.group(1), 'title': m.group(2), 'rows': []}
            secs.append(cur)
            sub = None
            continue
        m = re.match(r'^### (.+)', line)
        if m and cur:
            sub = m.group(1)
            continue
        if cur and line.startswith('| #'):
            head = [c.strip() for c in line.strip('|').split('|')]
            continue
        m = re.match(r'^\| (\d+-\d+) \|', line)
        if m and cur:
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            cur['rows'].append({'id': cells[0], 'sub': sub, 'text': cells[1],
                                'extra': [[h, c] for h, c in zip(head[2:], cells[2:])]})
    return secs


def main():
    data = {'secs': parse(), 'results': json.loads(RES.read_text(encoding='utf-8')) if RES.exists() else {}}
    tpl = (HERE / 'template.html').read_text(encoding='utf-8')
    out = tpl.replace('/*DATA*/null', json.dumps(data, ensure_ascii=False))
    (HERE / 'checklist.html').write_text(out, encoding='utf-8')
    n = sum(len(s['rows']) for s in data['secs'])
    print(n, 'rows,', len(data['results']), 'results')


if __name__ == '__main__':
    main()
