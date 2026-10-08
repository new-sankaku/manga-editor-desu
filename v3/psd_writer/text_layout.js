// 文字の組版（縦書き・横書き）。字の形と置き場を決めるだけで、描くのは render_text.js。
//
// 使う既製品（自前で書かない所）:
// - 字の形: harfbuzzjs（HarfBuzz）。縦書きは向きを TTB にして形を作ると、書体の vert/vrt2 の字形
//   （「」、。ー… 小書きの位置）と縦の送りが書体どおりに出る
// - 字の向き: Unicode の UAX #50（vertical_orientation.json。build_vertical_orientation.js で作る）
//   U・Tu は立てる。R は横に寝かせて90度回す。Tr は書体に縦の字形があればそれを、無ければ90度回す（UAX #50 の決まり）
// - 禁則（行頭・行末に置けない字）: linebreak（UAX #14）。改行してよい所だけで折り返すので、
//   「、。」」ー 小書きの字が行頭に来ない・「が行末に来ない
// - 文節で折り返す: budoux（日本語の文節の切れ目）。文節が1行に入らないときだけ、その中を UAX #14 の切れ目で折る
// - 字の集まり（濁点の合成など）: Intl.Segmenter（書記素）
//
// 縦中横は自前（決めごと 2.3）。半角の数字が tate_chu_yoko_max_digits 字以下で続く所と、
// tate_chu_yoko_marks のとき「!?」など2字の感嘆符・疑問符を、1字分の升に横に並べて立てる。
// 1字分より広ければ横だけ縮める。
//
// 座標: 1行（縦書きは1列）ごとに、縦書きは列の中心 x=0・列の上 y=0、横書きは行の左 x=0・基準線 y=0 で
// 字ごとの行列（書体の単位 → 画素。y は下向き）を作る。
const LineBreaker = require('linebreak');
const { loadDefaultJapaneseParser } = require('budoux');
const VO = require('./vertical_orientation.json');

let hb = null;
async function loadHarfbuzz() {
  if (!hb) hb = await import('harfbuzzjs');
  return hb;
}

const fonts = new Map();

function fontOf(fontPath, readFile) {
  if (!fonts.has(fontPath)) {
    const face = new hb.Face(new hb.Blob(readFile(fontPath)), 0);
    const font = new hb.Font(face);
    const ext = font.hExtents();
    fonts.set(fontPath, { path: fontPath, face, font, upem: face.upem, asc: ext.ascender, desc: ext.descender });
  }
  return fonts.get(fontPath);
}

function orientation(cp) {
  const r = VO.ranges;
  let lo = 0;
  let hi = r.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (cp < r[mid][0]) hi = mid - 1;
    else if (cp > r[mid][1]) lo = mid + 1;
    else return r[mid][2];
  }
  return VO.default;
}

function shape(f, str, direction, language) {
  const buf = new hb.Buffer();
  buf.addText(str);
  buf.setDirection(direction);
  buf.guessSegmentProperties();
  if (language) buf.setLanguage(language);
  hb.shape(f.font, buf);
  return buf.getGlyphInfosAndPositions();
}

const DIGIT = /^[0-9]$/;
const MARK = /^[!?！？]$/;

// 文字の番号（コードポイントの番号。ルビ・書式の範囲と同じ数え方）ごとの書式
function styleAt(it, i) {
  const base = { font_path: it.font_path, size: it.font_size_px, embolden_ratio: 0, color: null };
  for (const s of it.spans || []) {
    if (i >= s.start && i < s.end) {
      if (s.font_path) base.font_path = s.font_path;
      if (s.size_ratio) base.size = it.font_size_px * s.size_ratio;
      if (s.embolden_ratio) base.embolden_ratio = s.embolden_ratio;
      if (s.color) base.color = s.color;
    }
  }
  return base;
}

