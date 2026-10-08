// P59 本番の書き出し（v3/psd_writer/write_layered_psd.js）と同じ形の依頼を受け、目印を足した PSD を書く。読み戻しもする。
// 本番との違い（どれもこの試作だけ）:
//   層に id（PSD の lyid）・timestamp（shmd の層の時刻。数値で項目の番号を入れる）を付けられる。
//   文書に xmp（XMP の文字列）を付けられる。
//   文字層の png_path を省ける（ag-psd は文字を描かないので、画素の無い文字層ができる。それを確かめるため）。
// 使い方:
//   node write.js write < 依頼.json         … output_path に PSD を書く。読み戻した層の一覧を標準出力に JSON で出す
//   node write.js read 入力.psd 出力.json    … ag-psd で読んだ層の一覧（id・時刻・文字・位置・画素の要約）を書く
// 失敗したら標準エラーに理由を書いて終了コード1（代わりの値で続けない）。
const fs = require('fs');
const crypto = require('crypto');
const { PNG } = require('pngjs');
const { writePsdBuffer, readPsd, initializeCanvas } = require('ag-psd');

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
  if (spec.id !== undefined) common.id = spec.id;
  if (spec.timestamp !== undefined) common.timestamp = spec.timestamp;
  if (spec.children) {
    if (spec.png_path) throw new Error(`グループに画像は付けられません: ${spec.name}`);
    return { ...common, opened: true, children: spec.children.map(toLayer) };
  }
  let layer = { ...common };
  if (spec.png_path) {
    const img = readPng(spec.png_path);
    layer = { ...layer, left: spec.left, top: spec.top, right: spec.left + img.width, bottom: spec.top + img.height, imageData: img };
  } else if (!spec.text) {
    throw new Error(`層に画像（png_path）がありません: ${spec.name}`);
  }
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

function pixelSummary(img) {
  if (!img) return null;
  let opaque = 0;
  for (let i = 3; i < img.data.length; i += 4) if (img.data[i] > 0) opaque++;
  return { w: img.width, h: img.height, opaque_px: opaque, sha1: crypto.createHash('sha1').update(Buffer.from(img.data.buffer)).digest('hex').slice(0, 12) };
}

function summarize(layers, depth, path, out) {
  for (const x of layers) {
    const p = path.concat([x.name]);
    out.push({
      path: p, name: x.name, depth, id: x.id ?? null, timestamp: x.timestamp ?? null, hidden: !!x.hidden, opacity: x.opacity,
      blend_mode: x.blendMode, group: !!x.children,
      text: x.text ? x.text.text : null, orientation: x.text ? (x.text.orientation || null) : null,
      font: x.text && x.text.style && x.text.style.font ? x.text.style.font.name : null,
      left: x.left ?? null, top: x.top ?? null, right: x.right ?? null, bottom: x.bottom ?? null,
      pixels: x.children ? null : pixelSummary(x.imageData),
    });
    if (x.children) summarize(x.children, depth + 1, p, out);
  }
  return out;
}

function readBack(buf) {
  const back = readPsd(buf, { useImageData: true });
  const xmp = back.imageResources && back.imageResources.xmpMetadata ? back.imageResources.xmpMetadata : null;
  return { width: back.width, height: back.height, xmp, layers: summarize(back.children || [], 0, [], []) };
}

function main() {
  const mode = process.argv[2];
  if (mode === 'write') {
    const req = JSON.parse(fs.readFileSync(0, 'utf8'));
    const psd = { width: req.width, height: req.height, children: req.layers.map(toLayer) };
    if (req.composite_png) {
      const c = readPng(req.composite_png);
      if (c.width !== req.width || c.height !== req.height) throw new Error('合成画像の大きさが width・height と違います');
      psd.imageData = c;
    }
    if (req.xmp) psd.imageResources = { xmpMetadata: req.xmp };
    const buf = writePsdBuffer(psd, { generateThumbnail: false, invalidateTextLayers: false });
    fs.writeFileSync(req.output_path, buf);
    process.stdout.write(JSON.stringify({ bytes: buf.length, ...readBack(buf) }));
  } else if (mode === 'read') {
    const t0 = Date.now();
    const buf = fs.readFileSync(process.argv[3]);
    const r = readBack(buf);
    fs.writeFileSync(process.argv[4], JSON.stringify({ read_ms: Date.now() - t0, ...r }));
  } else {
    throw new Error('使い方: node write.js write|read');
  }
}

try {
  main();
} catch (e) {
  process.stderr.write(String(e && e.stack ? e.stack : e) + '\n');
  process.exit(1);
}
