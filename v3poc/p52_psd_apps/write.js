// P52 PSD を別のソフトで開くための PSD を ag-psd（MIT）で書く（P36 write.js と同じ構成。層の画素は run.py が out/layers に作る）。
// 使い方: node write.js（run.py が呼ぶ）。out/layers.psd（カラーのグループを隠す）と out/layers_visible.psd（見せる・トーンを不透明度60%）を書く。
const fs = require('fs');
const path = require('path');
const { PNG } = require('pngjs');
const { writePsdBuffer, readPsd, initializeCanvas } = require('ag-psd');
initializeCanvas(() => { throw new Error('canvas not used'); }, (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }));

const L = path.join(__dirname, 'out', 'layers');
const img = (f) => { const p = PNG.sync.read(fs.readFileSync(path.join(L, f))); return { width: p.width, height: p.height, data: new Uint8ClampedArray(p.data) }; };
const layer = (name, f, extra = {}) => { const d = img(f); return { name, top: 0, left: 0, bottom: d.height, right: d.width, imageData: d, ...extra }; };
const W = img('paper.png').width, H = img('paper.png').height;

function build(visible) {
  return {
    width: W, height: H, imageData: img(visible ? 'expected_visible.png' : 'expected_hidden.png'),
    children: [
      layer('紙', 'paper.png'),
      { name: 'カラー', opened: true, hidden: !visible, children: [layer('着彩', 'color.png', { blendMode: 'multiply' })] },
      layer('トーン', 'tone.png', { opacity: visible ? 0.6 : 1 }),
      layer('ベタ', 'beta.png'),
      layer('線画', 'line.png'),
      // 文字層：文字の情報と、描いた画素の両方を持つ
      { ...layer('セリフ', 'text.png'), text: { text: 'きょうは\n早いね', transform: [1, 0, 0, 1, W - 110, 80], orientation: 'vertical',
          style: { font: { name: 'SourceHanSansJP-Regular' }, fontSize: 40, fillColor: { r: 0, g: 0, b: 0 } } } },
    ],
  };
}
for (const [name, vis] of [['layers', false], ['layers_visible', true]]) {
  const buf = writePsdBuffer(build(vis), { generateThumbnail: false, invalidateTextLayers: false });
  fs.writeFileSync(path.join(__dirname, 'out', name + '.psd'), buf);
  const back = readPsd(buf, { useImageData: true });
  const rows = [];
  const walk = (xs, d) => xs.forEach((x) => { rows.push({ name: x.name, depth: d, hidden: !!x.hidden, opacity: x.opacity, blendMode: x.blendMode, group: !!x.children, text: x.text ? x.text.text : undefined }); if (x.children) walk(x.children, d + 1); });
  walk(back.children, 0);
  fs.writeFileSync(path.join(__dirname, 'out', name + '_agpsd.json'), JSON.stringify({ bytes: buf.length, layers: rows }, null, 1));
  console.log(name, buf.length, rows.length);
}