// 1つの升（字・縦中横のまとまり）の字形と大きさ
function makeCell(it, text, start, end, kind, readFile, missing) {
  const st = styleAt(it, start);
  const f = fontOf(st.font_path, readFile);
  const s = st.size / f.upem;
  const mid = (f.asc + f.desc) / 2;
  const glyphs = [];
  let adv = 0;
  const check = (r) => {
    for (const g of r) if (g.codepoint === 0) missing.add(text);
  };
  if (kind === 'upright') {
    const r = shape(f, text, hb.Direction.TTB, it.language);
    check(r);
    // Tr の字は、縦の字形に替わらなければ90度回す（UAX #50）
    const cps = Array.from(text);
    const tr = orientation(cps[0].codePointAt(0)) === 'Tr';
    const nominal = cps.length === 1 ? f.font.nominalGlyph(cps[0].codePointAt(0)) : undefined;
    if (tr && r.length === 1 && r[0].codepoint === nominal) return makeCell(it, text, start, end, 'rotated', readFile, missing);
    let py = 0;
    for (const g of r) {
      glyphs.push({ f, gid: g.codepoint, m: [s, 0, 0, -s, s * g.xOffset, -s * (py + g.yOffset)] });
      py += g.yAdvance;
    }
    adv = -py * s;
  } else if (kind === 'rotated') {
    const r = shape(f, text, hb.Direction.LTR, it.language);
    check(r);
    let px = 0;
    for (const g of r) {
      glyphs.push({ f, gid: g.codepoint, m: [0, s, s, 0, s * (g.yOffset - mid), s * (px + g.xOffset)] });
      px += g.xAdvance;
    }
    adv = px * s;
  } else if (kind === 'tcy') {
    const r = shape(f, text, hb.Direction.LTR, it.language);
    check(r);
    const w = r.reduce((a, g) => a + g.xAdvance, 0);
    const fx = s * Math.min(1, f.upem / w);
    const x0 = -(w * fx) / 2;
    const baseline = (f.upem * s) / 2 + s * mid;
    let px = 0;
    for (const g of r) {
      glyphs.push({ f, gid: g.codepoint, m: [fx, 0, 0, -s, x0 + fx * (px + g.xOffset), baseline - s * g.yOffset] });
      px += g.xAdvance;
    }
    adv = f.upem * s;
  } else {
    // 横書き：基準線 y=0
    const r = shape(f, text, hb.Direction.LTR, it.language);
    check(r);
    let px = 0;
    for (const g of r) {
      glyphs.push({ f, gid: g.codepoint, m: [s, 0, 0, -s, s * (px + g.xOffset), -s * g.yOffset] });
      px += g.xAdvance;
    }
    adv = px * s;
  }
  const ascent = (st.size * f.asc) / (f.asc - f.desc);
  return { start, end, kind, text, style: st, size: st.size, adv, ascent, glyphs };
}

// 1段落（改行の無い文字の並び）を升に分ける。base は段落の先頭の文字の番号
function cellsOf(it, para, base, readFile, missing) {
  const seg = new Intl.Segmenter(it.language || undefined, { granularity: 'grapheme' });
  const gs = [];
  let cp = base;
  for (const g of seg.segment(para)) {
    const n = Array.from(g.segment).length;
    gs.push({ text: g.segment, start: cp, end: cp + n, u16: g.index });
    cp += n;
  }
  const ts = it.typesetting;
  const cells = [];
  let i = 0;
  while (i < gs.length) {
    if (it.vertical) {
      // 縦中横の数字・感嘆符
      let j = i;
      while (j < gs.length && DIGIT.test(gs[j].text)) j += 1;
      if (j > i && j - i <= ts.tate_chu_yoko_max_digits) {
        cells.push({ ...makeCell(it, gs.slice(i, j).map((g) => g.text).join(''), gs[i].start, gs[j - 1].end, 'tcy', readFile, missing), u16: gs[i].u16 });
        i = j;
        continue;
      }
      if (j > i) {
        // 長い数字は横に寝かせる（UAX #50 で数字は R）
        for (let k = i; k < j; k += 1) cells.push({ ...makeCell(it, gs[k].text, gs[k].start, gs[k].end, 'rotated', readFile, missing), u16: gs[k].u16 });
        i = j;
        continue;
      }
      j = i;
      while (j < gs.length && MARK.test(gs[j].text)) j += 1;
      if (ts.tate_chu_yoko_marks && j - i === 2) {
        cells.push({ ...makeCell(it, gs[i].text + gs[i + 1].text, gs[i].start, gs[i + 1].end, 'tcy', readFile, missing), u16: gs[i].u16 });
        i = j;
        continue;
      }
      const o = orientation(gs[i].text.codePointAt(0));
      const kind = o === 'R' ? 'rotated' : 'upright';
      cells.push({ ...makeCell(it, gs[i].text, gs[i].start, gs[i].end, kind, readFile, missing), u16: gs[i].u16 });
    } else {
      cells.push({ ...makeCell(it, gs[i].text, gs[i].start, gs[i].end, 'horizontal', readFile, missing), u16: gs[i].u16 });
    }
    i += 1;
  }
  return cells;
}

// 改行してよい所（升の番号。その升の前で改行できる）
function breakPoints(para, cells, mode) {
  const startAt = new Map(cells.map((c, k) => [c.u16, k]));
  const uax = new Set();
  const lb = new LineBreaker(para);
  let b;
  while ((b = lb.nextBreak())) {
    if (startAt.has(b.position) && startAt.get(b.position) > 0) uax.add(startAt.get(b.position));
  }
  if (mode !== 'phrase') return { preferred: uax, inner: uax };
  const phrase = new Set();
  let u = 0;
  for (const p of loadDefaultJapaneseParser().parse(para)) {
    u += p.length;
    if (uax.has(startAt.get(u))) phrase.add(startAt.get(u));
  }
  return { preferred: phrase, inner: uax };
}

