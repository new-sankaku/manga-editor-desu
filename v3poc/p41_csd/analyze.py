"""P41 CSD の特徴で、画風が分かれるか・中身に引きずられないかを数える。
P15：4絵柄（カラー・ペン・昔の漫画・トーン）×7狙い×3 seed。
  ・いちばん近い絵が同じ絵柄か（1つ抜き）を、画風の向きと中身の向きで比べる
  ・同じ絵柄で狙い違い／違う絵柄で狙い同じ の近さの平均
P16：同じ絵柄（トーン）で人物・場所・狙いが違う絵。近さの分布が P15 の「同じ絵柄」と同じ幅に収まるか
P25（あれば）：同じ絵柄の言葉で8場面を作った絵と、写実の言葉を足した絵。
使い方: python analyze.py"""
import json
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'


def load(name):
    d = np.load(OUT / f'emb_{name}.npz')
    keep = [i for i, f in enumerate(d['files']) if not f.endswith('_cut.png')]
    return [str(f) for f in d['files'][keep]], d['style'][keep], d['content'][keep]


def nn_acc(v, labels):
    s = v @ v.T
    np.fill_diagonal(s, -9)
    return round(float(np.mean([labels[i] == labels[int(np.argmax(s[i]))] for i in range(len(labels))])), 3)


def pair_means(v, a, b):
    s = v @ v.T
    same_a_diff_b, diff_a_same_b, diff_both = [], [], []
    n = len(a)
    for i in range(n):
        for j in range(i + 1, n):
            if a[i] == a[j] and b[i] != b[j]:
                same_a_diff_b.append(s[i, j])
            elif a[i] != a[j] and b[i] == b[j]:
                diff_a_same_b.append(s[i, j])
            elif a[i] != a[j]:
                diff_both.append(s[i, j])
    f = lambda x: round(float(np.mean(x)), 3)
    return {'same_style_diff_target': f(same_a_diff_b), 'diff_style_same_target': f(diff_a_same_b), 'diff_both': f(diff_both),
            'same_style_min': round(float(np.min(same_a_diff_b)), 3), 'diff_style_max': round(float(np.max(diff_a_same_b + diff_both)), 3)}


def main():
    res = {}
    files, st, ct = load('p15_shots')
    style = [f.split('_')[0] for f in files]
    target = ['_'.join(f.split('_')[1:-1]) for f in files]
    res['p15'] = {'n': len(files), 'nn_same_style_by_style_vec': nn_acc(st, style), 'nn_same_style_by_content_vec': nn_acc(ct, style),
                  'nn_same_target_by_style_vec': nn_acc(st, target), 'nn_same_target_by_content_vec': nn_acc(ct, target),
                  'style_vec': pair_means(st, style, target), 'content_vec': pair_means(ct, style, target)}
    per = {}
    s = st @ st.T
    for k in sorted(set(style)):
        idx = [i for i, x in enumerate(style) if x == k]
        oth = [i for i, x in enumerate(style) if x != k]
        per[k] = {'within': round(float(np.mean([s[i, j] for i in idx for j in idx if i < j])), 3), 'to_others': round(float(np.mean(s[np.ix_(idx, oth)])), 3)}
    res['p15']['per_style'] = per
    files16, st16, _ = load('p16_general')
    s16 = st16 @ st16.T
    iu = np.triu_indices(len(files16), 1)
    res['p16'] = {'n': len(files16), 'style_sim_mean': round(float(s16[iu].mean()), 3), 'style_sim_p05': round(float(np.percentile(s16[iu], 5)), 3),
                  'note': 'P16 は1つの絵柄（トーン）で人物・場所・狙いを変えた絵'}
    tone = [i for i, x in enumerate(style) if x == 'tone']
    # P16 の各絵が、P15 の4絵柄のどれにいちばん近いか（絵柄ごとの平均の向きとの近さ）
    cent = {k: st[[i for i, x in enumerate(style) if x == k]].mean(0) for k in sorted(set(style))}
    near = [max(cent, key=lambda k: float(v @ cent[k])) for v in st16]
    res['p16']['nearest_p15_style'] = {k: near.count(k) for k in cent}
    p25 = OUT / 'emb_p25_style_light.npz'
    if p25.exists():
        f25, s25, _ = load('p25_style_light')
        grp = {}
        for i, f in enumerate(f25):
            grp.setdefault(f.split('_')[0], []).append(i)
        sm = s25 @ s25.T
        res['p25'] = {}
        for g, idx in grp.items():
            res['p25'][g] = {'n': len(idx), 'within_mean': round(float(np.mean([sm[i, j] for i in idx for j in idx if i < j])), 3) if len(idx) > 1 else None,
                             'nearest_p15_style': {k: sum(1 for i in idx if max(cent, key=lambda c: float(s25[i] @ cent[c])) == k) for k in cent}}
        if 'style' in grp and 'real' in grp:
            res['p25']['style_to_real_mean'] = round(float(np.mean(sm[np.ix_(grp['style'], grp['real'])])), 3)
    (OUT / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
