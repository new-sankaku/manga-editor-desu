// AIハーネスの画面を Playwright で通し、7つの状態の画面の写しと、変化が画面に出るまでの遅れを取る。
// 先に動く見本を起こす（ComfyUI・LLM・検出器は偽物）：
//   (cd v3/server && uv run python tests/integration/harness_screen_demo.py --port 8790)
// そのあと：
//   CTRL=http://127.0.0.1:8791 SHOTS=v3/web/harness/screenshots \
//   NODE_PATH=/opt/node22/lib/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node v3/web/test/harness_ui.mjs
import { createRequire } from "node:module";
import { mkdirSync, statSync, writeFileSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const CTRL = process.env.CTRL;
const SHOTS = process.env.SHOTS;
if (!CTRL || !SHOTS) throw new Error("CTRL・SHOTS を決めてください");
mkdirSync(SHOTS, { recursive: true });

const info = await (await fetch(`${CTRL}/info`)).json();
const API = new URL(info.web).origin;
const ctrl = (path, body) => fetch(`${CTRL}${path}`, { method: "POST", headers: { "Content-Type": "application/json" },
                                                     body: JSON.stringify(body ?? {}) }).then((r) => r.json());
const api = async (method, path, body) => {
  const r = await fetch(`${API}${path}`, { method, headers: { "X-V3-User": info.user, "X-V3-Request": "1",
                                                              "Content-Type": "application/json" },
                                           body: body === undefined ? undefined : JSON.stringify(body) });
  const t = await r.text();
  return { status: r.status, body: t ? JSON.parse(t) : null };
};
const snapshot = async () => (await api("GET", `/works/${info.wid}/harness/snapshot`)).body;

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
await page.addInitScript((u) => localStorage.setItem("v3.user", u), info.user);

const results = { shots: [], checks: [], latency: {} };
async function shot(name, what, opts = {}) {
  const path = `${SHOTS}/${name}.png`;
  await page.screenshot({ path, ...opts });
  const size = statSync(path).size;
  results.shots.push({ path, what, bytes: size });
  console.log("shot", path, size);
  if (size >= 1024 * 1024) throw new Error(`${path} が 1MB を超えた`);
}
function check(cond, msg) { if (!cond) throw new Error(`確かめ失敗: ${msg}`); results.checks.push(msg); console.log("ok", msg); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  await page.goto(info.web);
  await page.waitForSelector("#conn.conn-live");
  check(true, "SSE につながると「受信中」になる");

  // ---------------------------------------------------------------- 1. 工程の図：作業がいくつも動いている
  await ctrl("/knob", { comfy_steps: 10, comfy_step_seconds: 0.35 });
  const started = await ctrl("/start", { max_parallel_units: 4 });
  check(started.status === 201, "S4 を始められる");
  await page.waitForFunction(() => document.querySelectorAll('.pchip[data-status="running"]').length >= 3, null, { timeout: 30000 });
  await page.waitForSelector(".hz-progress.stage .hz-bar span", { timeout: 30000 });
  await sleep(700);
  check(await page.locator('.pchip[data-status="queued"]').count() >= 1, "同時に回す数（4）を超えた作業は順番待ち");
  await shot("01_stage_view_running", "工程の図。S4 の下に7つの作業、4つが実行中（ComfyUI の段数の細い棒つき）、残りは順番待ち");

  // ---------------------------------------------------------------- 1b. 工程の図：ページごとにたたむ・開く
  await page.click("#fold");
  await sleep(300);
  const folded = await page.evaluate(() => window.__harness.graphNodes("node.group.collapsed"));
  check(folded.length === 2 && folded.every((d) => /（[34]）/.test(d.label)), "ページごとにたたむと、ページのまとまり2つが作業の数と内訳のノードになる");
  check((await page.evaluate(() => window.__harness.graphNodes('node[kind="unit"]'))).length === 0, "たたむと作業のノードは見えない");
  await shot("08_stage_folded", "工程の図。S4 の作業をページごとにたたんだところ（p1 4つ・p2 3つ。状態の内訳と、一番急ぐ状態の色）");
  await page.click("#unfold");
  await sleep(300);
  check((await page.evaluate(() => window.__harness.graphNodes('node[kind="unit"]'))).length === 7, "全部開くと作業のノード7つに戻る");

  // ---------------------------------------------------------------- 3. 生成のノード：ComfyUI の段数と途中の絵
  const genUnit = await page.evaluate(() => document.querySelector(".hz-progress.stage").dataset.pnode.slice(5));
  await page.click(`.pchip[data-unit="${genUnit}"]`);
  await page.waitForSelector(".hz-progress.unit .hz-previews img", { timeout: 30000 });
  await page.waitForFunction(() => [...document.querySelectorAll(".hz-progress.unit em")].some((e) => /\s[4-9]\/10|\s10\/10/.test(e.textContent)), null, { timeout: 30000 });
  check(true, "生成のノードに候補ごとの段数と途中の絵が出る");
  await shot("03_generate_progress_preview", "作業の図。生成のノードの下に候補ごとの ComfyUI の段数（n/10）と途中の絵、下に時間の列");

  // ---------------------------------------------------------------- 3b. 作業の図：生成の段を開く（送り先ごとの子）
  await page.evaluate(() => window.__harness.toggleStep("generate"));
  await page.waitForFunction(() => window.__harness.graphNodes('node[kind="part"]').length >= 1, null, { timeout: 10000 });
  const parts = await page.evaluate(() => window.__harness.graphNodes('node[kind="part"]').map((d) => d.label));
  check(parts.every((l) => /依頼 \d/.test(l)), `生成の段を開くと送り先ごとの子が出る（${parts.join(" / ").replace(/\n/g, " ")}）`);
  await sleep(300);
  await shot("09_unit_generate_open", "作業の図。生成の段を開いたところ（送り先ごとの依頼の数）");
  await page.evaluate(() => window.__harness.toggleStep("generate"));
  await sleep(200);
  check((await page.evaluate(() => window.__harness.graphNodes('node[kind="part"]'))).length === 0, "もう一度押すとたたむ");

  // ---------------------------------------------------------------- 4. 人の判断待ち：判断のパネル
  await page.click("#tab-stage");
  await page.waitForSelector('.pchip[data-status="awaiting_review"]', { timeout: 60000 });
  const reviewUnit = await page.getAttribute('.pchip[data-status="awaiting_review"]', "data-unit");
  await page.click(`.pchip[data-unit="${reviewUnit}"]`);
  await page.waitForSelector(".review-box .cand img[src]", { timeout: 15000 });
  await sleep(400);
  check(await page.locator(".review-box .cand").count() === 2, "判断のパネルに候補が2枚出る");
  await shot("04_review_panel", "人の判断待ち。人の判断のノードが脈打ち、横のパネルに候補（検査の指摘・評価役の選択）と採用・却下・直した絵");

  // ---------------------------------------------------------------- 2. 作業の図：戻りの辺を印が動く（却下→文脈）
  await page.fill("#reject-reason", "表情が硬い。もう少し柔らかく");
  const t0 = Date.now();
  await page.click("text=却下して止める");
  // 却下は止まるだけ（決めごと 5.3）。止まったのを見てから再開を押すと、理由を入れて作り直す
  await page.waitForSelector(`.pchip[data-unit="${reviewUnit}"][data-status="stopped"]`, { timeout: 15000 });
  check(true, "却下すると止まる（すぐには作り直さない）");
  // 止まった理由の文にも「再開」が入るので、ボタンを名前で選ぶ
  await page.getByRole("button", { name: "再開", exact: true }).first().click();
  await page.waitForFunction(() => window.__harness.lastTraversal && window.__harness.lastTraversal.retry, null, { timeout: 15000 });
  const opToScreen = Date.now() - t0;
  await sleep(450);
  const trav = await page.evaluate(() => window.__harness.lastTraversal);
  check(trav.from === "review" && trav.to === "context", "却下して再開すると 人の判断→文脈 の戻りの辺を印が動く");
  await shot("02_unit_retry_marker", "作業の図。却下で 人の判断→文脈 の戻りの辺（破線）を印が動いている途中。辺に「却下（理由つき） ×1」");
  results.latency.reject_click_to_marker_ms = opToScreen;

  // ---------------------------------------------------------------- 5. 取り消し中・止めた・古い
  await page.click("#tab-stage");
  let snap = await snapshot();
  const others = snap.units.filter((u) => u.unit_id !== reviewUnit);
  const staleTarget = snap.units.find((u) => u.status === "awaiting_review" && u.unit_id !== reviewUnit)
    || snap.units.find((u) => u.status === "done") || others.find((u) => u.status === "running");
  const idx = info.pids.indexOf(staleTarget.target_id);
  await ctrl(`/upstream/${idx}`);
  await page.waitForSelector(`.pchip.stale[data-unit="${staleTarget.unit_id}"]`, { timeout: 15000 });
  check(true, "上流（コマの中身）を変えると、その作業に「古い」が付く（自動では作り直さない）");
  snap = await snapshot();
  const live = snap.units.filter((u) => u.status === "running" && u.unit_id !== staleTarget.unit_id);
  const pauseU = live.find((u) => u.step === "generate") || live[0];
  let r = await api("POST", `/works/${info.wid}/harness/units/${pauseU.unit_id}/control`, { action: "pause", mode: "now" });
  check(r.status === 200, "今すぐ止めるを送れる");
  await page.waitForSelector(`.pchip[data-unit="${pauseU.unit_id}"][data-status="paused"]`, { timeout: 15000 });
  snap = await snapshot();
  const cancelU = snap.units.find((u) => u.status === "running" && ![pauseU.unit_id, staleTarget.unit_id].includes(u.unit_id));
  await ctrl("/knob", { detector_sleep: 3, llm_sleep: 3 });
  r = await api("POST", `/works/${info.wid}/harness/units/${cancelU.unit_id}/control`, { action: "cancel_unit" });
  check(r.status === 200, `作業を取り消すを送れる ${JSON.stringify(r.body)}`);
  await page.waitForSelector(`.pchip[data-unit="${cancelU.unit_id}"][data-status="cancelling"]`, { timeout: 10000 });
  await shot("05_cancelling_paused_stale", "工程の図。取り消し中（赤の破線）・止めた（青灰）・上流が変わった（紫の下地）が同時に出ている");
  await ctrl("/knob", { detector_sleep: 0.4, llm_sleep: 0.6 });

  // ---------------------------------------------------------------- 7. ページとコマの表
  await page.waitForSelector(`.pchip[data-unit="${cancelU.unit_id}"][data-status="cancelled"]`, { timeout: 30000 });
  await page.locator(".table-box").scrollIntoViewIfNeeded();
  await shot("07_page_panel_table", "ページとコマの表。コマごとの状態・何回目/上限・古い印、ページごとのまとめ", { fullPage: true });

  // ---------------------------------------------------------------- 6. 切断中 → つなぎ直して snapshot を取り直す
  await page.evaluate(() => window.scrollTo(0, 0));
  await ctrl("/down");  // API のサーバーを止める（SSE が切れる）
  await page.waitForSelector("#conn.conn-disconnected", { timeout: 15000 });
  await sleep(600);
  await shot("06_disconnected", "切断中。上の帯と図の斜線で受け取れていないことを示し、つなぎ直しを待っている");
  const off = Date.now();
  await ctrl("/up");
  // 画面がつなぎ直す前に状態を変える（つなぎ直したときに snapshot で取り直せるか）
  r = await api("POST", `/works/${info.wid}/harness/units/${pauseU.unit_id}/control`, { action: "resume" });
  check(r.status === 200, "画面がつなぎ直す前に、画面の外から再開を送る");
  await page.waitForSelector("#conn.conn-live", { timeout: 20000 });
  results.latency.reconnect_ms = Date.now() - off;
  await page.waitForFunction((id) => {
    const el = document.querySelector(`.pchip[data-unit="${id}"]`);
    return el && el.dataset.status !== "paused";
  }, pauseU.unit_id, { timeout: 15000 });
  check(true, "つなぎ直すと snapshot を取り直し、切れている間の変化（再開）が画面に出る");

  // ---------------------------------------------------------------- 遅れ（正本に出来事を書いた時刻 → 画面に当て終えた時刻）
  await sleep(4000);
  const lat = await page.evaluate(() => window.__harness.latencies);
  const by = {};
  for (const l of lat) (by[l.kind] ||= []).push(l.ms);
  const q = (xs, p) => xs.sort((a, b) => a - b)[Math.min(xs.length - 1, Math.floor(p * xs.length))];
  for (const [k, xs] of Object.entries(by)) results.latency[k] = { n: xs.length, p50: q(xs, 0.5), p95: q(xs, 0.95), max: Math.max(...xs) };
  const all = lat.map((l) => l.ms);
  results.latency.all = { n: all.length, p50: q(all, 0.5), p95: q(all, 0.95), max: Math.max(...all) };
  // サーバーを止めている間の読み込みの失敗は数えない（わざと切った）
  const real = errors.filter((e) => !/Failed to load resource|ERR_CONNECTION_REFUSED|Failed to fetch/.test(e));
  check(real.length === 0, `画面のエラーが無い ${real.join(" / ")}`);
} catch (e) {
  await page.screenshot({ path: `${SHOTS}/failed.png` });
  console.error(e, errors);
  process.exitCode = 1;
} finally {
  if (process.env.RESULT) writeFileSync(process.env.RESULT, JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results.latency, null, 2));
  await browser.close();
}
