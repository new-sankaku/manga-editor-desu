// 文字を PNG に描く（@napi-rs/canvas）。書き出し（PNG・PDF・PSD）の文字は、どれもここで描く。
// 組版（字の形・向き・禁則・縦中横・自動の改行・行間）は text_layout.js。ここは字の輪郭を塗るだけ。
// 入力（標準入力の JSON）: { items: [文字...] }
//   文字: { id, text, font_path, font_size_px, vertical: bool, color: "#RRGGBB", box_w_px, box_h_px,
//           language?: "ja" など（書体の言語ごとの字形を選ぶ。作品の設定の言語）,
//           typesetting: { line_spacing_ratio, line_break: "none"|"character"|"phrase",
//                          tate_chu_yoko_max_digits, tate_chu_yoko_marks, align: "start"|"center",
//                          hanging_punctuation?: bool（行末の句読点をぶら下げる） },
//           spans: [{ start, end, font_path?, size_ratio?, embolden_ratio?, color? }]（文字の一部の書式）,
//           decoration: {fill?, edge?, glow?, shadow?, ghosts[], band?, spacing_ratio},
//           ruby: [{start, end, text}], output_path?, measure_only?: bool, layout_detail?: bool }
//   飾りの比は文字の大きさとの比（name_structure/item_styles.py の TextDecoration）。
//   文字の番号（ruby・spans の start・end）はコードポイントの番号で、改行も1字に数える。
// 出力: 各文字の PNG を output_path に書き（measure_only のときは書かない）、
//   { items: [{ id, width, height, opaque_pixels, overflow, lines, block_w, block_h, missing_chars, layout? }] } を標準出力に出す。
//   layout は layout_detail のときだけ（行の切れ目と字の置き場。layoutDetail を見る）。
// 文字のブロックは箱の真ん中に置く。縦書きは右の列から左へ。
// 箱に入らない文字は切らずに、絵を広げて描き、overflow を true にする（呼ぶ側が止めるか印を出す）。
const fs = require('fs');
const path = require('path');
const { createCanvas, Path2D } = require('@napi-rs/canvas');
const { layoutText, placeRuby } = require('./text_layout');

const pathCache = new Map();
function glyphPath(f, gid) {
  const key = `${f.path}#${gid}`;
  if (!pathCache.has(key)) pathCache.set(key, new Path2D(f.font.glyphToPath(gid)));
  return pathCache.get(key);
}

function hexToRgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

function readFile(p) {
  if (!fs.existsSync(p)) throw new Error(`書体のファイルがありません: ${p}`);
  return fs.readFileSync(p);
}

// 置いた升の字を、画素の行列（ブロックの左上が原点）にして並べる
function glyphDraws(placed) {
  const out = [];
  for (const p of placed) {
    for (const g of p.cell.glyphs) {
      const [a, b, c, d, e, f] = g.m;
      out.push({ f: g.f, gid: g.gid, m: [a, b, c, d, e + p.ox, f + p.oy], size: p.cell.size, style: p.cell.style });
    }
  }
  return out;
}

// 組んだ結果を、画面が字を置ける形にする（layout_detail のとき）。座標は文字のブロックの左上が原点の画素。
// block_origin は箱の左上からブロックの左上まで（ブロックは箱の真ん中）。縦書きの字の x は列の真ん中・y は字の上端、
// 横書きの字の x は字の左端・y は基準線。hanging はぶら下げた句読点（箱の外に出る）
function layoutDetail(it, lay, rubyPlaced) {
  const chars = Array.from(it.text);
  const cell = (p) => ({ start: p.cell.start, end: p.cell.end, text: chars.slice(p.cell.start, p.cell.end).join(''),
    kind: p.cell.kind, line: p.line, x: p.ox, y: p.oy, advance: p.cell.adv, size: p.cell.size });
  return {
    block_origin: [(it.box_w_px - lay.blockW) / 2, (it.box_h_px - lay.blockH) / 2],
    lines: lay.lines.map((l, i) => {
      const cs = lay.placed.filter((p) => p.line === i);
      return { center: l.center, thick: l.thick, start: cs.length ? cs[0].cell.start : null,
        end: cs.length ? cs[cs.length - 1].cell.end : null };
    }),
    glyphs: lay.placed.map((p) => ({ ...cell(p), hanging: p.hanging })),
    ruby: rubyPlaced.map((p) => ({ ruby: p.ruby, text: p.cell.text, x: p.ox, y: p.oy, advance: p.cell.adv,
      size: p.cell.size })),
  };
}

