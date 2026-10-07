// P36 層に分けた絵を PSD に書き出し、読み戻して同じかを確かめる（一覧 5-14）。
// 書き出しと読み戻しは ag-psd（MIT）。別の読み手として psd-tools（MIT）でも読む（check.py）。
// 使い方: node write.js（先に python prep.py）
const fs = require('fs');
const path = require('path');
const { PNG } = require('pngjs');
const { writePsdBuffer, readPsd, initializeCanvas } = require('ag-psd');
// 画面の無い node では、読み戻しの画素の入れ物だけを渡す（絵を描く道具は使わない）
initializeCanvas(() => { throw new Error('canvas not used'); }, (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }));

const L = path.join(__dirname, 'out', 'layers');
const img = (f) => { const p = PNG.sync.read(fs.readFileSync(path.join(L, f))); return { width: p.width, height: p.height, data: new Uint8ClampedArray(p.data) }; };
const layer = (name, f, extra = {}) => { const d = img(f); return { name, top: 0, left: 0, bottom: d.height, right: d.width, imageData: d, ...extra }; };

const paper = img('paper.png');
const W = paper.width, H = paper.height;
const psd = {
  width: W, height: H, imageData: img('expected_rgba.png'),
  children: [
    layer('紙', 'paper.png'),
    { name: 'カラー', opened: true, hidden: true, children: [layer('着彩', 'color.png', { blendMode: 'multiply' })] },
    layer('トーン', 'tone.png', { opacity: 1 }),
    layer('ベタ', 'beta.png'),
    layer('線画', 'line.png'),
    { name: 'セリフ', top: 60, left: W - 160, bottom: 460, right: W - 60,
      text: { text: 'きょうは\n早いね', transform: [1, 0, 0, 1, W - 110, 80], orientation: 'vertical',
              style: { font: { name: 'SourceHanSansJP-Regular' }, fontSize: 40, fillColor: { r: 0, g: 0, b: 0 } } } },
  ],
};
const buf = writePsdBuffer(psd, { generateThumbnail: false, invalidateTextLayers: true });
fs.writeFileSync(path.join(__dirname, 'out', 'layers.psd'), buf);

// ag-psd で読み戻す
const back = readPsd(fs.readFileSync(path.join(__dirname, 'out', 'layers.psd')), { useImageData: true });
const flat = [];
const walk = (xs, depth) => xs.forEach((x) => { flat.push({ x, depth }); if (x.children) walk(x.children, depth + 1); });
walk(back.children, 0);
const src = { '紙': 'paper.png', '着彩': 'color.png', 'トーン': 'tone.png', 'ベタ': 'beta.png', '線画': 'line.png' };
const rows = flat.map(({ x, depth }) => {
  const r = { name: x.name, depth, hidden: !!x.hidden, blendMode: x.blendMode, group: !!x.children, text: x.text ? x.text.text : undefined,
              orientation: x.text ? x.text.orientation : undefined };
  if (src[x.name]) {
    const a = img(src[x.name]).data, b = x.imageData ? x.imageData.data : null;
    let diff = 0;
    if (!b || b.length !== a.length) diff = -1; else for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) diff++;
    r.pixel_diff = diff;
  }
  return r;
});
const res = { bytes: buf.length, width: back.width, height: back.height, layers: rows };
fs.writeFileSync(path.join(__dirname, 'out', 'agpsd_readback.json'), JSON.stringify(res, null, 1));
console.log(JSON.stringify(res));
