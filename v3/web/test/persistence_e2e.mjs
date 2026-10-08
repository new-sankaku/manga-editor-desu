// 保存と再起動の確かめ（opt-in の e2e の組。速い組には入れない）。
// 本物の一式（PostgreSQL・Temporal・OpenFGA・口のサーバー・作業者）を、ほかの作業と分けて動かし（v3/server/tests/persistence/stack.sh）、
// 画面で編集した物が、開き直し・口のサーバーの再起動・作業者の停止・既製品の再起動・compose の down と up の後も
// 同じに残るかを確かめる。偽物は LLM・検出器・ComfyUI だけ（fake_workers_main.py・fake_comfy_main.py）。
//
//   NODE_PATH=/opt/node22/lib/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node v3/web/test/persistence_e2e.mjs
//
// 前提を作るのは口から（seed_work.py）。画面で行うのは、残るべき編集と、開き直した後の確かめだけ。ブラウザは1回だけ起こす。
// 待つのは状態（保存の待ち行列が空・正本の値・画面の画素が落ち着く）で、決まった時間は待たない。
// 結果は PE_DIR（既定 /tmp/v3pe）の results.json に置く。画面の写しは SHOTS=<フォルダ> を付けたときだけそこへ置く（比べる写しは手元の記憶で持つ）。手順と結果は llm_doc/V3サーバーの土台.md「保存と再起動の確かめ」。
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const V3 = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SERVER = `${V3}/server`;
const STACK = `${SERVER}/tests/persistence/stack.sh`;
const PE_DIR = process.env.PE_DIR || "/tmp/v3pe";
const API = `http://127.0.0.1:${process.env.V3PE_API_PORT || 8961}`;
const COMFY = `http://127.0.0.1:${process.env.V3PE_COMFY_PORT || 8963}`;
const SHOTS = process.env.SHOTS || null;
const ADMIN = "pe-admin", USER = "pe-author";
mkdirSync(PE_DIR, { recursive: true });
if (SHOTS) mkdirSync(SHOTS, { recursive: true });
const save = (name, data) => { if (SHOTS) writeFileSync(`${SHOTS}/${name}`, data); };

