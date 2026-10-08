// text_layout.js の試験: 禁則・縦中横・字の向き・自動の改行（字・文節）・行間・文字の一部の書式。
// 書体は IPA ゴシック（無ければ飛ばす）。実行: npm test
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const { loadDefaultJapaneseParser } = require('budoux');
const { layoutText } = require('../text_layout.js');

const FONT = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf';
const skip = !fs.existsSync(FONT) && '試験の書体が無い';
const SIZE = 20;
const TS = { line_spacing_ratio: 0.5, line_break: 'character', tate_chu_yoko_max_digits: 2, tate_chu_yoko_marks: true, align: 'start' };

function item(text, over = {}) {
  return {
    id: 't', text, font_path: FONT, font_size_px: SIZE, vertical: true, color: '#000000', language: 'ja',
    box_w_px: 400, box_h_px: 400, typesetting: TS, spans: [], decoration: { fill: '#000000' }, ruby: [], ...over,
  };
}

function lineTexts(r, text) {
  const chars = Array.from(text);
  const out = [];
  for (const p of r.placed) {
    out[p.line] = (out[p.line] || '') + chars.slice(p.cell.start, p.cell.end).join('');
  }
  return out;
}

test('禁則：句点を行頭に置かない', { skip }, async () => {
  const text = 'あいうえ。';
  // 4字ちょうどの列：そのまま折ると「。」が2列目の頭に来る
  const r = await layoutText(item(text, { box_h_px: SIZE * 4 }), fs.readFileSync);
  const lines = lineTexts(r, text);
  assert.ok(lines.length === 2, JSON.stringify(lines));
  assert.ok(!lines[1].startsWith('。'), JSON.stringify(lines));
  assert.strictEqual(lines.join(''), text);
});

test('禁則：始めのかぎ括弧を行末に置かない', { skip }, async () => {
  const text = 'あいう「え」';
  const r = await layoutText(item(text, { box_h_px: SIZE * 4 }), fs.readFileSync);
  const lines = lineTexts(r, text);
  assert.ok(!lines[0].endsWith('「'), JSON.stringify(lines));
});

test('縦中横：桁数の上限まで・感嘆符と疑問符', { skip }, async () => {
  const kinds = async (text, ts) => {
    const r = await layoutText(item(text, { typesetting: { ...TS, ...ts } }), fs.readFileSync);
    return r.placed.map((p) => [Array.from(text).slice(p.cell.start, p.cell.end).join(''), p.cell.kind]);
  };
  assert.deepStrictEqual((await kinds('第12話', {})).find(([s]) => s === '12'), ['12', 'tcy']);
  // 上限を超える桁は縦中横にしない（1字ずつ回す）
  assert.ok((await kinds('第123話', {})).every(([, k]) => k !== 'tcy'));
  assert.ok((await kinds('第12話', { tate_chu_yoko_max_digits: 0 })).every(([, k]) => k !== 'tcy'));
  assert.deepStrictEqual((await kinds('え!?', {})).find(([s]) => s === '!?'), ['!?', 'tcy']);
  assert.ok((await kinds('え!?', { tate_chu_yoko_marks: false })).every(([, k]) => k !== 'tcy'));
});

test('字の向き：かなは立て、ラテン文字は回し、括弧は縦の字形', { skip }, async () => {
  const text = 'あA「ー';
  const r = await layoutText(item(text, { typesetting: { ...TS, tate_chu_yoko_max_digits: 0 } }), fs.readFileSync);
  const k = Object.fromEntries(r.placed.map((p) => [Array.from(text)[p.cell.start], p.cell.kind]));
  assert.strictEqual(k['あ'], 'upright');
  assert.strictEqual(k.A, 'rotated');
  assert.strictEqual(k['「'], 'upright');
  assert.strictEqual(k['ー'], 'upright');
});

test('自動の改行：none は折らずにはみ出しを返す', { skip }, async () => {
  const r = await layoutText(item('あいうえおかきくけこ', { box_h_px: SIZE * 4, typesetting: { ...TS, line_break: 'none' } }),
    fs.readFileSync);
  assert.strictEqual(r.lines.length, 1);
  assert.strictEqual(r.overflow, true);
});

test('自動の改行：文節で折る', { skip }, async () => {
  const text = '今日は天気が良いので公園に行きます';
  const r = await layoutText(item(text, { box_h_px: SIZE * 7, typesetting: { ...TS, line_break: 'phrase' } }), fs.readFileSync);
  const lines = lineTexts(r, text);
  // 行の切れ目が、budoux の文節の切れ目のどれかになっている（文節の途中で切らない）
  const ends = new Set();
  let n = 0;
  for (const ph of loadDefaultJapaneseParser().parse(text)) ends.add((n += ph.length));
  let pos = 0;
  for (const l of lines.slice(0, -1)) assert.ok(ends.has((pos += l.length)), JSON.stringify(lines));
  assert.ok(lines.length >= 2 && lines.every((l) => l.length <= 7), JSON.stringify(lines));
});

test('行間と文字の一部の書式', { skip }, async () => {
  const two = await layoutText(item('あい\nうえ'), fs.readFileSync);
  assert.strictEqual(two.lines.length, 2);
  assert.ok(Math.abs(two.blockW - (SIZE * 2 + SIZE * TS.line_spacing_ratio)) < 0.01, String(two.blockW));
  const big = await layoutText(item('あいう', { spans: [{ start: 1, end: 2, size_ratio: 2 }] }), fs.readFileSync);
  assert.strictEqual(big.placed[1].cell.size, SIZE * 2);
  assert.ok(Math.abs(big.blockW - SIZE * 2) < 0.01);
});

test('書体に無い字を返す', { skip }, async () => {
  const r = await layoutText(item('あ\u{1F600}'), fs.readFileSync);
  assert.deepStrictEqual(r.missing, ['\u{1F600}']);
});
