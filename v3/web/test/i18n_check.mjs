// 画面の文言が、どの言語の辞書にも漏れなく入っているかを確かめる（ブラウザは要らない。llm_doc/V3細部の決めごと.md 24章）。
//   node v3/web/test/i18n_check.mjs                全部を確かめる
//   node v3/web/test/i18n_check.mjs --area harness そのまとまりのファイルと辞書だけを確かめる（まとまりどうしの訳の食い違いは見ない）
// 止めるもの：
//   1. 日本語の文字列が t() に包まれていない（JS の文字列・テンプレートの地の文・HTML の文字と属性）
//   2. t() の1つ目が、そのまま書いた文字列でない（変数や式を渡している）
//   3. 使っている文言が辞書に無い（count を渡す文言は、その言語の数の形 _one・_other などが全部要る）
//   4. 辞書に、使っていない文言がある・訳が空・訳に日本語が残る・{{ }} の名前が元の文言に無い
//   5. 同じ文言の訳が、まとまりによって違う
//   6. どのまとまりにも入っていないファイルがある・common/i18n.js の LANGS と i18n/ のフォルダが合わない
// 訳さない物の印（コメントに書く）：
//   // i18n:data   画面の文言ではないデータ（サーバーと突き合わせる名前・PSD の層の名前など）。同じ行の文字列を外す
//   // i18n:dev    作る人だけが見る文（画面に出ない例外など）。同じ行の文字列を外す
//   // i18n:off 〜 // i18n:on   間の行をまとめて外す（データの表など）
//   console.*( ) の中の文字列は、印が無くても外す
//   HTML では、要素に data-i18n-skip を付けると、その開始タグの属性と直後の文字を外す
// 部品：acorn 8.19.0（test/vendor/acorn-8.19.0。MIT）で JS を読む
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "./vendor/acorn-8.19.0/acorn.mjs";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
// 画面のまとまり → 入るファイルの頭。辞書は i18n/<言語>/<まとまり>.js
const AREAS = {
  common: ["common/"],
  harness: ["harness/"],
  imagegen: ["index.html", "js/"],
  manuscript: ["manuscript/"],
  planning: ["works/", "plan/", "structure/"],
  production: ["materials/", "export/", "services/", "import/", "translation/", "review/"],
};
const SKIP_DIRS = new Set(["vendor", "test", "i18n", "screenshots", "css"]);
const JA = /[぀-ヿ一-鿿]/;
const ATTRS = ["title", "aria-label", "placeholder", "alt", "label", "value"];
const squash = (s) => s.replace(/\s+/g, " ").trim();
const rel = (f) => relative(WEB, f).split(sep).join("/");

const only = process.argv.includes("--area") ? process.argv[process.argv.indexOf("--area") + 1] : null;
if (only && !AREAS[only]) { console.error(`--area は ${Object.keys(AREAS).join("・")} のどれか`); process.exit(2); }

const bad = [];
const report = (file, line, kind, text) => bad.push(`${file}:${line}  ${kind}  ${text.length > 90 ? text.slice(0, 90) + "…" : text}`);
const used = {};  // まとまり → Map(文言 → { count を渡すか, 場所 })
for (const a of Object.keys(AREAS)) used[a] = new Map();
function use(area, key, plural, where) {
  const u = used[area].get(key) || { plural: false, where };
  u.plural = u.plural || plural;
  used[area].set(key, u);
}

function areaOf(file) {
  return Object.keys(AREAS).find((a) => AREAS[a].some((p) => (p.endsWith("/") ? file.startsWith(p) : file === p)));
}
function* walkFiles(dir) {
  for (const name of readdirSync(dir).sort()) {
    const f = join(dir, name);
    if (statSync(f).isDirectory()) { if (!SKIP_DIRS.has(name)) yield* walkFiles(f); }
    else if (/\.(js|html)$/.test(name)) yield f;
  }
}