async function render(it) {
  if (!it.typesetting) throw new Error(`文字 ${it.id} の組版の設定（typesetting）がありません`);
  const lay = await layoutText(it, readFile);
  const size = it.font_size_px;
  const deco = it.decoration || {};
  const pad = Math.ceil(size * 2);
  const W = Math.ceil(Math.max(it.box_w_px, lay.blockW + 2 * pad));
  const H = Math.ceil(Math.max(it.box_h_px, lay.blockH + 2 * pad));
  const ox = (W - lay.blockW) / 2;
  const oy = (H - lay.blockH) / 2;
  const ruby = await placeRuby(it, lay, readFile);
  const rubyPlaced = ruby.placed;
  const info = { id: it.id, width: W, height: H, overflow: lay.overflow, lines: lay.lines.length,
    block_w: lay.blockW, block_h: lay.blockH, missing_chars: [...new Set([...lay.missing, ...ruby.missing])] };
  if (it.layout_detail) info.layout = layoutDetail(it, lay, rubyPlaced);
  if (it.measure_only) return { ...info, opaque_pixels: null };

  const canvas = createCanvas(W, H);
  const ctx = canvas.getContext('2d');
  const draws = glyphDraws(lay.placed);

  const rubyDraws = glyphDraws(rubyPlaced);

  if (deco.band) {
    ctx.fillStyle = hexToRgba(deco.band.color, deco.band.opacity);
    ctx.fillRect(ox - size * 0.2, oy - size * 0.2, lay.blockW + size * 0.4, lay.blockH + size * 0.4);
  }

  // style: { fill?, stroke?: {ratio, color} }。線の太さは各字の大きさとの比
  function drawPass(list, dx, dy, style) {
    for (const g of list) {
      const [a, b, c, d, e, f] = g.m;
      const scale = Math.sqrt(Math.abs(a * d - b * c));
      const p = glyphPath(g.f, g.gid);
      ctx.save();
      ctx.setTransform(a, b, c, d, e + ox + dx, f + oy + dy);
      const fill = style.useSpanColor && g.style.color ? g.style.color : style.fill;
      if (style.stroke) {
        ctx.lineJoin = 'round';
        ctx.lineWidth = (style.stroke.ratio * g.size) / scale;
        ctx.strokeStyle = style.stroke.color;
        ctx.stroke(p);
      }
      if (fill) {
        ctx.fillStyle = fill;
        ctx.fill(p);
        if (style.useSpanColor && g.style.embolden_ratio > 0) {
          // 太字：字の色で輪郭をなぞって太らせる（書式の embolden_ratio は字の大きさとの比）
          ctx.lineJoin = 'round';
          ctx.lineWidth = (g.style.embolden_ratio * g.size) / scale;
          ctx.strokeStyle = fill;
          ctx.stroke(p);
        }
      }
      ctx.restore();
    }
  }

  function withBlur(blurPx, fn) {
    ctx.save();
    if (blurPx > 0) ctx.filter = `blur(${blurPx}px)`;
    fn();
    ctx.restore();
  }

  const all = draws.concat(rubyDraws);
  for (const gh of deco.ghosts || []) {
    ctx.save();
    ctx.globalAlpha = gh.opacity;
    withBlur(gh.blur_ratio * size, () => drawPass(all, gh.dx_ratio * size, gh.dy_ratio * size, {
      fill: gh.color, stroke: gh.ratio > 0 ? { ratio: 2 * gh.ratio, color: gh.color } : null,
    }));
    ctx.restore();
  }
  if (deco.shadow) {
    const s = deco.shadow;
    ctx.save();
    ctx.globalAlpha = s.opacity;
    withBlur(s.blur_ratio * size, () => drawPass(all, s.ratio * size, s.ratio * size, {
      fill: s.color, stroke: deco.edge ? { ratio: 2 * deco.edge.ratio, color: s.color } : null,
    }));
    ctx.restore();
  }
  if (deco.glow) {
    const g = deco.glow;
    withBlur(g.blur_ratio * size, () => drawPass(all, 0, 0, { stroke: { ratio: 2 * g.ratio, color: g.color } }));
  }
  if (deco.edge) drawPass(all, 0, 0, { stroke: { ratio: 2 * deco.edge.ratio, color: deco.edge.color } });
  drawPass(all, 0, 0, { fill: deco.fill || it.color, useSpanColor: true });

  const buf = canvas.toBuffer('image/png');
  fs.mkdirSync(path.dirname(it.output_path), { recursive: true });
  fs.writeFileSync(it.output_path, buf);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  let opaque = 0;
  for (let i = 3; i < data.length; i += 4) if (data[i] > 0) opaque += 1;
  return { ...info, opaque_pixels: opaque };
}

async function main() {
  const req = JSON.parse(fs.readFileSync(0, 'utf8'));
  const out = [];
  for (const it of req.items) out.push(await render(it));
  process.stdout.write(JSON.stringify({ items: out }));
}

main().catch((e) => {
  process.stderr.write(String(e && e.stack ? e.stack : e) + '\n');
  process.exit(1);
});
