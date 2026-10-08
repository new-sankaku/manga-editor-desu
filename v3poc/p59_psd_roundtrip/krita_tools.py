"""P59 Krita 5.2 の Python（kritarunner で画面なしに動かす）。run.py が呼ぶ。
  QT_QPA_PLATFORM=offscreen PYTHONPATH=<このフォルダ> kritarunner -s krita_tools -f dump <入力.psd> <出力.json> <合成.png> <保存.psd>
  QT_QPA_PLATFORM=offscreen PYTHONPATH=<このフォルダ> kritarunner -s krita_tools -f edit <入力.psd> <出力.json> <合成.png> <保存.psd> <計画.json>
dump は開くのにかかった時間・層の一覧を書き、手を加えずに PSD と合成の PNG に書き出す。
edit は人の直しを真似る（どの操作が通ったかを書く）。失敗した操作は理由を書いて次へ進む。
"""
import json
import time
import traceback


def _walk(node, depth, out):
    for c in node.childNodes():
        b = c.bounds()
        out.append({'depth': depth, 'name': c.name(), 'type': c.type(), 'visible': c.visible(), 'opacity': c.opacity(),
                    'blend': c.blendingMode(), 'bounds': [b.x(), b.y(), b.width(), b.height()],
                    'unique_id': c.uniqueId().toString()})
        if c.type() == 'grouplayer':
            _walk(c, depth + 1, out)
    return out


def _find(node, name):
    for c in node.childNodes():
        if c.name() == name:
            return c
        if c.type() == 'grouplayer':
            r = _find(c, name)
            if r is not None:
                return r
    return None


def _open(path):
    from krita import Krita
    k = Krita.instance()
    t0 = time.perf_counter()
    doc = k.openDocument(path)
    if doc is None:
        raise RuntimeError('Krita が開けませんでした: ' + path)
    doc.waitForDone()
    return k, doc, time.perf_counter() - t0


def _save(k, doc, out_png, out_psd):
    from krita import InfoObject
    doc.setBatchmode(True)
    doc.refreshProjection()
    doc.waitForDone()
    ok_psd = doc.exportImage(out_psd, InfoObject())
    ok_png = doc.exportImage(out_png, InfoObject())
    doc.waitForDone()
    return ok_psd, ok_png


def dump(*args):
    a = list(args[0]) if args and isinstance(args[0], (list, tuple)) else list(args)
    src, out_json, out_png, out_psd = a[:4]
    res = {}
    try:
        k, doc, sec = _open(src)
        res['open_sec'] = round(sec, 3)
        res['size'] = [doc.width(), doc.height()]
        res['layers'] = _walk(doc.rootNode(), 0, [])
        res['export_psd_ok'], res['export_png_ok'] = _save(k, doc, out_png, out_psd)
        doc.close()
    except Exception:
        res['error'] = traceback.format_exc()[-800:]
    open(out_json, 'w', encoding='utf-8').write(json.dumps(res, ensure_ascii=False))


def _paint_rect(node, x, y, w, h, bgra):
    """ページの座標の範囲を1色で塗る（Krita の画素は BGRA の順）。"""
    from PyQt5.QtCore import QByteArray
    node.setPixelData(QByteArray(bytes(bgra) * (w * h)), x, y, w, h)


def edit(*args):
    a = list(args[0]) if args and isinstance(args[0], (list, tuple)) else list(args)
    src, out_json, out_png, out_psd, plan_path = a[:5]
    plan = json.load(open(plan_path, encoding='utf-8'))
    res = {'ops': []}

    def op(label, fn):
        try:
            detail = fn()
            res['ops'].append({'op': label, 'result': 'ok', 'detail': detail})
        except Exception as e:
            res['ops'].append({'op': label, 'result': 'failed', 'error': repr(e)[:300]})

    try:
        k, doc, sec = _open(src)
        root = doc.rootNode()
        res['open_sec'] = round(sec, 3)
        x, y, w, h = plan['paint_rect']
        op('paint_line_art', lambda: _paint_rect(_find(root, plan['line_name']), x, y, w, h, (30, 30, 30, 255)))
        op('rename', lambda: _find(root, plan['rename_from']).setName(plan['rename_to']))

        def toggle():
            n = _find(root, plan['toggle_name'])
            n.setVisible(not n.visible())
            return n.visible()
        op('toggle_visible', toggle)

        def add():
            g = _find(root, plan['group_name'])
            n = doc.createNode('手の描き直し', 'paintlayer')
            g.addChildNode(n, None)
            ex, ey, ew, eh = plan['add_rect']
            _paint_rect(n, ex, ey, ew, eh, (0, 0, 0, 255))
            return n.type()
        op('add_layer_in_group', add)
        op('delete_layer', lambda: _find(root, plan['delete_name']).remove())

        def text_type():
            n = _find(root, plan['text_name'])
            # Krita の PSD の読み込みで文字の層が何になるか（vectorlayer なら文字として残っている）
            if n.type() != 'vectorlayer':
                raise RuntimeError('文字の層として読めていません。type=' + n.type())
            return n.type()
        op('set_text_of_imported_text_layer', text_type)

        def add_text():
            # Krita の文字（ベクターの層に SVG の文字）を写植のグループに足す。人が打ち直すのを真似る
            g = _find(root, plan['text_group_name'])
            v = doc.createVectorLayer('打ち直した台詞')
            g.addChildNode(v, None)
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="1754"><text x="200" y="240" '
                   'style="font-family:IPAGothic;font-size:36px;writing-mode:tb-rl;fill:#000000">打ち直した台詞</text></svg>')
            shapes = v.addShapesFromSvg(svg)
            return {'type': v.type(), 'shapes': len(shapes)}
        op('add_krita_text_layer', add_text)
        res['layers_after'] = _walk(root, 0, [])
        res['export_psd_ok'], res['export_png_ok'] = _save(k, doc, out_png, out_psd)
        doc.close()
    except Exception:
        res['error'] = traceback.format_exc()[-800:]
    open(out_json, 'w', encoding='utf-8').write(json.dumps(res, ensure_ascii=False))