// ---------------------------------------------------------------- JS
function scanJs(code, file, area, firstLine = 1, sourceType = "module") {
  const comments = [];
  let ast;
  try { ast = parse(code, { ecmaVersion: "latest", sourceType, locations: true, onComment: comments }); }
  catch (e) { report(file, firstLine, "読めない JS", e.message); return; }
  const skipLines = new Set();
  let off = null;
  for (const c of comments) {
    if (/i18n:(data|dev)\b/.test(c.value)) for (let l = c.loc.start.line; l <= c.loc.end.line; l++) skipLines.add(l);
    if (/i18n:off\b/.test(c.value)) off = c.loc.start.line;
    if (/i18n:on\b/.test(c.value) && off !== null) { for (let l = off; l <= c.loc.end.line; l++) skipLines.add(l); off = null; }
  }
  if (off !== null) report(file, off + firstLine - 1, "i18n:off を閉じていない", "");
  const skipped = (n) => { for (let l = n.loc.start.line; l <= n.loc.end.line; l++) if (skipLines.has(l)) return true; return false; };
  const line = (n) => n.loc.start.line + firstLine - 1;
  const text = (n) => (n.type === "Literal" && typeof n.value === "string" ? n.value
    : n.type === "TemplateLiteral" && n.expressions.length === 0 ? n.quasis[0].value.cooked : null);
  const isT = (n) => n.type === "CallExpression" && n.callee.type === "Identifier" && n.callee.name === "t";
  const isConsole = (n) => n.type === "CallExpression" && n.callee.type === "MemberExpression" && n.callee.object.type === "Identifier" && n.callee.object.name === "console";
  function visit(n) {
    if (!n || typeof n.type !== "string") return;
    if (isConsole(n)) return;
    if (isT(n) && file !== "common/i18n.js") {
      const key = n.arguments[0] ? text(n.arguments[0]) : null;
      if (key === null) report(file, line(n), "t() の1つ目が文字列でない", code.slice(n.start, Math.min(n.end, n.start + 80)));
      else {
        const o = n.arguments[1];
        const plural = !!o && o.type === "ObjectExpression" && o.properties.some((p) => p.type === "Property" && (p.key.name || p.key.value) === "count");
        use(area, key, plural, `${file}:${line(n)}`);
      }
      for (const a of n.arguments.slice(1)) visit(a);
      return;
    }
    if (n.type === "Literal" && typeof n.value === "string" && JA.test(n.value) && !skipped(n)) report(file, line(n), "t() に包んでいない", n.value);
    if (n.type === "TemplateElement" && JA.test(n.value.cooked || "") && !skipped(n)) report(file, line(n), "t() に包んでいない（テンプレートの地の文）", squash(n.value.cooked));
    for (const k of Object.keys(n)) {
      const v = n[k];
      if (Array.isArray(v)) v.forEach(visit);
      else if (v && typeof v.type === "string") visit(v);
    }
  }
  visit(ast);
}

// ---------------------------------------------------------------- HTML
function scanHtml(src, file, area) {
  const tokens = src.match(/<!--[\s\S]*?-->|<script\b[\s\S]*?<\/script>|<style\b[\s\S]*?<\/style>|<[^>]+>|[^<]+/g) || [];
  let pos = 0, prevTag = null;
  const lineAt = (p) => src.slice(0, p).split("\n").length;
  const attr = (tag, name) => { const m = tag.match(new RegExp(`\\s${name}\\s*=\\s*"([^"]*)"`)); return m ? m[1] : null; };
  const has = (tag, name) => new RegExp(`\\s${name}(\\s|=|>|/)`).test(tag);
  tokens.forEach((tok, i) => {
    const line = lineAt(pos);
    pos += tok.length;
    if (tok.startsWith("<!--") || /^<style\b/i.test(tok)) return;
    if (/^<script\b/i.test(tok)) {
      const open = tok.slice(0, tok.indexOf(">") + 1), body = tok.slice(open.length, tok.lastIndexOf("</script"));
      if (body.trim()) scanJs(body, file, area, line + open.split("\n").length - 1, /type\s*=\s*"module"/.test(open) ? "module" : "script");
      return;
    }
    if (tok.startsWith("<")) {
      if (tok.startsWith("</")) { prevTag = null; return; }
      prevTag = tok;
      if (has(tok, "data-i18n-skip")) return;
      const marked = (attr(tok, "data-i18n-attr") || "").split(/\s+/).filter(Boolean);
      for (const a of marked) {
        const v = attr(tok, a);
        if (v === null) report(file, line, "data-i18n-attr の属性が無い", a); else use(area, squash(v), false, `${file}:${line}`);
      }
      for (const a of ATTRS) { const v = attr(tok, a); if (v !== null && JA.test(v) && !marked.includes(a)) report(file, line, `data-i18n-attr に ${a} が無い`, v); }
      return;
    }
    if (!JA.test(tok)) { if (tok.trim()) prevTag = null; return; }
    const next = tokens[i + 1] || "";
    if (prevTag && has(prevTag, "data-i18n-skip")) return;
    if (prevTag && has(prevTag, "data-i18n") && next.startsWith("</")) use(area, squash(tok), false, `${file}:${line}`);
    else report(file, line, "data-i18n が無い（文字だけを持つ要素に付ける）", squash(tok));
    prevTag = null;
  });
}