const results = { scenarios: {}, checks: [], expected_changes: [], findings: [] };
const t0 = Date.now();
const log = (...a) => console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s]`, ...a);
function check(cond, msg) { if (!cond) throw new Error(`確かめ失敗: ${msg}`); results.checks.push(msg); log("ok", msg); }
function stack(...args) { log("stack.sh", args.join(" ")); return execFileSync(STACK, args, { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] }); }
const tick = (ms) => new Promise((r) => setTimeout(r, ms));
// 状態を待つ（fn が値を返すまで問い合わせる）。決まった時間は待たない
async function until(fn, what, timeout = 30000) {
  const end = Date.now() + timeout;
  let last;
  while (Date.now() < end) {
    try { const v = await fn(); if (v) return v; } catch (e) { last = e; }
    await tick(150);
  }
  throw new Error(`待ちきれなかった: ${what}${last ? `（${last.message}）` : ""}`);
}

async function api(method, p, body, who = USER) {
  const r = await fetch(`${API}${p}`, { method, headers: { "X-V3-User": who, "X-V3-Request": "1", "Content-Type": "application/json" },
                                        body: body === undefined ? undefined : JSON.stringify(body) });
  const t = await r.text();
  if (r.status >= 300) throw new Error(`${method} ${p} → ${r.status} ${t.slice(0, 300)}`);
  return t ? JSON.parse(t) : null;
}
// /health/ready は作業者を見ない。作業者のプロセスが生きていることは stack.sh status で見る（前は作業者が落ちたまま進み、最後の承認で止まった）
const workersUp = () => /^workers up$/m.test(execFileSync(STACK, ["status"], { encoding: "utf8" }));
const ready = () => until(async () => workersUp() && (await fetch(`${API}/health/ready`)).status === 200, "口のサーバーと作業者がそろう", 90000);

// ---------------------------------------------------------------- 一式を起こし、前提を口から入れる
stack("up");
stack("migrate");
stack("grant-admin", ADMIN);
for (const n of ["api", "workers", "comfy"]) stack("stop", n);
for (const n of ["comfy", "api", "workers"]) stack("start", n);
await ready();
const seed = JSON.parse(execFileSync("uv", ["run", "python", "tests/persistence/seed_work.py", "--api", API, "--comfy", COMFY,
                                            "--admin", ADMIN, "--author", USER], { cwd: SERVER, encoding: "utf8" }).trim().split("\n").pop());
const W = seed.workId, [EP1, EP2, EP3] = seed.episodes, [P1, P2] = seed.pages, [TOP, LOW] = seed.panels;
log("作品", W);
const harnessUnit = async (stageRun) => (await api("GET", `/works/${W}/harness/snapshot`)).units.find((u) => u.stage_run_id === stageRun);
await until(async () => (await harnessUnit(seed.stageRun))?.status === "awaiting_review", "話2の工程が確認待ちになる", 90000);
check(true, "前提：話2のハーネスの作業が確認待ち（偽の LLM・検出器・ComfyUI）");

// ---------------------------------------------------------------- ブラウザ（1回だけ起こす）
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 });
await ctx.addInitScript((u) => { try { localStorage.setItem("v3.user", u); } catch { /* */ } }, USER);
const page = await ctx.newPage();
const errors = [];
const dialogs = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
// 閉じる前に聞く（beforeunload）は数えてから進む
page.on("dialog", (d) => { dialogs.push(d.type()); d.accept().catch(() => {}); });
const S = (fn, arg) => page.evaluate(fn, arg);

// 原稿の画面
const msIdle = () => page.waitForFunction(() => window.__ms && window.__ms.saver && !window.__ms.saver.pending() && !window.__ms.saver.running
  && !window.__ms.saver.undoing && !window.__ms.stepping && !window.__ms.reloading && !window.__ms.saver.failed, null, { timeout: 30000 });
async function openManuscript(pageId = P1) {
  await page.goto(`${API}/web/manuscript/index.html?work=${W}&page=${pageId}`);
  await page.waitForFunction((p) => window.__ms && window.__ms.m && window.__ms.pageId === p && window.__ms.view.slots.length >= 1, pageId, { timeout: 30000 });
  await msIdle();
  await imagesLoaded();
}
// コマの絵を読み終えるまで待つ（読み終えると描き直し、打っている文字の欄が閉じる。llm_doc/V3原稿の画面.md の未修正の件）。
// 読み終えた後の描き直しは 30ms 後なので、読み込み中の絵が無い状態が 60ms 続くまで待つ
const imagesLoaded = () => page.waitForFunction(() => new Promise((r) => {
  const none = () => { const l = window.__ms.view.loading; return !l || !l.size; };
  if (!none()) return r(false);
  setTimeout(() => r(none()), 60);
}), null, { timeout: 30000 });
async function at(pageId, x, y) {
  return S(([pid, x, y]) => {
    const v = window.__ms.view, s = v.slots.find((q) => q.page.id === pid);
    const r = v.c.upperCanvasEl.getBoundingClientRect(), t = v.c.viewportTransform;
    return { x: r.left + (x + s.ox) * t[0] + t[4], y: r.top + (y + s.oy) * t[3] + t[5] };
  }, [pageId, x, y]);
}
const selectPage = (id) => S(async (id) => { (await import("/web/manuscript/js/main.js")).selectPage(id); }, id)
  .then(() => page.waitForFunction((id) => window.__ms.pageId === id && window.__ms.view.slots.some((s) => s.page.id === id), id)).then(imagesLoaded);
const model = (fn, arg) => S(fn, arg);
const beforeUnloadAsks = () => S(() => { const e = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(e); return e.defaultPrevented; });

// 要素の写しが落ち着くまで撮り直す（絵の読み込みを待つ。2回続けて同じなら落ち着いた）
async function stableShot(locator, name) {
  let prev = null;
  const buf = await until(async () => {
    const b = await locator.screenshot();
    const same = prev && prev.equals(b);
    prev = b;
    return same ? b : null;
  }, `${name} の写しが落ち着く`, 20000);
  save(`${name}.png`, buf);
  return buf;
}
// 2枚の PNG の違う画素の数（ブラウザで読む。色の差が 8 を超える画素）
async function pixelDiff(a, b) {
  return S(async ([a, b]) => {
    const load = async (s) => { const i = new Image(); i.src = `data:image/png;base64,${s}`; await i.decode(); return i; };
    const [x, y] = await Promise.all([load(a), load(b)]);
    if (x.width !== y.width || x.height !== y.height) return { size: [x.width, x.height, y.width, y.height], diff: -1 };
    const read = (i) => { const c = document.createElement("canvas"); c.width = i.width; c.height = i.height; const g = c.getContext("2d"); g.drawImage(i, 0, 0); return g.getImageData(0, 0, i.width, i.height).data; };
    const p = read(x), q = read(y);
    let n = 0;
    for (let k = 0; k < p.length; k += 4) if (Math.abs(p[k] - q[k]) > 8 || Math.abs(p[k + 1] - q[k + 1]) > 8 || Math.abs(p[k + 2] - q[k + 2]) > 8) n++;
    return { diff: n, total: p.length / 4 };
  }, [a.toString("base64"), b.toString("base64")]);
}

// 小さい PNG（絵を置く・ブラウザで作る）
async function smallPng() {
  await page.goto(`${API}/web/manuscript/index.html`);
  const b64 = await S(() => { const c = document.createElement("canvas"); c.width = 64; c.height = 48; const g = c.getContext("2d");
    g.fillStyle = "#ddd"; g.fillRect(0, 0, 64, 48); g.fillStyle = "#333"; g.beginPath(); g.arc(32, 24, 14, 0, 7); g.fill();
    return c.toDataURL("image/png").split(",")[1]; });
  return Buffer.from(b64, "base64");
}

try {
  const placePng = await smallPng();

  // ================================================================ 1. 画面で編集する（残るべき物）
  await openManuscript(P1);
  // ページを足す・見開き
  await page.click("#page-add");
  await page.waitForFunction((ep) => window.__ms.m.pages(ep).length === 3, EP1);
  await msIdle();
  const P3 = await model((ep) => window.__ms.m.pages(ep).find((p) => p.number === 3).id, EP1);
  await selectPage(P2);
  await page.locator("button", { hasText: /ページを見開きにする/ }).click();
  await page.waitForFunction(([a]) => !!window.__ms.m.spreadOf(a), [P2]);
  await msIdle();
  check(true, "ページを足し、向かいのページと見開きにする");
  // コマ枠を足す（2ページ目）
  await selectPage(P2);
  await page.keyboard.press("f");
  await page.click('[aria-label="コマ枠の操作"] [data-v="add"]');
  let q = await at(P2, 75, 60);
  await page.mouse.click(q.x, q.y);
  await page.waitForFunction((p) => window.__ms.m.panels(p).length === 1, P2);
  await msIdle();
  await page.click('[aria-label="コマ枠の操作"] [data-v="move"]');
  await selectPage(P1);
  // ナイフ（下のコマを横に分ける）
  await page.keyboard.press("c");
  q = await at(P1, 75, 165);
  await page.mouse.move(q.x - 30, q.y);
  await page.mouse.move(q.x, q.y, { steps: 4 });
  await page.waitForFunction(() => !!window.__ms.view.knifeObj);
  await page.mouse.click(q.x, q.y);
  await page.waitForFunction((p) => window.__ms.m.panels(p).length === 3, P1);
  await msIdle();
  check(true, "ナイフでコマを分ける");
  // 縦書きの文字（上のコマ）
  await page.keyboard.press("t");
  q = await at(P1, 25, 30);
  await page.mouse.click(q.x, q.y);
  await page.waitForSelector(".tx.editing");
  await page.keyboard.type("縦の文字12");
  await page.keyboard.press("Escape");
  await msIdle();
  // フキダシ（分けた上の側のコマ。しっぽ付き）
  await page.keyboard.press("s");
  q = await at(P1, 40, 130);
  await page.mouse.click(q.x, q.y);
  await page.waitForSelector(".tx.editing");
  await page.keyboard.type("フキダシ");
  await page.keyboard.press("Escape");
  await msIdle();
  const added = await model(() => window.__ms.m.rows("text_items").filter((t) => !t.removed && ["縦の文字12", "フキダシ"].includes(t.text))
    .map((t) => ({ kind: t.item_kind, dir: t.writing_direction, tail: t.tail_target_mm })));
  check(added.length === 2 && added.every((t) => t.dir === "vertical") && added.some((t) => t.kind === "balloon" && t.tail), `縦書きの文字とフキダシ（しっぽ付き）を足す ${JSON.stringify(added)}`);
  await page.keyboard.press("Escape");
  // 絵を置く（分けた下の側のコマ）
  await page.keyboard.press("v");
  const lowLower = await model((p) => window.__ms.m.panels(p).filter((x) => x.order !== 1).sort((a, b) => b.frame.polygon_mm[2][1] - a.frame.polygon_mm[2][1])[0].id, P1);
  q = await at(P1, 75, 200);
  await page.mouse.click(q.x, q.y);
  await page.waitForFunction((id) => window.__ms.sel && window.__ms.sel.id === id, lowLower);
  await page.click("details.disc > summary:has-text('絵を置く')");
  await page.setInputFiles('input[aria-label="置く絵のファイル"]', { name: "small.png", mimeType: "image/png", buffer: placePng });
  await page.waitForFunction((id) => !!window.__ms.m.find("panels", id).image_placement, lowLower, { timeout: 30000 });
  await msIdle();
  check(true, "コマに小さい絵を置く");
  await page.keyboard.press("Escape");
  // 絵を動かす（上のコマ。2回押して絵を動かす状態にし、ドラッグ）
  q = await at(P1, 20, 90);
  await page.mouse.dblclick(q.x, q.y);
  await page.waitForFunction((id) => window.__ms.imageEdit === id, TOP);
  const box0 = await model((id) => window.__ms.m.find("panels", id).image_placement.dest_box_mm, TOP);
  const q2 = await at(P1, 30, 95);
  await page.mouse.move(q.x, q.y);
  await page.mouse.down();
  await page.mouse.move(q2.x, q2.y, { steps: 6 });
  await page.mouse.up();
  await page.waitForFunction(([id, b]) => window.__ms.m.find("panels", id).image_placement.dest_box_mm[0] !== b[0], [TOP, box0]);
  await msIdle();
  await page.keyboard.press("Escape");
  check(true, "コマの絵を動かす");
  // トーン 2 枚
  await page.keyboard.press("n");
  for (const [x, y] of [[120, 140], [120, 200]]) { q = await at(P1, x, y); await page.mouse.click(q.x, q.y); await msIdle(); }
  await page.waitForFunction((p) => window.__ms.m.items(p).length === 2, P1);
  await page.keyboard.press("Escape");
  await page.keyboard.press("v");
  await page.keyboard.press("Escape");
  // 層のタブ：トーンと、コマの絵の層の順・見せる・不透明度・動かさない印
  await page.click('.itab[data-tab="layers"]');
  const toneRow = (i) => page.locator(".lrow:has(button.lname)").nth(i);
  const layerRow = (i) => page.locator(".lrow:has(span.lname)").nth(i);
  const setRange = (row, v) => row.locator('input[type="range"]').evaluate((el, v) => { el.value = String(v); el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true })); }, v);
  for (const [row, act] of [[toneRow(0), "下へ"], [toneRow(0), "隠す"], [toneRow(1), 0.4], [toneRow(1), "動かさない印"],
                            [layerRow(0), "上へ"], [layerRow(0), "隠す"], [layerRow(1), 0.5], [layerRow(1), "動かさない印"]]) {
    if (typeof act === "number") await setRange(row, act); else await row.locator(`[aria-label="${act}"]`).click();
    await msIdle();
  }
  const lay = await api("GET", `/works/${W}`);
  const tones = lay.page_items.filter((x) => x.page_id === P1);
  const pls = lay.panel_layers.filter((x) => x.panel_id === TOP && !x.removed);
  check(tones.some((t) => !t.visible) && tones.some((t) => t.fixed && t.opacity === 0.4), "トーンの見せる・不透明度・動かさない印が正本に入る");
  check(pls.some((l) => !l.visible) && pls.some((l) => l.fixed && l.opacity === 0.5)
        && pls.find((l) => l.id === seed.layers[0]).stack_order === 2, "コマの絵の層の順・見せる・不透明度・動かさない印が正本に入る");
  // ページの設定（色・解像度・ノンブル）
  await page.click('.itab[data-tab="tools"]');
  await page.click('[aria-label="ページの色"] [data-v="color"]');
  await msIdle();
  const dpi = page.locator('input[aria-label="解像度"]');
  await dpi.fill("150"); await dpi.press("Enter");
  await msIdle();
  await page.click('[aria-label="ノンブルの出し方"] [data-v="hidden"]');
  await msIdle();
  const pg1 = (await api("GET", `/works/${W}`)).pages.find((p) => p.id === P1);
  check(pg1.color_mode === "color" && pg1.dpi === 150 && pg1.nombre_display === "hidden", "ページの色・解像度・ノンブルが正本に入る");
  check(dialogs.length === 0, "保存が済んでいれば、閉じる前に聞かない");

  // 画像生成の画面：筆圧のあるペン・消しゴム・囲み
  await page.goto(`${API}/web/index.html?work=${W}&page=${P1}&panel=${TOP}`);
  await page.waitForFunction((id) => window.__wb && window.__wb.S.shownPanel === id && window.v3Stage.size, TOP, { timeout: 30000 });
  const wbIdle = () => page.waitForFunction(() => !window.__wb.Q.jobs.length && !window.__wb.Q.running && !window.__wb.Q.failed
    && !(window.__wb.S.hand && (window.__wb.S.hand.dirty || window.__wb.S.hand.uploading)), null, { timeout: 30000 });
  const st = await page.locator("#stage").boundingBox();
  const sp = (fx, fy) => [st.x + st.width * fx, st.y + st.height * fy];
  await page.click('.tool[data-tool="pen"]');
  const cdp = await ctx.newCDPSession(page);
  const pts = [[0.35, 0.45], [0.42, 0.5], [0.5, 0.52], [0.58, 0.5], [0.65, 0.46]].map(([a, b]) => sp(a, b));
  const ev = (type, [x, y], force, extra = {}) => cdp.send("Input.dispatchMouseEvent", { type, x, y, pointerType: "pen", force, button: "left", buttons: type === "mouseReleased" ? 0 : 1, ...extra });
  await ev("mouseMoved", pts[0], 0, { button: "none", buttons: 0 });
  await ev("mousePressed", pts[0], 0.2, { clickCount: 1 });
  for (let i = 1; i < pts.length; i++) await ev("mouseMoved", pts[i], 0.2 + i * 0.15);
  await ev("mouseReleased", pts.at(-1), 0, { clickCount: 1 });
  await wbIdle();
  const hand = (await api("GET", `/works/${W}`)).panel_layers.find((l) => l.panel_id === TOP && l.role === "human_hand" && !l.removed);
  const strokes = await api("GET", `/works/${W}/layers/${hand.id}/pen-strokes?points=true`);
  const pr = (strokes.strokes || strokes)[0].points.map((p) => p[2]);
  check(pr.every((v) => typeof v === "number") && new Set(pr).size > 1, `ペンの筆圧が線と一緒に残る（${pr.map((v) => v.toFixed(2)).join(",")}）`);
  await page.click('.tool[data-tool="erase"]');
  const imgBefore = (await api("GET", `/works/${W}`)).panels.find((p) => p.id === TOP).image_id;
  const e0 = sp(0.3, 0.25), e1 = sp(0.45, 0.3);
  await page.mouse.move(...e0); await page.mouse.down(); await page.mouse.move(...e1, { steps: 5 }); await page.mouse.up();
  await until(async () => (await api("GET", `/works/${W}`)).panels.find((p) => p.id === TOP).image_id !== imgBefore, "消しゴムで消した絵が正本に入る");
  await wbIdle();
  check(true, "消しゴムで消した絵が正本に入る（コマの絵が新しい版になる）");
  check(!(await beforeUnloadAsks()), "画像生成：保存が済み、囲みも無ければ閉じる前に聞かない");
  await page.click('#process-list .chip[data-process="inpaint"]');
  const m0 = sp(0.55, 0.3), m1 = sp(0.7, 0.4);
  await page.mouse.move(...m0); await page.mouse.down(); await page.mouse.move(...m1, { steps: 5 }); await page.mouse.up();
  await page.waitForFunction(() => window.v3Stage.hasMask());
  check(await beforeUnloadAsks(), "画像生成：塗った囲み（保存しない）があると、閉じる前に聞く");
  await shot("wb_mask");

  // ほかの画面：訳文・確認の状態・キーの設定・絵だけ
  const nd = dialogs.length;
  await page.goto(`${API}/web/translation/?work=${W}&episode=${EP1}&lang=en`);
  check(dialogs.length === nd + 1 && dialogs.at(-1) === "beforeunload", "囲みを残したまま画面を離れると、ブラウザが閉じる前に聞く");
  const pair = page.locator(".pair", { has: page.locator(".flag.warn") }).first();
  await pair.locator("textarea").fill("Is this the entrance?");
  await pair.locator("[data-save]").click();
  await until(async () => (await api("GET", `/works/${W}/translations?language=en`)).items?.some?.((x) => x.text === "Is this the entrance?")
    || JSON.stringify(await api("GET", `/works/${W}/translations?language=en`)).includes("Is this the entrance?"), "訳文が正本に入る");
  check(true, "訳文を入れる");
  await page.goto(`${API}/web/review/?work=${W}&episode=${EP1}&page=${P1}`);
  await page.waitForSelector('[data-move="in_review"]');
  await page.click('[data-move="in_review"]');
  await until(async () => JSON.stringify(await api("GET", `/works/${W}/review-records`)).includes("in_review"), "確認の状態が正本に入る");
  const reviewText = await until(async () => { const t = await page.innerText("#cur-status"); return t && t !== "下書き" ? t : null; }, "確認の状態の表示");
  check(true, `確認の状態を「${reviewText}」にする`);
  await page.click("#v3-keys");
  await page.waitForSelector("#v3-keys[open]");
  await page.click("#v3-keys tr[data-id='workbench.pen'] [data-add]");
  await page.keyboard.press("k");
  await until(async () => JSON.stringify((await api("GET", "/me/settings")).other?.keymap?.["workbench.pen"]) === '["b","k"]', "キーの設定が利用者の設定に入る");
  await page.keyboard.press("Escape");
  check(true, "キーの設定（ペンに K を足す）");

  // ================================================================ 2. 写し（正本と画面）
  const REVIEW_KEYS = ["unit_id", "status", "step", "attempt", "candidates", "stop_reason"];
  async function canonical() {
    const work = await api("GET", `/works/${W}`);
    const hl = work.panel_layers.find((l) => l.role === "human_hand" && !l.removed);
    const hs = await api("GET", `/works/${W}/harness/snapshot`);
    const unit = hs.units.find((u) => u.stage_run_id === seed.stageRun);
    // GET /works/{id} の表の行の並びは決まっていない（ORDER BY が無い。再起動の後に変わる）。id で並べてから比べる
    for (const [k, v] of Object.entries(work)) if (Array.isArray(v)) work[k] = [...v].sort((a, b) => String(a.id).localeCompare(String(b.id)));
    return {
      work, strokes: await api("GET", `/works/${W}/layers/${hl.id}/pen-strokes?points=true`),
      translations: await api("GET", `/works/${W}/translations?language=en`),
      reviews: await api("GET", `/works/${W}/review-records`),
      keymap: (await api("GET", "/me/settings")).other?.keymap,
      held: await api("GET", `/works/${W}/held-changes`),
      harness: { unit: Object.fromEntries(REVIEW_KEYS.map((k) => [k, unit[k]])),
                 stage: (({ id, status, stop_reason }) => ({ id, status, stop_reason }))(hs.stage_runs.find((r) => r.id === seed.stageRun)) },
      events: (await api("GET", `/works/${W}/events?limit=1000`)).map((e) => `${e.seq}:${e.id}:${e.op_type}:${e.undoes_event_id || ""}`),
    };
  }
  // 項目ごとに比べる。変わってよい項目は理由と一緒に返す
  const EXPECTED = { "work.work.head_seq": "取り消しの確かめで、ノンブルの出し方を変えて取り消す出来事が2つ増える",
                     events: "同じ理由で出来事が後ろに足される（前の出来事は1つも変わらない・消えないことを別に確かめる）" };
  function diff(a, b, p = "", out = []) {
    if (EXPECTED[p]) return out;
    if (typeof a !== typeof b || Array.isArray(a) !== Array.isArray(b) || a === null || b === null || typeof a !== "object") {
      if (JSON.stringify(a) !== JSON.stringify(b)) out.push(`${p}: ${JSON.stringify(a)?.slice(0, 120)} → ${JSON.stringify(b)?.slice(0, 120)}`);
      return out;
    }
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) diff(a[k], b[k], p ? `${p}.${k}` : k, out);
    return out;
  }
  async function screens(tag) {
    await openManuscript(P1);
    const ms = await stableShot(page.locator(".canvas-container").first(), `${tag}_manuscript`);
    await page.click('.itab[data-tab="layers"]');
    const layersDom = await page.locator(".lrow").evaluateAll((rs) => rs.map((r) => [r.textContent.trim(), ...[...r.querySelectorAll("[aria-label],[aria-pressed]")].map((b) => `${b.getAttribute("aria-label")}=${b.getAttribute("aria-pressed") ?? ""}`), ...[...r.querySelectorAll("input")].map((i) => i.value)].join("|")));
    await page.goto(`${API}/web/index.html?work=${W}&page=${P1}&panel=${TOP}`);
    await page.waitForFunction((id) => window.__wb && window.__wb.S.shownPanel === id && window.v3Stage.size, TOP, { timeout: 30000 });
    const wb = await stableShot(page.locator("#stage"), `${tag}_workbench`);
    await page.goto(`${API}/web/translation/?work=${W}&episode=${EP1}&lang=en`);
    const tr = await until(async () => { const v = await page.locator(".pair textarea").evaluateAll((ts) => ts.map((t) => t.value)); return v.length ? v : null; }, "訳文の画面");
    await page.goto(`${API}/web/review/?work=${W}&episode=${EP1}&page=${P1}`);
    const rv = await until(async () => { const t = await page.innerText("#cur-status").catch(() => ""); return t || null; }, "確認の画面");
    await page.goto(`${API}/web/harness/?work=${W}`);
    await page.waitForSelector("#conn.conn-live", { timeout: 30000 });
    const hz = await page.locator('.pchip[data-status="awaiting_review"]').count();
    return { ms, wb, dom: { layersDom, tr, rv, harnessAwaiting: hz > 0 } };
  }
  async function shot(name) { if (SHOTS) save(`${name}.png`, await page.screenshot()); }

  // 写しは、開き直した画面で取る（場面 a の前の基準）
  const base = await canonical();
  const baseScreens = await screens("0_base");
  check(baseScreens.dom.harnessAwaiting, "基準：工程の画面に確認待ちの作業が出る");
  writeFileSync(`${PE_DIR}/base_canonical.json`, JSON.stringify(base, null, 1));

  async function compare(name) {
    const now = await canonical();
    const d = diff(base, now);
    const evOk = base.events.every((e, i) => now.events[i] === e);
    const sc = await screens(name);
    const msd = await pixelDiff(baseScreens.ms, sc.ms), wbd = await pixelDiff(baseScreens.wb, sc.wb);
    const domSame = JSON.stringify(sc.dom) === JSON.stringify(baseScreens.dom);
    const r = { fields_diff: d, events_kept: evOk, new_events: now.events.slice(base.events.length), manuscript_pixels: msd, workbench_pixels: wbd, dom_same: domSame };
    results.scenarios[name] = { ...(results.scenarios[name] || {}), ...r };
    log(name, JSON.stringify({ ...r, new_events: r.new_events.length }));
    check(d.length === 0, `${name}：正本は写しと項目ごとに同じ（違い ${d.length}：${d.slice(0, 5).join(" / ")}）`);
    check(evOk, `${name}：前の出来事は1つも変わらず消えない`);
    // 違ってよいのは全体の 0.01% まで（画像生成の画面は、開き直すたびに 1〜2 画素違うことがあった。場所と原因は未検証）
    const fewPx = (r) => r.diff >= 0 && r.diff <= r.total * 0.0001;
    check(fewPx(msd) && fewPx(wbd), `${name}：原稿と画像生成の画面の画素が同じ（違う画素 ${msd.diff}・${wbd.diff}）`);
    check(domSame, `${name}：層のタブ・訳文・確認・工程の画面の中身が同じ ${domSame ? "" : JSON.stringify(sc.dom)}`);
    const items = await api("GET", `/works/${W}/harness/review-items`);
    check(JSON.stringify(items).includes(base.harness.unit.unit_id), `${name}：ハーネスの作業はまだ確認待ちで、確認の一覧に出る（承認できる）`);
  }

  // 取り消しの確かめ：場面の前に原稿の画面で解像度を変え、場面の後に（開き直さずに）Ctrl+Z で戻す。ページごとの取り消しが場面をまたいで効くか
  // 印にする変更はノンブルの出し方（隠しノンブル → 見せる）。解像度は見開きの組でそろえる値なので使わない
  const nombreOf = async () => (await api("GET", `/works/${W}`)).pages.find((p) => p.id === P1).nombre_display;
  async function markEdit() {
    await openManuscript(P1);
    await page.click('.itab[data-tab="tools"]');
    await page.click('[aria-label="ノンブルの出し方"] [data-v="visible"]');
    await msIdle();
    check(await nombreOf() === "visible", "取り消しの確かめ：ノンブルを「見せる」にする");
  }
  async function undoMark(name) {
    await page.evaluate(() => document.activeElement && document.activeElement.blur());
    await page.keyboard.press("Control+z");
    await until(async () => await nombreOf() === "hidden", `${name}：Ctrl+Z でノンブルが「隠しノンブル」に戻る`, 30000);
    await msIdle();
    check(true, `${name}：再起動の後も、開き直さずに Ctrl+Z でこのページの変更を取り消せる`);
  }

  // ================================================================ 3. 場面
  // a. ブラウザで開き直す
  await openManuscript(P1);
  await page.keyboard.press("Shift+F");
  await page.waitForFunction(() => document.documentElement.hasAttribute("data-focus"));
  await page.reload();
  await page.waitForFunction(() => window.__ms && window.__ms.m);
  check(await S(() => document.documentElement.hasAttribute("data-focus")), "a：絵だけ（localStorage）は開き直しても残る");
  await page.keyboard.press("Shift+F");
  await page.waitForFunction(() => !document.documentElement.hasAttribute("data-focus"));
  await msIdle();
  check(await S(() => !window.__ms.saver.histOf(window.__ms.pageId).undo.length), "a：開き直すと、ページごとの取り消しの記録は無くなる（記録はブラウザのメモリだけ。設計の限り）");
  await compare("a_reload");

  // b. 口のサーバーを止めて起こす
  await markEdit();
  stack("stop", "api"); stack("start", "api"); await ready();
  await undoMark("b");
  await compare("b_api_restart");
  // b2. 口のサーバーが止まっている間の変更：保存できず、閉じる前に聞く。閉じると消える。起こして送り直すと入る
  await openManuscript(P1);
  await page.click('.itab[data-tab="tools"]');
  stack("stop", "api");
  let i = page.locator('input[aria-label="解像度"]');
  await i.fill("152"); await i.press("Enter");
  await page.waitForFunction(() => !!window.__ms.saver.failed);
  check(await beforeUnloadAsks(), "b2：保存できない変更があると、閉じる前に聞く");
  check((await page.innerText("#stage-msg")).includes("保存できませんでした"), "b2：保存できなかったことと「もう一度送る」を出す");
  await shot("b2_save_failed");
  const nd2 = dialogs.length;
  await page.reload().catch(() => {});
  check(dialogs.length === nd2 + 1, "b2：そのまま開き直すと、ブラウザが閉じる前に聞く");
  stack("start", "api"); await ready();
  await openManuscript(P1);
  check((await api("GET", `/works/${W}`)).pages.find((p) => p.id === P1).dpi === 150, "b2：聞かれても閉じると、送れなかった変更は消える（待ち行列はブラウザのメモリだけ）");
  await page.click('.itab[data-tab="tools"]');
  stack("stop", "api");
  i = page.locator('input[aria-label="解像度"]');
  await i.fill("153"); await i.press("Enter");
  await page.waitForFunction(() => !!window.__ms.saver.failed);
  stack("start", "api"); await ready();
  await page.click("#stage-msg button:has-text('もう一度送る')");
  await msIdle();
  check((await api("GET", `/works/${W}`)).pages.find((p) => p.id === P1).dpi === 153, "b2：口が戻ってから「もう一度送る」で入る");
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.keyboard.press("Control+z");
  await until(async () => (await api("GET", `/works/${W}`)).pages.find((p) => p.id === P1).dpi === 150, "b2：送り直した変更も取り消せる");
  await msIdle();
  // b3. 2つの操作の変更（層の順の入れ替え）が1つ目だけ通って止まったとき、送り直しで1つ目を2回送らない
  await page.click('.itab[data-tab="layers"]');
  const orders = async () => (await api("GET", `/works/${W}`)).panel_layers.filter((l) => l.panel_id === TOP && !l.removed).map((l) => `${l.id}:${l.stack_order}:${l.fixed}`).sort().join(",");
  const order0 = await orders();
  // 層の1つには動かさない印があり、それを含む入れ替えはサーバーが断る。先に印を外し（後で取り消して戻す）、その層を入れ替える
  const fixedAt = await model((id) => window.__ms.m.layers(id).findIndex((l) => l.fixed), TOP);
  await page.locator(".lrow:has(span.lname)").nth(fixedAt).locator('[aria-label="動かさない印"]').click();
  await msIdle();
  const order1 = await orders();
  const evN = (await api("GET", `/works/${W}/events?limit=1000`)).length;
  let opsSeen = 0;
  await page.route(`**/works/${W}/ops`, (route) => { opsSeen += 1; return opsSeen === 2 ? route.abort("connectionreset") : route.continue(); });
  await page.locator(".lrow:has(span.lname)").nth(fixedAt).locator(`[aria-label="${fixedAt ? "下へ" : "上へ"}"]`).click();
  await page.waitForFunction(() => !!window.__ms.saver.failed);
  await page.unroute(`**/works/${W}/ops`);
  await page.click("#stage-msg button:has-text('もう一度送る')");
  await msIdle();
  const evAdded = (await api("GET", `/works/${W}/events?limit=1000`)).length - evN;
  check(evAdded === 2, `b3：途中で止まった2つの操作を送り直しても、出来事は2つだけ（${evAdded}）`);
  check(await orders() !== order1, "b3：送り直すと2つの層の順が入れ替わる");
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.keyboard.press("Control+z");
  await until(async () => (await orders()) === order1, "b3：Ctrl+Z 1回で順が両方戻る");
  await msIdle();
  await page.keyboard.press("Control+z");
  await until(async () => (await orders()) === order0, "b3：もう1回の Ctrl+Z で動かさない印も戻る");
  await msIdle();
  check(true, "b3：送り直した2つの操作を Ctrl+Z 1回で両方戻せる");
  EXPECTED.events = EXPECTED.events + "（b2・b3 の送り直しと取り消しの出来事も足される）";
  await compare("b2_saves_while_down");

  // c. 作業者を止めて起こす：ハーネスの作業の途中と、書き出しの途中
  await markEdit();
  const st3 = await api("POST", `/works/${W}/harness/stages`, { episode_id: EP3, stage: "S4", limits: seed.limits, spec: { drawing: seed.drawing } });
  await until(async () => ["running"].includes((await harnessUnit(st3.stage_run_id))?.status) && (await harnessUnit(st3.stage_run_id)).step !== null, "話3の作業が動き出す");
  // 見開きの組（1–2 ページ）を書き出す。1 ページは 150dpi（画面で入れた値）で、止めるまでの間がある
  const exp = await api("POST", `/works/${W}/exports`, { format: "png", page_ids: [P1, P2], spread_output: "split" });
  await until(async () => {
    const r = await api("GET", `/works/${W}/exports/${exp.id}`);
    if (r.status === "failed" || r.status === "done") throw new Error(`書き出しが止める前に ${r.status} になった ${r.detail || ""}`);
    return r.status === "running";
  }, "書き出しが動き出す");
  const midUnit = await harnessUnit(st3.stage_run_id);
  stack("stop", "workers", "KILL");
  results.scenarios.c_workers = { stopped_while: { unit: { status: midUnit.status, step: midUnit.step }, export: "running" } };
  stack("start", "workers"); await ready();
  await undoMark("c");
  const done = await until(async () => { const r = await api("GET", `/works/${W}/exports/${exp.id}`); return ["done", "failed"].includes(r.status) ? r : null; }, "書き出しが終わる", 240000);
  check(done.status === "done", `c：作業者を止めても、書き出しはやり直して終わる（${done.status} ${done.detail || ""}）`);
  const files = readdirSync(`${PE_DIR}/exports`, { recursive: true }).filter((f) => f.includes(exp.id) && statSync(`${PE_DIR}/exports/${f}`).isFile());
  const outFiles = done.outputs.map((o) => o.file);
  check(outFiles.length >= 1 && new Set(outFiles).size === outFiles.length && files.length === outFiles.length,
        `c：書き出しは1回分だけ（出力 ${outFiles.length}・重なり無し・置き場のファイル ${files.length}）`);
  results.scenarios.c_workers.export = { status: done.status, outputs: done.outputs.length, files };
  const u3 = await until(async () => { const u = await harnessUnit(st3.stage_run_id); return ["awaiting_review", "failed", "stopped"].includes(u.status) ? u : null; }, "話3の作業が止まらずに進む", 120000);
  results.scenarios.c_workers.unit_after = { status: u3.status, step: u3.step, attempt: u3.attempt, stop_reason: u3.stop_reason };
  check(u3.status === "awaiting_review", `c：作業者を止めても、ハーネスの作業はやり直して確認待ちになる（${u3.status}・${u3.attempt} 回目 ${u3.stop_reason || ""}）`);
  await compare("c_workers");

  // d. 既製品（PostgreSQL・Temporal・OpenFGA）を docker compose restart
  await markEdit();
  stack("restart-infra"); await ready();
  await undoMark("d");
  await compare("d_infra_restart");

  // e. compose down（ボリュームは残す）と up
  await markEdit();
  stack("down"); stack("up"); await ready();
  await undoMark("e");
  await compare("e_down_up");
  check((await api("GET", `/works/${W}/exports/${exp.id}`)).status === "done", "e：書き出しの記録は残る");

  // 最後に、確認待ちの作業を承認できる
  const items = await api("GET", `/works/${W}/harness/review-items`);
  const it = JSON.stringify(items);
  const candId = items.items.find((x) => x.unit_id === base.harness.unit.unit_id)?.review?.picked;
  check(!!candId, `確認の一覧から候補を取れる ${it.slice(0, 200)}`);
  await api("POST", `/works/${W}/harness/units/${base.harness.unit.unit_id}/review`, { action: "approve", candidate_id: candId });
  const fin = await until(async () => { const u = await harnessUnit(seed.stageRun); return u.status !== "awaiting_review" ? u : null; }, "承認が通る");
  check(fin.status !== "failed", `再起動を全部通った後でも、確認待ちの作業を承認できる（${fin.status}）`);
  check(!errors.length, `画面の JS の失敗が無い ${errors.slice(0, 3).join(" / ")}`);
  results.ok = true;
} catch (e) {
  results.ok = false;
  results.error = String(e.stack || e);
  console.error(e);
  try { save("failure.png", await page.screenshot()); } catch { /* */ }
} finally {
  results.seconds = Math.round((Date.now() - t0) / 1000);
  results.errors = errors;
  writeFileSync(`${PE_DIR}/results.json`, JSON.stringify(results, null, 1));
  await browser.close();
  log(results.ok ? "全部通った" : "失敗", `${PE_DIR}/results.json`);
  process.exit(results.ok ? 0 : 1);
}
