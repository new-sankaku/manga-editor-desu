// 原稿の画面を Playwright で通し、画面の写しを残し、動かす速さと保存の時間を測る。
// 使い方（本物のサーバー。/web を出し、V3_AUTH_MODE=dev_header で動いていること）：
//   V3_ORIGIN=http://127.0.0.1:8794 SHOTS=v3/web/manuscript/screenshots \
//   NODE_PATH=/opt/node22/lib/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node v3/web/test/manuscript_ui.mjs
// 偽のサーバー（manuscript_mock_server.mjs。本物ではない）で通すとき：V3_ORIGIN の代わりに MOCK=1。
// 作品は試験のたびに manuscript_seed.mjs で新しく作る（B5・600dpi・コマ 6・フキダシ 10・トーン 3）。
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { seed, httpCall } from "./manuscript_seed.mjs";
import { MockServer } from "./manuscript_mock_server.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const HERE = dirname(fileURLToPath(import.meta.url));
const MOCK = process.env.MOCK === "1";
const ORIGIN = MOCK ? "http://mock.v3.test" : process.env.V3_ORIGIN;
const SHOTS = process.env.SHOTS;
const USER = process.env.V3_USER || "ms-author";
if (!ORIGIN || !SHOTS) throw new Error("V3_ORIGIN（または MOCK=1）と SHOTS を決めてください");
mkdirSync(SHOTS, { recursive: true });
const label = MOCK ? "偽のサーバー" : `本物のサーバー（${ORIGIN}）`;
console.log("相手：", label);

