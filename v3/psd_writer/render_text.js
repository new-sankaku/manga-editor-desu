// 文字を PNG に描く（@napi-rs/canvas）。書き出し（PNG・PDF・PSD）の文字は、どれもここで描く。
// 入力（標準入力の JSON）: { items: [文字...] }
//   文字: { id, text, font_path, font_size_px, vertical: bool, color: "#RRGGBB", box_w_px, box_h_px,
//           line_gap_ratio, decoration: {fill?, edge?, glow?, shadow?, ghosts[], band?, spacing_ratio},
//           ruby: [{start, end, text}], output_path }
//   飾りの比は文字の大きさとの比（name_structure/item_styles.py の TextDecoration）。
// 出力: 各文字の PNG を output_path に書き、{ items: [{ id, width, height, opaque_pixels }] } を標準出力に出す。
// 文字は箱の真ん中に置く。縦書きは右の行から左へ、1字ずつ立てて並べる（約物の向きの調整・縦中横はしない。未検証）。
// 箱からはみ出した文字は切らずに、絵を広げて描く（はみ出しは opaque の位置で呼ぶ側が見られる）。
const fs = require('fs');
const path = require('path');
const { createCanvas, GlobalFonts } = require('@napi-rs/canvas');

const registered = new Map();

function familyOf(fontPath) {
  if (!registered.has(fontPath)) {
    if (!fs.existsSync(fontPath)) throw new Error(`書体のファイルがありません: ${fontPath}`);
    const alias = `v3font_${registered.size}`;
    if (!GlobalFonts.registerFromPath(fontPath, alias)) throw new Error(`書体を読めません: ${fontPath}`);
    registered.set(fontPath, alias);
  }
  return registered.get(fontPath);
}

function hexToRgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

// 1字ごとの置き場（文字の大きさの単位）を決める
function layout(it) {
  const lines = it.text.split('\n');
  const size = it.font_size_px;
  const deco = it.decoration || {};
  const step = size * (1 + (deco.spacing_ratio || 0));
  const lineStep = size * (1 + it.line_gap_ratio);
  const glyphs = [];
  let maxLen = 0;
  let index = 0;
  lines.forEach((line, li) => {
    const chars = Array.from(line);
    maxLen = Math.max(maxLen, chars.length);
    chars.forEach((ch, ci) => {
      if (it.vertical) glyphs.push({ ch, index, x: -li * lineStep, y: ci * step });
      else glyphs.push({ ch, index, x: ci * step, y: li * lineStep });
      index += 1;
    });
    index += 1; // 改行の分（ルビの位置は改行を含めた文字の番号）
  });
  const blockW = it.vertical ? (lines.length - 1) * lineStep + size : Math.max(1, maxLen) * step;
  const blockH = it.vertical ? Math.max(1, maxLen) * step : (lines.length - 1) * lineStep + size;
  return { glyphs, blockW, blockH, size };
}

function render(it) {
  const family = familyOf(it.font_path);
  const deco = it.decoration || {};
  const { glyphs, blockW, blockH, size } = layout(it);
  const pad = Math.ceil(size * 2);
  const W = Math.max(it.box_w_px, Math.ceil(blockW + 2 * pad));
  const H = Math.max(it.box_h_px, Math.ceil(blockH + 2 * pad));
  const canvas = createCanvas(Math.ceil(W), Math.ceil(H));
  const ctx = canvas.getContext('2d');
  // 箱の真ん中に置く。縦書きの1行目は右端
  const ox = (W - blockW) / 2 + (it.vertical ? blockW - size : 0);
  const oy = (H - blockH) / 2;
  ctx.textBaseline = 'top';
  ctx.textAlign = 'left';

  if (deco.band) {
    ctx.fillStyle = hexToRgba(deco.band.color, deco.band.opacity);
    ctx.fillRect((W - blockW) / 2 - size * 0.2, oy - size * 0.2, blockW + size * 0.4, blockH + size * 0.4);
  }

  function drawPass(fontPx, glyphList, dx, dy, style) {
    ctx.font = `${fontPx}px ${family}`;
    for (const g of glyphList) {
      const x = ox + g.x + dx;
      const y = oy + g.y + dy;
      if (style.stroke) {
        ctx.lineJoin = 'round';
        ctx.lineWidth = style.stroke.width;
        ctx.strokeStyle = style.stroke.color;
        ctx.strokeText(g.ch, x, y);
      }
      if (style.fill) {
        ctx.fillStyle = style.fill;
        ctx.fillText(g.ch, x, y);
      }
    }
  }

  function withBlur(blurPx, fn) {
    ctx.save();
    if (blurPx > 0) ctx.filter = `blur(${blurPx}px)`;
    fn();
    ctx.restore();
  }

  for (const gh of deco.ghosts || []) {
    ctx.save();
    ctx.globalAlpha = gh.opacity;
    withBlur(gh.blur_ratio * size, () => drawPass(size, glyphs, gh.dx_ratio * size, gh.dy_ratio * size, {
      fill: gh.color, stroke: gh.ratio > 0 ? { width: 2 * gh.ratio * size, color: gh.color } : null,
    }));
    ctx.restore();
  }
  if (deco.shadow) {
    const s = deco.shadow;
    ctx.save();
    ctx.globalAlpha = s.opacity;
    withBlur(s.blur_ratio * size, () => drawPass(size, glyphs, s.ratio * size, s.ratio * size, {
      fill: s.color, stroke: deco.edge ? { width: 2 * deco.edge.ratio * size, color: s.color } : null,
    }));
    ctx.restore();
  }
  if (deco.glow) {
    const g = deco.glow;
    withBlur(g.blur_ratio * size, () => drawPass(size, glyphs, 0, 0, { stroke: { width: 2 * g.ratio * size, color: g.color } }));
  }
  if (deco.edge) drawPass(size, glyphs, 0, 0, { stroke: { width: 2 * deco.edge.ratio * size, color: deco.edge.color } });
  const fill = deco.fill || it.color;
  drawPass(size, glyphs, 0, 0, { fill });

  // ルビ：親の文字の横（縦書き）か上（横書き）に、半分の大きさで並べる
  const rubySize = size / 2;
  for (const r of it.ruby || []) {
    const base = glyphs.filter((g) => g.index >= r.start && g.index < r.end);
    if (base.length === 0) continue;
    const chars = Array.from(r.text);
    const first = base[0];
    const span = base.length * size;
    const step = Math.max(rubySize, span / chars.length);
    const start = (span - step * chars.length) / 2 + (step - rubySize) / 2;
    const rg = chars.map((ch, i) => (it.vertical
      ? { ch, x: first.x + size, y: first.y + start + i * step }
      : { ch, x: first.x + start + i * step, y: first.y - rubySize }));
    drawPass(rubySize, rg, 0, 0, { fill, stroke: deco.edge ? { width: 2 * deco.edge.ratio * rubySize, color: deco.edge.color } : null });
  }

  const buf = canvas.toBuffer('image/png');
  fs.mkdirSync(path.dirname(it.output_path), { recursive: true });
  fs.writeFileSync(it.output_path, buf);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  let opaque = 0;
  for (let i = 3; i < data.length; i += 4) if (data[i] > 0) opaque += 1;
  return { id: it.id, width: canvas.width, height: canvas.height, opaque_pixels: opaque };
}

function main() {
  const req = JSON.parse(fs.readFileSync(0, 'utf8'));
  const out = req.items.map(render);
  process.stdout.write(JSON.stringify({ items: out }));
}

try {
  main();
} catch (e) {
  process.stderr.write(String(e && e.stack ? e.stack : e) + '\n');
  process.exit(1);
}
