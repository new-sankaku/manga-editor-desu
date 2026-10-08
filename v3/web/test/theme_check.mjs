// 色の組の確かめ（V3細部の決めごと 8章）。ブラウザは要らない。
//   node v3/web/test/theme_check.mjs
// 1. 組のファイル（common/themes/）の外の CSS・JS・HTML に、色の値（#…・rgb(数)・hsl(数)・white などの名前）が無いこと
//    - CSS は { } の中（宣言）だけを見る（#user のような id の書き方を拾わないため）
//    - JS は文字列の中の "#…" と、rgb(数…)・hsl(数…)、色の名前の文字列を見る
//    - rgba(var(--shade),…) のように組の名前から作る物は値ではないので通す
//    - その行に「色の決め打ちを許す：」と理由があれば通す（絵の中身の色など、画面の色でない物だけに使う）
// 2. common/theme.css に書いた名前（--名前：意味）が、どの組のファイルにも全部あること
// 見ないもの：vendor/（よそのライブラリ）・test/・screenshots/
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = fileURLToPath(new URL("..", import.meta.url));
const THEMES = join(WEB, "common", "themes");
const SKIP = new Set([join(WEB, "vendor"), join(WEB, "test"), join(WEB, "screenshots"), THEMES]);
const ALLOW = "色の決め打ちを許す：";
const NAMES = "white|black|red|green|blue|gray|grey|orange|yellow|purple|pink|brown|silver|navy|teal|maroon|olive|cyan|magenta";

const HEX = /#[0-9a-fA-F]{3,8}\b/;
const FUNC = /\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(\s*[\d.]/;
const NAMED_CSS = new RegExp(`(:|\\s|,)(${NAMES})(\\s|;|,|\\)|$)`, "i");
const JS_HEX = /["'`]#[0-9a-fA-F]{3,8}["'`]/;
const JS_NAMED = new RegExp(`["'\`](${NAMES})["'\`]`, "i");

function walk(dir, out = []) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (SKIP.has(p)) continue;
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(css|js|mjs|html)$/.test(n)) out.push(p);
  }
  return out;
}

function cssDecls(text) {
  // コメントを消して、{ } の中だけを行ごとに返す（行番号を保つ）
  const noComment = text.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
  let depth = 0;
  return noComment.split("\n").map((line) => {
    let kept = "";
    for (const ch of line) {
      if (ch === "{") { depth += 1; kept += " "; continue; }
      if (ch === "}") { depth -= 1; kept += " "; continue; }
      kept += depth > 0 ? ch : " ";
    }
    return kept;
  });
}

const found = [];
for (const file of walk(WEB)) {
  const text = readFileSync(file, "utf8");
  const lines = text.split("\n");
  const rel = relative(WEB, file);
  if (file.endsWith(".css")) {
    // @media { .a { … } } の中の .a は depth 1 に入るので、宣言（名前:値）の形の所だけを見る
    cssDecls(text).forEach((l, i) => {
      if (lines[i].includes(ALLOW)) return;
      for (const decl of l.split(";")) {
        const m = decl.match(/^[^:]*?([a-z-]+)\s*:(.*)$/i);
        if (!m) continue;
        const v = m[2];
        if (HEX.test(v) || FUNC.test(v) || NAMED_CSS.test(` ${v}`)) found.push(`${rel}:${i + 1}: ${decl.trim()}`);
      }
    });
  } else {
    lines.forEach((l, i) => {
      if (l.includes(ALLOW)) return;
      const code = l.replace(/\/\/.*$/, "");
      if (JS_HEX.test(code) || FUNC.test(code) || JS_NAMED.test(code) || (file.endsWith(".html") && /style="[^"]*(#[0-9a-fA-F]{3,8}\b|\b(rgba?|hsla?)\(\s*\d)/.test(code))) {
        found.push(`${rel}:${i + 1}: ${l.trim().slice(0, 160)}`);
      }
    });
  }
}

const contract = readFileSync(join(WEB, "common", "theme.css"), "utf8");
const names = [...contract.matchAll(/^\s*(--[a-z0-9-]+)：/gm)].map((m) => m[1]);
const missing = [];
for (const n of readdirSync(THEMES).filter((x) => x.endsWith(".css"))) {
  const t = readFileSync(join(THEMES, n), "utf8");
  for (const name of names) if (!new RegExp(`${name}\\s*:`).test(t)) missing.push(`themes/${n} に ${name} が無い`);
}
if (!names.length) missing.push("common/theme.css から名前を読めませんでした");

for (const f of found) console.log("色の値：", f);
for (const m of missing) console.log("名前：", m);
console.log(`見た名前 ${names.length} 個。色の値 ${found.length} 件、足りない名前 ${missing.length} 件`);
if (found.length || missing.length) process.exit(1);
