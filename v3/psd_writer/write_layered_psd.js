// 層の JSON（標準入力）と PNG から PSD を書く。p36・p52 の write.js を元にした。
// 入力: { width, height, composite_png|null, output_path, layers: [層...] }（層は下が先）
//   層: { name, png_path?, children?, hidden, blend_mode: normal|multiply, opacity 0..1, left, top,
//         text?: { text, orientation, font_name, font_size, color_rgb, x, y } }
//   children があればグループ。文字層は text と png_path（描いた画素）の両方が要る。
// 出力: output_path に PSD を書き、ag-psd で読み戻した層の一覧を標準出力に JSON で出す。
// 失敗したら標準エラーに理由を書いて終了コード1。
const fs = require('fs');
const { PNG } = require('pngjs');
const { writePsdBuffer, readPsd, initializeCanvas } = require('ag-psd');

// 画面の無い node では、読み戻しの画素の入れ物だけを渡す（絵を描く道具は使わない）
initializeCanvas(() => { throw new Error('canvas not used'); }, (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }));

const BLEND = { normal: 'normal', multiply: 'multiply' };

function readPng(p) {
  const png = PNG.sync.read(fs.readFileSync(p));
  return { width: png.width, height: png.height, data: new Uint8ClampedArray(png.data) };
}

function toLayer(spec) {
  if (typeof spec.name !== 'string' || spec.name === '') throw new Error('層の名前がありません');
  if (!(spec.blend_mode in BLEND)) throw new Error(`合成モードが不明です: ${spec.blend_mode}（${spec.name}）`);
  const common = { name: spec.name, hidden: !!spec.hidden, blendMode: BLEND[spec.blend_mode], opacity: spec.opacity };
  if (spec.children) {
    if (spec.png_path) throw new Error(`グループに画像は付けられません: ${spec.name}`);
    return { ...common, opened: true, children: spec.children.map(toLayer) };
  }
  if (!spec.png_path) throw new Error(`層に画像（png_path）がありません: ${spec.name}`);
  const img = readPng(spec.png_path);
  const layer = { ...common, left: spec.left, top: spec.top, right: spec.left + img.width, bottom: spec.top + img.height, imageData: img };
  if (spec.text) {
    const t = spec.text;
    layer.text = {
      text: t.text,
      transform: [1, 0, 0, 1, t.x, t.y],
      orientation: t.orientation,
      style: { font: { name: t.font_name }, fontSize: t.font_size, fillColor: { r: t.color_rgb[0], g: t.color_rgb[1], b: t.color_rgb[2] } },
    };
  }
  return layer;
}

function summarize(layers, depth, out) {
  for (const x of layers) {
    out.push({
      name: x.name, depth, hidden: !!x.hidden, opacity: x.opacity, blend_mode: x.blendMode,
      group: !!x.children, text: x.text ? x.text.text : null, orientation: x.text ? x.text.orientation : null,
    });
    if (x.children) summarize(x.children, depth + 1, out);
  }
  return out;
}

function main() {
  const req = JSON.parse(fs.readFileSync(0, 'utf8'));
  const psd = { width: req.width, height: req.height, children: req.layers.map(toLayer) };
  if (req.composite_png) {
    const c = readPng(req.composite_png);
    if (c.width !== req.width || c.height !== req.height) throw new Error('合成画像の大きさが width・height と違います');
    psd.imageData = c;
  }
  const buf = writePsdBuffer(psd, { generateThumbnail: false, invalidateTextLayers: false });
  fs.writeFileSync(req.output_path, buf);
  const back = readPsd(buf, { useImageData: true });
  process.stdout.write(JSON.stringify({ bytes: buf.length, width: back.width, height: back.height, layers: summarize(back.children, 0, []) }));
}

try {
  main();
} catch (e) {
  process.stderr.write(String(e && e.stack ? e.stack : e) + '\n');
  process.exit(1);
}
