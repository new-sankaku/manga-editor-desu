// 画面の試験（Playwright）で共通に使う部品。
// - openBrowser：PW_WS（run_ui.mjs が1回だけ起こしたブラウザ）があればそこへつなぎ、無ければ自分で起こす。
//   どちらでも試験のファイルごとに新しい context を作る（cookie・localStorage を分ける）
// - makeShot：画面の写しは SHOTS を決めたときだけ撮る（普段の試験では撮らない。1枚 1MB 未満かも確かめる）
// - serveWeb：画面のファイル（v3/web）を、偽の住所の下でそのまま出す。口の答えは answer(route, url) で決める
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

export const WEB_DIR = fileURLToPath(new URL("..", import.meta.url));
export const SHOTS = process.env.SHOTS || null;
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

export async function openBrowser() {
  return process.env.PW_WS ? chromium.connect(process.env.PW_WS) : chromium.launch();
}

// 画面が描き終わるまで待つ（次の描画を2回待つ）。写しを撮る前に使う
export async function settled(page) {
  await page.evaluate(() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok))));
}

// 写しを撮る関数を返す。SHOTS が無ければ何もしない。onSize(name, kb) で大きさの確かめを呼んだ側に渡す
export function makeShot(page, { onSize, prefix = "" } = {}) {
  const taken = [];
  async function shot(name, opts = {}) {
    if (!SHOTS) return null;
    await settled(page);
    const path = `${SHOTS}/${prefix}${name}.png`;
    await page.screenshot({ path, ...opts });
    const kb = Math.round(statSync(path).size / 1024);
    taken.push(path);
    if (onSize) onSize(name, kb);
    else if (kb >= 1024) throw new Error(`${path} が 1MB を超えた（${kb}KB）`);
    console.log("shot", path, `${kb}KB`);
    return path;
  }
  shot.taken = taken;
  return shot;
}

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
                ".svg": "image/svg+xml", ".json": "application/json", ".png": "image/png", ".woff2": "font/woff2" };

// origin の下の /web/… は v3/web のファイルを出し、ほかは answer(route, url) に任せる
export async function serveWeb(page, origin, answer) {
  await page.route(`${origin}/**`, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/web/")) {
      const f = normalize(join(WEB_DIR, decodeURIComponent(url.pathname.slice(5)) || "index.html"));
      const file = f.endsWith("/") ? join(f, "index.html") : f;
      if (!file.startsWith(WEB_DIR) || !existsSync(file)) return route.fulfill({ status: 404, body: "無い" });
      return route.fulfill({ status: 200, body: readFileSync(file), contentType: TYPES[extname(file)] || "application/octet-stream" });
    }
    return answer(route, url);
  });
}

// 画面の呼び出しが静まるまで待つ道具を返す。Playwright の networkidle は 500ms 静まるのを待つので、
// 呼び出しの数を自分で数え、0 のまま quietMs 続いたら返す（SSE のような開いたままの呼び出しがある画面には使わない）
export function trackRequests(page, quietMs = 100) {
  let inflight = 0;
  let last = Date.now();
  const done = () => { inflight = Math.max(0, inflight - 1); last = Date.now(); };
  page.on("request", () => { inflight += 1; last = Date.now(); });
  page.on("requestfinished", done);
  page.on("requestfailed", done);
  return async function quiet(timeoutMs = 15000) {
    const deadline = Date.now() + timeoutMs;
    while (inflight > 0 || Date.now() - last < quietMs) {
      if (Date.now() > deadline) throw new Error(`呼び出しが ${timeoutMs}ms 静まらなかった（残り ${inflight} 件）`);
      await new Promise((ok) => setTimeout(ok, 20));
    }
  };
}