function lineLength(cells, spacing) {
  if (cells.length === 0) return 0;
  return cells.reduce((a, c) => a + c.adv, 0) + spacing * (cells.length - 1);
}

// 升を行に分ける（貪欲に詰める）。改行してよい所でだけ切る
function breakLines(cells, points, limit, spacing, mode) {
  if (mode === 'none') return [cells];
  const split = (list, set, offset) => {
    const segs = [];
    let cur = [];
    list.forEach((c, k) => {
      if (k > 0 && set.has(offset + k)) {
        segs.push(cur);
        cur = [];
      }
      cur.push(c);
    });
    if (cur.length) segs.push(cur);
    return segs;
  };
  const lines = [];
  let cur = [];
  const place = (seg) => {
    const joined = cur.length ? lineLength(cur.concat(seg), spacing) : lineLength(seg, spacing);
    if (cur.length && joined > limit) {
      lines.push(cur);
      cur = [];
    }
    cur = cur.concat(seg);
  };
  let offset = 0;
  for (const seg of split(cells, points.preferred, 0)) {
    if (lineLength(seg, spacing) > limit && points.inner !== points.preferred) {
      // 文節が1行に入らない：その中を禁則の切れ目で折る
      for (const sub of split(seg, points.inner, offset)) place(sub);
    } else {
      place(seg);
    }
    offset += seg.length;
  }
  if (cur.length || lines.length === 0) lines.push(cur);
  return lines;
}

// 文字1つを組む。返すのは字ごとの置き場（ブロックの左上が原点）・ブロックの大きさ・はみ出し
async function layoutText(it, readFile) {
  await loadHarfbuzz();
  const ts = it.typesetting;
  const base = it.font_size_px;
  const deco = it.decoration || {};
  const spacing = base * (deco.spacing_ratio || 0);
  const gap = base * ts.line_spacing_ratio;
  const limit = it.vertical ? it.box_h_px : it.box_w_px;
  const missing = new Set();
  const lines = [];
  const chars = Array.from(it.text);
  let start = 0;
  const paras = [];
  for (let k = 0; k <= chars.length; k += 1) {
    if (k === chars.length || chars[k] === '\n') {
      paras.push({ text: chars.slice(start, k).join(''), base: start });
      start = k + 1;
    }
  }
  for (const p of paras) {
    const cells = cellsOf(it, p.text, p.base, readFile, missing);
    const pts = ts.line_break === 'none' ? null : breakPoints(p.text, cells, ts.line_break);
    for (const cs of breakLines(cells, pts, limit, spacing, ts.line_break)) lines.push(cs);
  }
  // 行の太さ（縦書きは列の幅）は、その行で一番大きい字。ルビのある行は、ルビの幅（親の字の半分）を足して取る
  const thick = lines.map((cs) => (cs.length ? Math.max(...cs.map((c) => c.size)) : base));
  const rubyExtra = lines.map((cs) => Math.max(0, ...(it.ruby || []).flatMap((r) => cs
    .filter((c) => c.start >= r.start && c.end <= r.end).map((c) => c.size / 2))));
  const lens = lines.map((cs) => lineLength(cs, spacing));
  const cross = thick.reduce((a, t, li) => a + t + rubyExtra[li], 0) + gap * (lines.length - 1);
  const along = Math.max(0, ...lens);
  const blockW = it.vertical ? cross : along;
  const blockH = it.vertical ? along : cross;
  const placed = [];
  const lineBoxes = [];
  let c0 = 0;
  lines.forEach((cs, li) => {
    const t = thick[li];
    const shift = ts.align === 'center' ? (along - lens[li]) / 2 : 0;
    let pos = shift;
    // 横書きの行の基準線：その行で一番高い字に合わせる
    const baseline = cs.length ? Math.max(...cs.map((c) => c.ascent)) : 0;
    const lineX = it.vertical ? blockW - c0 - rubyExtra[li] - t / 2 : 0;
    const lineY = it.vertical ? 0 : c0 + rubyExtra[li];
    lineBoxes.push({ center: it.vertical ? lineX : lineY + t / 2, thick: t });
    for (const c of cs) {
      const ox = it.vertical ? lineX : pos;
      const oy = it.vertical ? pos : lineY + baseline;
      placed.push({ cell: c, ox, oy, line: li });
      pos += c.adv + spacing;
    }
    c0 += t + rubyExtra[li] + gap;
  });
  const overflow = lens.some((l) => l > limit + 0.5) || cross > (it.vertical ? it.box_w_px : it.box_h_px) + 0.5;
  return { placed, lines: lineBoxes, blockW, blockH, overflow, missing: [...missing] };
}

module.exports = { layoutText, loadHarfbuzz, fontOf, orientation, makeCell, shape };
