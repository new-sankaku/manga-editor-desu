"""P39 絵として描かれた擬音（描き文字）を、機械がどこまで読めるか（一覧 6-2、細部9章の3）。
描き文字を文字の層として置いておけば読み取りは要らない。絵の中から読み取るしかない場合にどれだけ落ちるかを、
吹き出しの中の台詞と比べて見る。実際の漫画のページ3枚を Sonnet に読ませ、正誤は人が付ける（out_local/labels.json）。
ページは他人の作品なので、画像も読み取り結果も out_local に置き、リポジトリにも公開物にも入れない。数だけを結果に書く。
使い方: python run.py <空フォルダ> [ページのファイル名 ...]（読んだページは読み直さない）"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out_local'
SRC = pathlib.Path(r'C:\01_work\00_Git\kaguya-m2m\testdata\naname')
PAGES = [a for a in sys.argv[2:]] or ['013.png', '017.png', '018.png']
CWD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
PROMPT = """次の画像ファイルは漫画の1ページです。読んでください。
{file}

このページの文字を、次の2種類に分けてすべて書き出してください。
・台詞：吹き出しの中や、枠の中に活字で書かれた文字
・描き文字：絵の一部として手で描かれた擬音・擬態語（効果音）
読めない・自信が無いものは、読めた部分だけを書き、確かさを「低」にしてください。無理に読むと、存在しない文字を翻訳に回すことになります。
それぞれに、どのコマのどのあたりか（右上のコマの左下、など）を添えてください。

出力はJSONだけにしてください。形式：{{"serif":[{{"where":"位置","text":"文字","sure":"高か低"}}],"sfx":[{{"where":"位置","text":"文字","sure":"高か低"}}]}}"""


def main():
    f = OUT / 'read.json'
    res = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
    for p in PAGES:
        if p in res:
            continue
        r = subprocess.run(['claude', '-p', '--model', 'sonnet', '--output-format', 'json', '--allowedTools', 'Read', '--max-turns', '6'],
                           input=PROMPT.format(file=SRC / p), capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=900)
        j = json.loads(r.stdout)
        m = re.search(r'\{.*\}', j.get('result', ''), re.S)
        res[p] = {'read': json.loads(m.group(0)) if m else None, 'cost_usd': j.get('total_cost_usd')}
        print(p, len(res[p]['read']['serif']) if m else None, len(res[p]['read']['sfx']) if m else None, flush=True)
    (OUT / 'read.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
