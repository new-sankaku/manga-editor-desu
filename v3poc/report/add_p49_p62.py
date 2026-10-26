"""報告のページに P49〜P62（サーバーに移す部品の試作・GPU の ComfyUI での確かめ・AIが出しにくい向き）の節を足す。
1回だけ流す（入れ済みなら何もしない）。文の全文は llm_doc/V3検証の結果.md と V3画像生成の機能と画面.md 7.1。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / 'index.html'
s = p.read_text(encoding='utf-8')


def fig(path, cap, sm=False):
    c = ' class="sm"' if sm else ''
    return f'<figure{c}><a href="../{path}"><img src="../{path}" alt="{cap}" loading="lazy"></a><figcaption>{cap}</figcaption></figure>'


def sec(id_, h2, rows, folder, cond, body, figs=()):
    c = f'<details class="cond"><summary>条件（何を渡して何で作ったか）</summary><div class="tw"><table>{cond}</table></div></details>' if cond else ''
    f = f'<div class="figs">{"".join(fig(*a) for a in figs)}</div>' if figs else ''
    return f'''<section id="{id_}">
  <h2>{h2}</h2>
  <p class="rows">一覧 {rows} ／ <code>v3poc/{folder}/</code></p>
  {c}
  {body}
  {f}
</section>
'''


def ul(*items):
    return '<ul>' + ''.join(f'<li{" class=" + chr(34) + k + chr(34) if k else ""}>{t}</li>' for k, t in items) + '</ul>'


G = None  # ふつうの行
ORDER = ['grid_2x3', 'offset_gutters', 'rows_1_2_1', 'rows_3_2_2', 'tall_left', 'tall_left_bottom', 'tall_mid_row', 'tall_right']
DIAG = ['diag_band', 'dynamic', 'slant_rows', 'slant_three', 'tall_slant_left', 'tall_slant_right', 'triangle_split', 'zigzag']
P62 = [('back_full', '真後ろの全身（12/12）'), ('back_34', '斜め後ろ（0/12。12枚とも真後ろ）'), ('look_back', '振り返り（12/12）'),
       ('profile_walk', '真横で歩く全身（12/12）'), ('profile_face', '真横の顔のアップ（12/12）'), ('lying_side', '横向きに寝転ぶ（12/12）'),
       ('crouch_back', '後ろ向きでしゃがむ（12/12。下から見た構図に寄る）'), ('two_profile', '2人が向かい合う（12/12。髪の言葉は1人にだけ効く）'),
       ('head_down', 'うつむき（顔が隠れたのは12/12。上体ごと深く倒す）')]

NEW = [
 sec('p49', '日本語の文字を manga-ocr で読めるか', '—', 'p49_manga_ocr',
     '<tr><th>材料</th><td>Pillow で描いた文字（正解が分かる）。漫画のページから切り抜いた文字では未検証</td></tr><tr><th>動かし方</th><td>manga-ocr 0.1.16・CPU 4コア</td></tr>',
     ul((G, '白地の台詞は横書き39/40・縦書き39/40が完全一致。ルビ付き24/24。'),
        ('bad', '網点の上の白字黒縁は7/24、描き文字に近いものは網点の上で36中0。'),
        ('bad', '文字の無い入力8つは8つとも何かの文を返した。文字の有無は別の検出器で決める。'),
        (G, 'ページを丸ごと渡すと関係のない文。フキダシごとに切り抜くと5/5。')),
     [('p49_manga_ocr/out/sheet.png', '読ませた切り抜きと結果'), ('p49_manga_ocr/out/page.png', 'フキダシ5つのページ')]),
 sec('p50', 'コマ割りの計算を制約ソルバー kiwisolver で解けるか', '—', 'p50_kiwi_layout', '',
     ul((G, '段と比・隙間・断ち切り・最小のコマ・見開きは線形制約で解けた。1ページ0.1ms前後。'),
        ('bad', '強い固定・中の比は勝てないと例外を出さずに静かに崩れる。呼ぶ側が指定どおりか調べる。'),
        (G, '斜めの区切りは角度を定数にすれば書ける。角度を変数にした制約・面積の指定は書けない。')),
     [('p50_kiwi_layout/out/sheet.png', '解いたコマ割り')]),
 sec('p51', '入稿用の画像と PDF を作れるか', '—', 'p51_export', '',
     ul((G, 'B5 の塗り足し込みで 600dpi は 4441×6213px。numpy で書いた網点は濃度の誤差±0.004以内。'),
        ('bad', '閾値128で2値にすると 600dpi で 0.03mm の線は消える。'),
        (G, 'img2pdf はページの大きさを mm で指定すると 188.000×263.000mm に合った。')),
     [('p51_export/out/crops.png', '細い線と網点の拡大')]),
 sec('p52', 'PSD を GIMP・Krita・ImageMagick で開けるか', '5-14', 'p52_psd_apps', '',
     ul((G, 'GIMP と Krita は名前・グループ・乗算・不透明度・隠すを読み、合成の差0。文字レイヤーはふつうのレイヤー。'),
        ('bad', 'ImageMagick は日本語の名前が「?」、グループを読まない。'),
        (G, 'Photoshop と CLIP STUDIO PAINT は未検証。')),
     [(f'p52_psd_apps/out/layers/{n}.png', n, True) for n in
      ('paper', 'color', 'tone', 'beta', 'line', 'text', 'expected_visible', 'expected_hidden')]),
 sec('p53', '画面の部品の候補（Fabric.js・perfect-freehand・網点）', '—', 'p53_canvas_libs', '',
     ul((G, 'Fabric.js の日本語入力は確定後の文字は正しい。縦書きは無いが、1文字ずつ置くと DOM の縦書きとほぼ同じ位置。'),
        ('bad', 'halftone-webgl は灰色に対する黒の割合が比例しない（灰色0.5で黒22%）。'),
        (G, 'canvas のタイルで作る網点は指定との差0.008以内（灰色0.9だけ0.858）。')),
     [('p53_canvas_libs/out/vertical.png', '1文字ずつ置いた縦書き'), ('p53_canvas_libs/out/pattern.png', 'タイルの網点'),
      ('p53_canvas_libs/out/halftone_webgl_circle45.png', 'halftone-webgl の網点')]),
 sec('p54', 'ログインと画像の置き場', '—', 'p54_login_storage', '',
     ul((G, 'Keycloak と Ory は確かめた14項目すべて通った。起動は 68.3秒と 11.0秒。'),
        (G, 'MinIO・SeaweedFS・RustFS は置く・取る・署名付きURL・バージョン・分割アップロードが通った。Garage は未検証。'),
        (G, '絵は無い（数字だけの試作）。'))),
 sec('p55', '呼び出しの記録・評価・注釈のツール', '—', 'p55_trace_eval', '',
     ul((G, 'Langfuse は見出し traceparent だけで複数の呼び出しを1つにまとめられた。'),
        (G, 'promptfoo は合格率の下限で回帰の試験が通る・落ちるを分けた。'),
        (G, 'Label Studio はコマの多角形・人物の枠・フキダシの枠を付けて JSON と COCO で書き出せた。')),
     [('p55_trace_eval/out/page1.png', 'Label Studio に取り込んだページ')]),
 sec('p56', 'ComfyUI への送信（CPU・SD1.5）', '—', 'p56_comfy_send', '',
     ul((G, 'seed を固定して再利用を消して2回送ると、ピクセルは同じでファイルの中身は違った。同じ絵かはピクセルで比べる。'),
        (G, '実行中の物は /queue の削除では止まらず /interrupt で止まった。'),
        (G, '絵の確かめではなく、送り方の確かめ（SD1.5 の小さな絵）。')),
     [('p56_comfy_send/out/seed11_a.png', 'seed 11（1回目）', True), ('p56_comfy_send/out/seed11_b.png', 'seed 11（2回目）', True),
      ('p56_comfy_send/out/seed12.png', 'seed 12', True)]),
 sec('p57', '作品をまたぐ順番（Temporal の公平さ）', '—', 'p57_fairness', '',
     ul((G, '公平さを入れると、後から5件依頼した作品Bが1・3・5・7・9番目に入った。切ると31〜35番目。'),
        (G, '絵は無い（順番の数字だけの試作）。'))),
 sec('p58', '意思決定モデル Clef-flash に読む順を当てさせる', '—', 'p58_decision_model', '',
     ul(('bad', '読む順は P11 0/8、P45 0/8（Claude はほぼ全問正解）。'),
        (G, '原稿の指示・話の矛盾は 0.5 で切るより確率の順位で使う方が合う見込み（AUC 1.0・0.85）。')),
     [(f'p58_decision_model/out/order_p11_{n}.png', n, True) for n in ORDER]
     + [(f'p58_decision_model/out/order_p45_{n}.png', n, True) for n in DIAG]),
 sec('p59', 'PSD の使い勝手と、手で直した PSD を戻せるか', '5-14・5-12', 'p59_psd_roundtrip', '',
     ul((G, '本番の書き出しの PSD は GIMP・Krita で名前・乗算・隠すが残り、合成の差0。'),
        ('bad', '文字レイヤーは両方でピクセルのレイヤーになり、文字として直せない。'),
        (G, '線画を塗った分は差 19,200 ピクセルで、塗った範囲と一致した。新しいバージョンにできた。')),
     [('p59_psd_roundtrip/out/sheet_open.png', '開いたときの見た目'), ('p59_psd_roundtrip/out/sheet_roundtrip.png', '直して戻した差'),
      ('p59_psd_roundtrip/out/sheet_text_no_pixels.png', 'ピクセルの無い文字レイヤー')]),
 sec('p60', 'ハーネスの作業の流れと、その画面', '—', 'p60_harness_loop', '',
     ul((G, '回数・費用・時間の上限で必ず止まった。ワーカーを落としても送った数の重複0。'),
        (G, '止める・取り消すの遅れはハートビートの間隔で決まり、約12秒。'),
        ('bad', 'b〜s の場面の絵はモックで、検査・評価の結果は絵の良し悪しとしては意味が無い。')),
     [(f'p60_harness_loop/out/{n}.png', c) for n, c in
      (('graph_running', '作業の流れのグラフ（走っている）'), ('node_detail', '段の中身'), ('review_wait', '判断待ち'),
       ('stage_paused', '工程を止めた'), ('stage_done', '工程が終わった'), ('approve_0', '採用 1回目'),
       ('approve_1', '採用 2回目'), ('approve_2', '採用 3回目'))]),
 sec('p61', 'GPU の ComfyUI で画像生成の処理とハーネスの作画を流す', '—', 'p61_gpu_server',
     '<tr><th>環境</th><td>ComfyUI 0.42.0・RTX 4070 Ti。SDXL（waiIllustriousSDXL v1.6・25手・cfg 6）、形の指定は xinsir の union promax、指示で直すは Qwen-Image 2.1</td></tr>'
     '<tr><th>試験</th><td><code>tests/integration/test_image_generation_gpu.py</code>・<code>test_harness_real.py</code>。LLM は偽物（鍵が無い）</td></tr>',
     ul((G, '囲んで直す・描き足す・絵から作り直す・指示で直すで、手動編集の範囲と囲んだ外が変わらなかった。'),
        (G, 'ハーネスの作画を1周・絵の中の文字で落ちた候補を囲んで直す・今すぐ止めて再開・本物の検出器と回す、の4件が通った。'),
        (G, '白黒の漫画の絵：seed 3 と 4 は別の絵、seed 3 に戻すと同じ絵（差0）。')),
     [('p61_gpu_server/sheet.png', '画像生成の処理（2026-10-25）'),
      ('p61_gpu_server/out/2026-10-26/sheet.png', '囲んで直す前と後（2組）・白黒の seed 3・4・3（2026-10-26）')]
     + [(f'p61_gpu_server/out/2026-10-25/{n}.png', c, True) for n, c in
        (('source', '元の絵'), ('inpaint_only_masked_True', '囲んだ所だけ直す'), ('inpaint_only_masked_False', '全体で直す'),
         ('outpaint', '描き足す'), ('image_to_image', '絵から作り直す'), ('instruction_edit_whole', '指示で直す（全体）'),
         ('instruction_edit_masked', '指示で直す（囲んだ範囲）'), ('control_lineart_input', '線画の指定'),
         ('control_lineart', '線画から作る'), ('control_pose_input', '骨格の指定'), ('control_pose', '骨格から作る'),
         ('harness_k0_picked', 'ハーネスの候補1（採った）'), ('harness_k1', 'ハーネスの候補2'))]),
 sec('p62', 'AIが出しにくい向き・姿勢を、ControlNet の骨格で再現できるか', '1-1・1-4', 'p62_hard_views',
     '<tr><th>絵のモデル</th><td>SDXL（waiIllustriousSDXL v1.6・25手・cfg 5・euler_ancestral）</td></tr>'
     '<tr><th>ControlNet</th><td>xinsir の union promax（openpose）。骨格の図は手で座標を置いた。効き2段（強さ0.8・終わり0.8／1.0・1.0）×seed 6つ。一覧の左端が骨格の図、上の段が0.8</td></tr>',
     ul((G, '骨格の図の顔の点の置き方で、向き（左右・後ろ）と振り返りが決まった。後ろ向きは鼻と目を描かず耳を2つ。'),
        ('bad', '斜め後ろだけは骨格の図で作れなかった（0/12）。'),
        (G, '出た絵を反転して輪郭（canny）で渡すと向きは決まるが、人物と構図も写る。')),
     [(f'p62_hard_views/out/sheet_{n}.png', c) for n, c in P62]
     + [('p62_hard_views/out/sheet_direction_profile_walk.png', '輪郭で向きを反転（歩く全身）'),
        ('p62_hard_views/out/sheet_direction_two_profile.png', '輪郭で向かい合わせる（2人）')]),
]

if '<section id="p49">' not in s:
    s = s.replace('<section id="src">', ''.join(NEW) + '<section id="src">', 1)
    s = s.replace('<a href="#src">出典</a>', '<a href="#p49">文字の読み取り</a><a href="#p50">コマ割りの計算</a><a href="#p51">入稿の画像</a>'
                  '<a href="#p52">PSD を開く</a><a href="#p53">画面の部品</a><a href="#p54">ログイン</a><a href="#p55">記録と注釈</a>'
                  '<a href="#p56">ComfyUI への送信</a><a href="#p57">作品の順番</a><a href="#p58">意思決定モデル</a><a href="#p59">PSD を戻す</a>'
                  '<a href="#p60">ハーネスの流れ</a><a href="#p61">GPU で流す</a><a href="#p62">向き・姿勢</a><a href="#src">出典</a>', 1)
    p.write_text(s, encoding='utf-8')
    print('入れた')
else:
    print('入れ済み')
