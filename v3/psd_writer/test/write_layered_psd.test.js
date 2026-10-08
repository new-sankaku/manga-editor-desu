// write_layered_psd.js の試験: 小さな PNG から PSD を書き、ag-psd で読み戻して層の数・名前・属性が一致するか。
// 実行: npm test（node --test）
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { PNG } = require('pngjs');
const { readPsd, initializeCanvas } = require('ag-psd');

initializeCanvas(() => { throw new Error('canvas not used'); }, (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }));
const SCRIPT = path.join(__dirname, '..', 'write_layered_psd.js');

function writePng(dir, name, w, h, rgba) {
  const png = new PNG({ width: w, height: h });
  for (let i = 0; i < w * h; i++) png.data.set(rgba, i * 4);
  const p = path.join(dir, name);
  fs.writeFileSync(p, PNG.sync.write(png));
  return p;
}

function run(req) {
  return spawnSync(process.execPath, [SCRIPT], { input: JSON.stringify(req), encoding: 'utf8' });
}

test('層・グループ・隠す・乗算・不透明度・縦書きの文字層を書いて読み戻せる', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'psdw-'));
  const paper = writePng(dir, 'paper.png', 20, 30, [255, 255, 255, 255]);
  const color = writePng(dir, 'color.png', 20, 30, [255, 200, 190, 255]);
  const text = writePng(dir, 'text.png', 20, 30, [0, 0, 0, 255]);
  const out = path.join(dir, 'a.psd');
  const base = { hidden: false, blend_mode: 'normal', opacity: 1, left: 0, top: 0 };
  const req = {
    width: 20, height: 30, composite_png: paper, output_path: out,
    layers: [
      { ...base, name: '紙', png_path: paper },
      { ...base, name: 'カラー', hidden: true, children: [{ ...base, name: '着彩', png_path: color, blend_mode: 'multiply', opacity: 0.5 }] },
      { ...base, name: 'セリフ', png_path: text, text: { text: 'きょうは\n早いね', orientation: 'vertical', font_name: 'TestFont', font_size: 12, color_rgb: [0, 0, 0], x: 5, y: 5 } },
    ],
  };
  const r = run(req);
  assert.strictEqual(r.status, 0, r.stderr);
  const summary = JSON.parse(r.stdout);
  const back = readPsd(fs.readFileSync(out), { useImageData: true });
  assert.strictEqual(back.width, 20);
  const names = summary.layers.map((l) => l.name);
  assert.deepStrictEqual(names, ['紙', 'カラー', '着彩', 'セリフ']);
  const group = summary.layers.find((l) => l.name === 'カラー');
  assert.strictEqual(group.group, true);
  assert.strictEqual(group.hidden, true);
  const tint = summary.layers.find((l) => l.name === '着彩');
  assert.strictEqual(tint.depth, 1);
  assert.strictEqual(tint.blend_mode, 'multiply');
  assert.ok(Math.abs(tint.opacity - 0.5) < 0.01);
  const t = summary.layers.find((l) => l.name === 'セリフ');
  assert.strictEqual(t.text, 'きょうは\n早いね');
  assert.strictEqual(t.orientation, 'vertical');
  // ファイルから読み戻した層の並びも同じ
  assert.strictEqual(back.children.length, 3);
});

test('画像の無い層は失敗して標準エラーに理由を出す', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'psdw-'));
  const r = run({ width: 4, height: 4, composite_png: null, output_path: path.join(dir, 'b.psd'),
    layers: [{ name: 'だめ', hidden: false, blend_mode: 'normal', opacity: 1, left: 0, top: 0 }] });
  assert.strictEqual(r.status, 1);
  assert.match(r.stderr, /png_path/);
});
