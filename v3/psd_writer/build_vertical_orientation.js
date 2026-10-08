// Unicode の VerticalOrientation.txt（UAX #50）から、縦書きの字の向きの表 vertical_orientation.json を作る。
// 使い方: node build_vertical_orientation.js VerticalOrientation.txt
//   元のファイル: https://www.unicode.org/Public/16.0.0/ucd/VerticalOrientation.txt
// 出力: { source, default: "R", ranges: [[開始, 終了, 値], ...] }。値が R の範囲は書かない（表に無い字は R）。
const fs = require('fs');
const path = require('path');

const src = process.argv[2];
if (!src) throw new Error('VerticalOrientation.txt のパスを渡してください');
const text = fs.readFileSync(src, 'utf8');
const header = text.split('\n')[0].replace(/^#\s*/, '');
const missing = text.match(/^# @missing: 0000\.\.10FFFF; (\w+)/m);
if (!missing || missing[1] !== 'R') throw new Error('表に無い字の値（@missing）が R ではない。作り方を見直してください');
const rows = [];
for (const line of text.split('\n')) {
  const m = line.match(/^([0-9A-F]+)(?:\.\.([0-9A-F]+))?\s*;\s*(U|R|Tu|Tr)\b/);
  if (!m) continue;
  const start = parseInt(m[1], 16);
  const end = m[2] ? parseInt(m[2], 16) : start;
  if (m[3] === 'R') continue;
  const last = rows[rows.length - 1];
  if (last && last[2] === m[3] && last[1] + 1 === start) last[1] = end;
  else rows.push([start, end, m[3]]);
}
rows.sort((a, b) => a[0] - b[0]);
const out = { source: header, default: 'R', ranges: rows };
fs.writeFileSync(path.join(__dirname, 'vertical_orientation.json'), JSON.stringify(out));
process.stdout.write(`${rows.length} ranges\n`);
