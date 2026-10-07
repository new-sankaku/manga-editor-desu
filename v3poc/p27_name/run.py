"""P27 LLM にネーム（ページ・コマ・写し方・セリフ）を作らせたとき、どんな問題を起こすか（一覧 2-3〜2-16）。
あらすじ2本 × 3回。Sonnet（Claude Code の claude -p）。出力は JSON。
機械で数えられるものは check.py で数え、話の流れは目で読む（out/labels.json）。
使い方: python run.py <空フォルダ> [モデル]"""
import concurrent.futures as cf
import json
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
CWD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
MODEL = sys.argv[2] if len(sys.argv) > 2 else 'sonnet'
RUNS = 3

PLOTS = {
    'school': {
        'pages': 6,
        'plot': '転校生の少女・水瀬が、主人公の少年・高木の隣の席になる。水瀬は教科書を忘れていて、高木が見せる。'
                '放課後、高木は自分の教科書にはさまったメモを見つける。メモには、水瀬が幼いころ高木と会っていたことが書かれている。',
        'charas': '高木（高校2年の男子。口数が少なく、ぶっきらぼうな話し方。「〜だろ」「別に」）\n'
                  '水瀬（高校2年の女子。転校生。明るく丁寧な話し方。「〜ですよね」「ありがとうございます」）\n'
                  '担任（中年の男性教師。のんびりした話し方）',
    },
    'harbor': {
        'pages': 8,
        'plot': '夜の港で、運び屋の女・カヤが、追手の二人組から小さな荷物を守って逃げる。コンテナの間で追い詰められるが、'
                '荷物の中身（目覚まし時計のような装置）を鳴らして追手の気をそらし、出港する船に飛び乗る。'
                '船の上で送り状を見ると、送り先は長く会っていない妹だった。',
        'charas': 'カヤ（20代の女性の運び屋。冷静で短く話す。「行くよ」「黙って」）\n'
                  '追手A（大柄な男。乱暴な話し方）\n追手B（細身の男。丁寧だが冷たい話し方）',
    },
}

PROMPT = """あなたは日本の漫画のネームを切る人です。次のあらすじから、{pages}ページの読み切りのネームを作ってください。

あらすじ：
{plot}

登場人物（話し方）：
{charas}

本の決まり：右から左へ読む本です。1ページ目は左のページで、そのあとは右・左の順に並びます。左のページの次はめくりになります。
コマは各ページの中で右上から左下へ読みます。

各コマについて、次を決めてください。どれも選び方で読みやすさが変わります。
・大きさ（大・中・小）：大きいコマは見せ場が立つが、多いとどれも立たなくなる
・形（四角・斜め・枠なし・断ち切り）：四角以外は勢いが出るが、読む順が迷いやすくなり、多いと見づらい
・写す範囲（遠景・引き・全身・膝上・胸から上・顔・部分）：遠くから写すと場所と位置関係が分かり、近くから写すと感情が伝わる。同じ範囲が続くと単調になる
・角度（目の高さ・見下ろし・見上げ・真横・背後・真上）：変えると変化が付くが、理由のない角度は読む人を迷わせる
・写る人物ごとの顔の大きさ（大・中・小・見えない）と向き（右・左・正面・後ろ）
・背景（描き込む・簡略・なし・効果線やトーンだけ）：描くと場所が分かり、省くと人物に目が行く
・場面の番号（場所か時間が変わったら次の番号）
・話の中での役目（起・承・転・結のどれか）
・ページの最後のコマなら、次のページを読ませる引きになっているか（はい・いいえ）
・吹き出し（話す人・種類（台詞・叫び・心の声・ナレーション）・文）と描き文字の擬音
・コマの中身（何が描かれているか）

各ページについて、段の分け方（上から順に、各段に入るコマの番号を右から並べたもの）と、見開きにするかを決めてください。

出力はJSONだけにしてください。説明は書かないでください。形式：
{{"pages":[{{"page":ページ番号,"spread":真偽,"rows":[[コマ番号,...],...],"panels":[{{"n":コマ番号,"size":"...","shape":"...","shot":"...","angle":"...",
"people":[{{"name":"...","face":"...","facing":"..."}}],"background":"...","scene":場面の番号,"role":"...","hook":真偽,"content":"...",
"balloons":[{{"speaker":"...","kind":"...","text":"..."}}],"sfx":["..."]}}]}}]}}
コマ番号は作品の最初から通し番号にしてください。"""


def ask(prompt):
    t0 = time.time()
    r = subprocess.run(['claude', '-p', '--model', MODEL, '--output-format', 'json', '--max-turns', '1'],
                       input=prompt, capture_output=True, text=True, encoding='utf-8', cwd=str(CWD), timeout=1200)
    j = json.loads(r.stdout)
    txt = j.get('result', '')
    m = re.search(r'\{.*\}', txt, re.S)
    return (json.loads(m.group(0)) if m else None), txt, round(time.time() - t0, 1), j.get('total_cost_usd')


def one(key, run):
    f = OUT / f'{key}_{MODEL}_{run}.json'
    if f.exists():
        return f.name
    p = PLOTS[key]
    d, txt, sec, cost = ask(PROMPT.format(**p))
    f.write_text(json.dumps({'plot': key, 'run': run, 'model': MODEL, 'sec': sec, 'cost_usd': cost, 'name': d, 'raw': None if d else txt},
                            ensure_ascii=False, indent=1), encoding='utf-8')
    return f.name


def main():
    (OUT / 'prompt.json').write_text(json.dumps({'prompt': PROMPT, 'plots': PLOTS}, ensure_ascii=False, indent=1), encoding='utf-8')
    with cf.ThreadPoolExecutor(3) as ex:
        for r in ex.map(lambda a: one(*a), [(k, i) for k in PLOTS for i in range(1, RUNS + 1)]):
            print(r, flush=True)


if __name__ == '__main__':
    main()