// ---------------------------------------------------------------- 辞書
function readDict(file) {
  const out = new Map();
  let ast;
  try { ast = parse(readFileSync(join(WEB, file), "utf8"), { ecmaVersion: "latest", sourceType: "module", locations: true }); }
  catch (e) { report(file, 1, "読めない辞書", e.message); return out; }
  const exp = ast.body.find((n) => n.type === "ExportDefaultDeclaration");
  if (!exp || exp.declaration.type !== "ObjectExpression") { report(file, 1, "辞書は export default { … } の形にする", ""); return out; }
  for (const p of exp.declaration.properties) {
    const k = p.type === "Property" && !p.computed ? (p.key.type === "Literal" ? String(p.key.value) : p.key.name) : null;
    const v = p.type === "Property" && (p.value.type === "Literal" && typeof p.value.value === "string" ? p.value.value
      : p.value.type === "TemplateLiteral" && p.value.expressions.length === 0 ? p.value.quasis[0].value.cooked : null);
    if (k === null || v === null || v === false) { report(file, p.loc.start.line, "辞書の行は \"文言\": \"訳\" の形にする", ""); continue; }
    if (out.has(k)) report(file, p.loc.start.line, "辞書に同じ文言が2つある", k);
    out.set(k, { v, line: p.loc.start.line });
  }
  return out;
}
const vars = (s) => new Set([...s.matchAll(/\{\{\s*([\w.]+)[^}]*\}\}/g)].map((m) => m[1]));

// ---------------------------------------------------------------- 流す
for (const f of walkFiles(WEB)) {
  const file = rel(f), area = areaOf(file);
  if (!area) { report(file, 1, "どのまとまりにも入っていない（i18n_check.mjs の AREAS に足す）", ""); continue; }
  if (only && area !== only) continue;
  const src = readFileSync(f, "utf8");
  if (file.endsWith(".js")) scanJs(src, file, area); else scanHtml(src, file, area);
}

const langs = readdirSync(join(WEB, "i18n")).filter((n) => statSync(join(WEB, "i18n", n)).isDirectory()).sort();
const declared = [...readFileSync(join(WEB, "common/i18n.js"), "utf8").match(/export const LANGS = (\[\[.*?\]\]);/)[1].matchAll(/\["(\w+)"/g)].map((m) => m[1]);
if (declared.filter((l) => l !== "ja").sort().join() !== langs.join()) report("common/i18n.js", 1, "LANGS と i18n/ のフォルダが合わない", `${declared.join()} / ${langs.join()}`);

for (const lng of langs) {
  const forms = new Intl.PluralRules(lng).resolvedOptions().pluralCategories;
  const index = existsSync(join(WEB, "i18n", `${lng}.js`)) ? readFileSync(join(WEB, "i18n", `${lng}.js`), "utf8") : null;
  if (index === null) report(`i18n/${lng}.js`, 1, "まとめるファイルが無い", "");
  const seen = new Map();  // 文言 → { 訳, ファイル }
  for (const area of Object.keys(AREAS)) {
    if (only && area !== only) continue;
    const file = `i18n/${lng}/${area}.js`;
    if (!existsSync(join(WEB, file))) { report(file, 1, "辞書が無い", ""); continue; }
    if (index !== null && !index.includes(`./${lng}/${area}.js`)) report(`i18n/${lng}.js`, 1, "まとめるファイルが辞書を読んでいない", area);
    const dict = readDict(file), needed = new Set();
    for (const [key, u] of used[area]) {
      const keys = u.plural ? forms.map((c) => `${key}_${c}`) : [key];
      for (const k of keys) { needed.add(k); if (!dict.has(k)) report(file, 1, `辞書に無い（${u.where}）`, k); }
    }
    for (const [k, { v, line }] of dict) {
      if (!needed.has(k)) report(file, line, "使っていない文言", k);
      if (!v.trim()) report(file, line, "訳が空", k);
      if (lng !== "zh" && JA.test(v)) report(file, line, "訳に日本語が残っている", `${k} → ${v}`);
      const kv = vars(k);
      for (const x of vars(v)) if (!kv.has(x)) report(file, line, "訳の {{ }} が元の文言に無い", `${k} → ${v}`);
      const s = seen.get(k);
      if (s && s.v !== v) report(file, line, `同じ文言の訳が違う（${s.file}）`, `${k} → ${v} / ${s.v}`);
      else seen.set(k, { v, file });
    }
  }
}

const total = Object.values(used).reduce((n, m) => n + m.size, 0);
if (bad.length) {
  console.log(bad.join("\n"));
  console.log(`\ni18n_check：${bad.length} 件（文言 ${total}・言語 ${langs.join("・")}${only ? `・まとまり ${only}` : ""}）`);
  process.exit(1);
}
console.log(`i18n_check：ok（文言 ${total}・言語 ${langs.join("・")}${only ? `・まとまり ${only}` : ""}）`);