const mock = MOCK ? new MockServer(join(HERE, "..")) : null;
const call = MOCK ? mock.call() : httpCall(ORIGIN, USER);
const ids = await seed(call, `原稿の画面の試験（${MOCK ? "偽" : "本物"}）`);
if (MOCK) {
  mock.addHeld(ids.workId, [
    { id: "held-1", target_table: "text_items", target_id: ids.texts[2], page_id: ids.pages[0], field: "text", proposed_value: "待てって！", current_value: "待って！", proposal_id: null, status: "open", created_at: "" },
    { id: "held-2", target_table: "panels", target_id: ids.panels[3], page_id: ids.pages[0], field: "frame_style", proposed_value: { line_width_mm: 0.8, line_color: "#000000" }, current_value: null, proposal_id: null, status: "open", created_at: "" },
  ]);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
await page.addInitScript((u) => { try { localStorage.setItem("v3.user", u); localStorage.removeItem("v3.ms.spread"); } catch { /* */ } }, USER);
if (MOCK) await mock.install(page, ORIGIN);

const results = { server: label };
const shots = [];
async function shot(name, opts = {}) {
  const path = `${SHOTS}/${name}.png`;
  await page.screenshot({ path, ...opts });
  const kb = Math.round(statSync(path).size / 1024);
  if (kb > 1024) throw new Error(`${path} が 1MB を超えた（${kb}KB）`);
  shots.push(path);
  console.log("shot", path, `${kb}KB`);
}
function check(cond, msg) { if (!cond) throw new Error(`確かめ失敗: ${msg}`); console.log("ok", msg); }
const S = (fn, arg) => page.evaluate(fn, arg);
const idle = () => page.waitForFunction(() => window.__ms && window.__ms.saver && !window.__ms.saver.pending() && !window.__ms.saver.running && !window.__ms.saver.undoing && !window.__ms.stepping && !window.__ms.reloading);

// ページの mm（基本枠の座標）→ 画面の点
async function at(pageId, x, y) {
  return S(([pid, x, y]) => {
    const v = window.__ms.view, s = v.slots.find((q) => q.page.id === pid);
    const r = v.c.upperCanvasEl.getBoundingClientRect(), t = v.c.viewportTransform;
    return { x: r.left + (x + s.ox) * t[0] + t[4], y: r.top + (y + s.oy) * t[3] + t[5] };
  }, [pageId, x, y]);
}
const P1 = ids.pages[0];
const count = (table, pageId) => S(([t, p]) => window.__ms.m.rows(t).filter((r) => r.page_id === p && !r.removed).length, [table, pageId]);

await page.goto(`${ORIGIN}/web/manuscript/index.html?work=${ids.workId}&page=${P1}`);
try {
  await page.waitForFunction(() => window.__ms && window.__ms.m && window.__ms.view.slots.length === 1);
  await page.waitForFunction(() => window.__ms.view.images.size >= 2, null, { timeout: 15000 });
  await page.waitForTimeout(300);
  check(await count("panels", P1) === 6 && await count("text_items", P1) === 10 && await count("page_items", P1) === 3, "1ページ目にコマ 6・フキダシ 10・トーン 3");
  check(await page.locator(".tx").count() === 10, "文字を 10 個重ねて出す");
  check(await page.locator(".tx.v").count() === 10, "縦書きで出す");
  await shot("01_page_panels_balloons");

  // ---- フキダシを動かす：1回のドラッグのコマの時間と、保存までの時間
  const t0 = ids.texts[4];
  const box = await S((id) => window.__ms.m.find("text_items", id).box_mm, t0);
  await S(() => { const v = window.__ms.view; v.perf.renders = []; v.perf.moves = []; window.__frames = []; let last = performance.now();
    const loop = (t) => { window.__frames.push(t - last); last = t; if (window.__frames.length < 600) requestAnimationFrame(loop); }; requestAnimationFrame(loop); });
  const c0 = await at(P1, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2);
  await page.mouse.move(c0.x, c0.y);
  await page.mouse.down();
  for (let i = 1; i <= 60; i++) await page.mouse.move(c0.x - i * 2, c0.y + i, { steps: 1 });
  await page.mouse.up();
  const saveStart = Date.now();
  await page.waitForFunction(([id, x]) => window.__ms.m.find("text_items", id).box_mm[0] !== x, [t0, box[0]]);
  await idle();
  const saveWall = Date.now() - saveStart;
  const perf = await S(() => {
    const v = window.__ms.view, r = [...v.perf.renders].sort((a, b) => a - b), f = window.__frames.slice(2).filter((x) => x > 0).sort((a, b) => a - b);
    const q = (a, p) => a.length ? Math.round(a[Math.min(a.length - 1, Math.floor(a.length * p))] * 10) / 10 : null;
    return { renders: r.length, render_p50: q(r, 0.5), render_p95: q(r, 0.95), render_max: q(r, 1), frame_p50: q(f, 0.5), frame_p95: q(f, 0.95), save_ms: Math.round(window.__ms.saver.lastSaveMs) };
  });
  results.drag = perf;
  results.drag.save_wall_ms = saveWall;
  const box2 = await S((id) => window.__ms.m.find("text_items", id).box_mm, t0);
  check(Math.abs(box2[0] - box[0]) > 10, "フキダシを動かした位置が正本に入った");
  const marks = await S((id) => window.__ms.m.find("text_items", id).human_hand_fields, t0);
  check(marks.includes("box_mm"), "動かした項目に人の手の印が付いた");

  // 保存の時間を 10 回（文字の大きさを変える操作）
  const saves = [];
  for (let i = 0; i < 10; i++) {
    const ms = await S(async ([id, i]) => {
      const t = performance.now();
      const { change } = await import("/web/manuscript/js/main.js");
      await change("文字の大きさ", [{ type: "update_text_item", id, font_size_pt: 9 + (i % 2) * 0.5 }], { pages: [window.__ms.pageId] });
      return performance.now() - t;
    }, [t0, i]);
    saves.push(ms);
  }
  saves.sort((a, b) => a - b);
  results.save = { n: saves.length, p50_ms: Math.round(saves[5]), max_ms: Math.round(saves[9]) };
  await idle();

  // ---- 取り消し・やり直し（ページごと）
  const before = await S((id) => window.__ms.m.find("text_items", id).font_size_pt, t0);
  await page.keyboard.press("Control+z");
  await idle();
  const undone = await S((id) => window.__ms.m.find("text_items", id).font_size_pt, t0);
  check(undone !== before, "Ctrl+Z で文字の大きさが1つ前に戻った");
  await page.keyboard.press("Control+Shift+z");
  await idle();
  await page.waitForTimeout(200);
  check(await S((id) => window.__ms.m.find("text_items", id).font_size_pt, t0) === before, "Ctrl+Shift+Z でやり直した");

  // ---- 拡大・移動（Ctrl+ホイールと、ホイール）
  const center = await at(P1, 75, 100);
  await page.mouse.move(center.x, center.y);
  const z0 = await S(() => window.__ms.view.zoom());
  await S(() => { window.__ms.view.perf.renders = []; });
  const tz = Date.now();
  for (let i = 0; i < 20; i++) { await page.keyboard.down("Control"); await page.mouse.wheel(0, -60); await page.keyboard.up("Control"); }
  await page.waitForTimeout(250);
  results.zoom = { wheel_events: 20, wall_ms: Date.now() - tz, redraws_during: await S(() => window.__ms.view.perf.renders.length), from: Math.round(z0 * 100) / 100, to: Math.round(await S(() => window.__ms.view.zoom()) * 100) / 100 };
  check(results.zoom.to > z0 * 2, "Ctrl+ホイールで広がる");
  await page.keyboard.press("0");
  await page.waitForTimeout(200);

  // ---- ナイフ
  await page.keyboard.press("c");
  // 分けた小さい側に文字が入ると、v3-server-plan のサーバーは 500 を返す（文字のコマを新しいコマへ移す更新が、
  // 新しいコマの行を入れる前に流れる。llm_doc/V3原稿の画面.md）。ここでは文字の入らない所で分ける
  const k = await at(P1, 75, 124);
  await page.mouse.move(k.x - 30, k.y);
  await page.mouse.move(k.x, k.y, { steps: 5 });
  check(await S(() => !!window.__ms.view.knifeObj), "ナイフの線をコマの上に見せる");
  await shot("02_knife_preview");
  await page.mouse.click(k.x, k.y);
  await idle();
  await page.waitForFunction((p) => window.__ms.m.panels(p).length === 7, P1);
  check(true, "ナイフでコマを2つに分けた（コマ 7）");
  await page.mouse.move(k.x + 200, k.y + 200);
  await page.waitForTimeout(150);
  await shot("03_knife_split");
  await page.keyboard.press("Control+z");
  await idle();
  await page.waitForFunction((p) => window.__ms.m.panels(p).length === 6, P1);
  check(true, "ナイフを取り消すとコマ 6 に戻る");

  // ---- 縦書きの文字を打つ（その場で）
  await page.keyboard.press("v");
  const t1 = ids.texts[0];
  const b1 = await S((id) => window.__ms.m.find("text_items", id).box_mm, t1);
  await S(([id, b]) => window.__ms.view.focusBox(window.__ms.pageId, b), [t1, b1]);
  await page.waitForTimeout(200);
  const e1 = await at(P1, (b1[0] + b1[2]) / 2, (b1[1] + b1[3]) / 2);
  await page.mouse.dblclick(e1.x, e1.y);
  await page.waitForSelector(".tx.editing");
  await page.keyboard.press("End");
  await page.keyboard.type("？\n12時だ!?");
  await page.waitForTimeout(100);
  await shot("04_vertical_text_editing");
  await page.keyboard.press("Escape");
  await idle();
  const txt = await S((id) => window.__ms.m.find("text_items", id).text, t1);
  check(txt.endsWith("12時だ!?"), `打った文字が正本に入った（${JSON.stringify(txt)}）`);
  check(await page.locator(`.tx[data-id="${t1}"] .tcy`).count() >= 1, "数字と !? を縦中横で見せる");
  await page.keyboard.press("0");

  // ---- 判断待ち
  if (MOCK) {
    await page.keyboard.press("j");
    await page.waitForTimeout(200);
    const hs = await S(() => ({ n: window.__ms.held.length, tab: window.__ms.tab, active: document.activeElement && document.activeElement.tagName }));
    check(await page.locator(".held-row").count() === 2, `判断待ちを 2 件並べる（偽のサーバーが作ったもの）${JSON.stringify(hs)}`);
    await shot("05_held_changes");
    await page.keyboard.press("x");
    await idle();
    await page.waitForFunction(() => window.__ms.held.length === 1);
    check(true, "X で判断待ちを断る");
    await page.keyboard.press("0");
  }

  // ---- 見開き
  await page.click("#view-spread");
  await page.waitForFunction(() => window.__ms.view.slots.length === 2);
  check(true, "見開きで2ページを並べる");
  await page.keyboard.press("PageDown");
  await page.waitForFunction((p) => window.__ms.view.slots.some((s) => s.page.id === p) && window.__ms.view.slots.length === 2, ids.pages[2]);
  const sl = await S(() => window.__ms.view.slots.map((s) => ({ id: s.page.id, side: s.side, x: s.x })));
  check(sl[0].id === ids.pages[3] && sl[1].id === ids.pages[2], "右から読む：3ページが右・4ページが左");
  check(sl[1].x === 182, "見開きの組のページは、ノドで付けて並べる");
  await page.waitForTimeout(200);
  await shot("06_spread");
  await page.keyboard.press("PageUp");
  await page.waitForFunction((p) => window.__ms.view.slots.some((s) => s.page.id === p), P1);
  await page.waitForTimeout(250);
  await shot("07_spread_page1_2");

  // ---- ページの一覧：並べ替え（2ページを1ページの前へ。3・4ページは見開きの組なので離せない）
  await page.click("#view-spread");
  const cards = page.locator(".pcard");
  check(await cards.count() === 4, "ページの一覧に 4 ページ");
  const from = await cards.nth(1).locator(".pthumb").boundingBox();
  const to = await cards.nth(0).locator(".pthumb").boundingBox();
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + from.width / 2 + 10, from.y + from.height / 2, { steps: 3 });
  await page.mouse.move(to.x + 4, to.y + to.height / 2, { steps: 12 });
  await page.mouse.up();
  await idle();
  await page.waitForTimeout(300);
  const order = await S((ep) => window.__ms.m.pages(ep).map((p) => p.id), ids.episodeId);
  check(order[0] === ids.pages[1], "ドラッグで並べ替えると正本の番号が変わる");
  await shot("08_page_list", { clip: { x: 0, y: 900 - 220, width: 1010, height: 220 } });
  await page.keyboard.press("Control+z");
  await idle();
  await page.waitForTimeout(200);
  check((await S((ep) => window.__ms.m.pages(ep).map((p) => p.id), ids.episodeId))[1] === ids.pages[1], "並べ替えを取り消せる");
  await shot("09_page_list_and_settings");

  // ---- 入稿前の確かめ
  await page.click('.itab[data-tab="check"]');
  await page.click("#pf-ep");
  await page.waitForSelector(".issue, .note", { timeout: 60000 });
  await page.waitForFunction(() => window.__ms.preflight && !window.__ms.preflight.running, null, { timeout: 60000 });
  const pf = await S(() => ({ errors: window.__ms.preflight.errors, warnings: window.__ms.preflight.warnings, kinds: [...new Set(window.__ms.preflight.issues.map((x) => x.kind))] }));
  results.preflight = pf;
  check(pf.errors + pf.warnings > 0, `確かめで問題が並ぶ（${JSON.stringify(pf)}）`);
  const withLoc = page.locator(".issue:has(svg.lucide-crosshair)");
  if (await withLoc.count()) {
    await withLoc.first().click();
    await page.waitForTimeout(300);
    check(await S(() => !!window.__ms.sel), "問題を押すとその場所を選ぶ");
  }
  await shot("10_preflight");

  // ---- 画像生成の画面へのリンク
  await page.keyboard.press("Escape");
  const href = await S((pid) => { const { workbenchUrl } = window.__msMain || {}; void workbenchUrl; return document.querySelector("#to-workbench").getAttribute("href"); }, null);
  check(href.startsWith("../index.html?work="), `画像生成の画面へのリンク（${href}）`);

  check(errors.length === 0, `画面のエラーなし ${errors.join(" / ")}`);
} catch (e) {
  await page.screenshot({ path: `${SHOTS}/zz_failure.png` }).catch(() => {});
  console.error(errors.join("\n"));
  await browser.close();
  throw e;
}
await browser.close();
console.log("RESULTS", JSON.stringify(results));
console.log("SHOTS", shots.join(" "));
