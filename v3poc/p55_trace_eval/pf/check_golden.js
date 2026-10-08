// P55 回帰の判定。P55_MODE=record なら今回の答えを golden.json に記録する。P55_MODE=compare なら記録と一致するかを見る。
// 記録が無いのに compare なら失敗にする(黙って通さない)。
const fs = require('fs');
const path = require('path');
const GOLDEN = path.resolve(__dirname, '../out/golden.json');
const norm = (s) => String(s).trim().replace(/[。.\s]/g, '');
module.exports = (output, context) => {
  const id = context.vars.id;
  const mode = process.env.P55_MODE;
  const now = norm(output);
  let g = {};
  try { g = JSON.parse(fs.readFileSync(GOLDEN, 'utf8')); } catch (e) { g = {}; }
  if (mode === 'record') {
    g[id] = now;
    fs.writeFileSync(GOLDEN, JSON.stringify(g, null, 1));
    return { pass: true, score: 1, reason: `記録 ${id}=${now}` };
  }
  if (mode !== 'compare') return { pass: false, score: 0, reason: 'P55_MODE が record でも compare でもない' };
  if (!(id in g)) return { pass: false, score: 0, reason: `記録が無い ${id}` };
  return { pass: g[id] === now, score: g[id] === now ? 1 : 0, reason: `記録=${g[id]} 今回=${now}` };
};
