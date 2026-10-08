// 画像生成の画面を Playwright で通す。サーバー（/web を出す）と ComfyUI と作業者が動いていること。
// 使い方：
//   V3_WEB=http://127.0.0.1:8765/web/ V3_USER=ui-author SHOTS=/tmp/shots \
//   NODE_PATH=/opt/node22/lib/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node v3/web/test/image_generation_ui.mjs
// 作品・ページ・コマは、その利用者が見てよい最初の物を使う（コマには絵と人の手の範囲が要る）。
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const WEB = process.env.V3_WEB;
const USER = process.env.V3_USER;
const SHOTS = process.env.SHOTS;
if (!WEB || !USER || !SHOTS) throw new Error("V3_WEB・V3_USER・SHOTS を決めてください");
mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
await page.addInitScript((u) => localStorage.setItem("v3.user", u), USER);

let n = 0;
async function shot(name) {
  n += 1;
  const path = `${SHOTS}/${String(n).padStart(2, "0")}_${name}.png`;
  await page.screenshot({ path });
  console.log("shot", path);
}
function check(cond, msg) { if (!cond) throw new Error(`確かめ失敗: ${msg}`); console.log("ok", msg); }

// 絵の画素 (x, y) の画面の位置
async function at(x, y) {
  return page.evaluate(([x, y]) => {
    const s = window.v3Stage;
    const v = s.c.viewportTransform;
    const r = s.c.upperCanvasEl.getBoundingClientRect();
    return { x: r.left + x * v[0] + v[4], y: r.top + y * v[3] + v[5] };
  }, [x, y]);
}
async function drag(points) {
  const p0 = await at(...points[0]);
  await page.mouse.move(p0.x, p0.y);
  await page.mouse.down();
  for (const pt of points.slice(1)) { const p = await at(...pt); await page.mouse.move(p.x, p.y, { steps: 6 }); }
  await page.mouse.up();
}
const imgCount = () => page.locator(".cand[data-image]").count();

await page.goto(WEB);
try {
await page.waitForSelector("#process-list .chip");
await page.waitForFunction(() => window.v3Stage.size !== null);
await shot("start");

// ---- 囲んで直す：筆で塗る（人の手の範囲にもかかるように）
await page.click('#process-list .chip[data-process="inpaint"]');
check(await page.locator('.tool[data-tool="mask"]').getAttribute("aria-pressed") === "true", "囲んで直すを選ぶと囲む道具になる");
await page.fill("#brush-size", "30");
await page.dispatchEvent("#brush-size", "input");
await drag([[60, 120], [150, 140], [230, 150], [260, 120]]);
const protectedClean = await page.evaluate(() => {
  const s = window.v3Stage;
  const d = s.maskCanvas.getContext("2d").getImageData(130, 130, 40, 60).data;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return false;
  return true;
});
check(protectedClean, "人の手の範囲は塗れない（マスクに残らない）");
check(await page.evaluate(() => window.v3Stage.hasMask()), "塗った所がマスクに入る");
await page.fill('[data-name="prompt"]', "a red flower");
await page.click('#count button[data-n="2"]');
await shot("inpaint_mask");

// 多角形を足して、反転・戻すを試す
await page.click('#mask-tools button[data-mask="polygon"]');
for (const [x, y] of [[20, 20], [80, 20], [60, 70]]) { const p = await at(x, y); await page.mouse.click(p.x, p.y); }
const first = await at(20, 20);
await page.mouse.click(first.x, first.y);
const polyOn = await page.evaluate(() => window.v3Stage.maskCanvas.getContext("2d").getImageData(50, 30, 1, 1).data[3]);
check(polyOn > 0, "多角形で囲んだ所が塗られる");
await page.click("#undo");
const polyOff = await page.evaluate(() => window.v3Stage.maskCanvas.getContext("2d").getImageData(50, 30, 1, 1).data[3]);
check(polyOff === 0, "取り消すで多角形の前に戻る（囲みもコマの取り消しの記録に入る）");

await page.click("#generate");
await page.waitForSelector('.itab[data-tab="cands"][aria-selected="true"]');
await page.waitForSelector(".cand.wait");
await shot("inpaint_progress");
await page.waitForFunction(() => document.querySelectorAll(".cand[data-image]").length >= 2, null, { timeout: 600000 });
await page.waitForTimeout(800);
await shot("inpaint_candidates");
const meta = await page.locator(".cand[data-image] .cand-f .meta").first().textContent();
check(/seed \d+/.test(meta) && meta.includes("sd15_unet"), `候補につなぎ先・モデル・seed が出る（${meta}）`);
check(await page.locator(".cand[data-image] .prot").count() >= 1, "候補に人の手の範囲の印が出る");

// ---- 比べる
await page.locator(".cand[data-image] .th").first().click();
await page.locator("#sets .set .row .btn").first().click();
await page.waitForSelector("#compare:not([hidden]) figure img");
await page.waitForTimeout(300);
await shot("compare_side");
await page.click('#compare-mode button[data-mode="slider"]');
await page.waitForSelector(".slider-wrap");
await page.fill(".slider-wrap input", "30");
await page.dispatchEvent(".slider-wrap input", "input");
await shot("compare_slider");
await page.click("#compare-close");

// ---- 採用 → 取り消す → やり直す
const firstCand = page.locator(".cand[data-image]").first();
const candId = await firstCand.getAttribute("data-image");
await firstCand.locator(".btn.primary").click();
await page.waitForSelector(`.cand[data-image="${candId}"] .flag.on`);
check(true, "採用すると「採用中」になる");
await page.waitForTimeout(1500);
check(await page.evaluate(() => window.v3Stage.hasMask()), "採用しても、同じ大きさの絵なら囲んだ範囲は残る");
await page.click('.itab[data-tab="versions"]');
await page.waitForSelector(`.vrow.cur[data-version="${candId}"]`);
await shot("versions_after_adopt");
await page.click("#undo");
await page.waitForFunction((id) => !document.querySelector(`.vrow.cur[data-version="${id}"]`), candId);
check(true, "取り消すと前の絵に戻る");
await page.click("#redo");
await page.waitForSelector(`.vrow.cur[data-version="${candId}"]`);
check(true, "やり直すと採用した絵に戻る");

// ---- 版：見る・戻す
const old = page.locator(".vrow:not(.cur)").first();
const oldId = await old.getAttribute("data-version");
await old.locator(".btn", { hasText: "見る" }).click();
await page.waitForSelector("#viewing:not([hidden])");
await shot("version_viewing");
await page.click("#viewing-back");
await old.locator(".btn", { hasText: "戻す" }).click();
await page.waitForSelector(`.vrow.cur[data-version="${oldId}"]`);
check(true, "版の「戻す」でコマの絵がその版になる");

// ---- 却下
await page.click('.itab[data-tab="cands"]');
const second = page.locator(".cand[data-image]").nth(1);
const secondId = await second.getAttribute("data-image");
await second.locator(".btn", { hasText: "却下" }).click();
await page.waitForSelector(`.cand.discarded[data-image="${secondId}"]`);
check(true, "却下すると印が付く");

// ---- 描き足す：枠の右の辺を動かす
await page.click('.itab[data-tab="ask"]');
await page.click('#process-list .chip[data-process="outpaint"]');
check(await page.locator('.tool[data-tool="extend"]').getAttribute("aria-pressed") === "true", "描き足すを選ぶと枠の道具になる");
await page.waitForTimeout(200);
const size = await page.evaluate(() => window.v3Stage.size);
const handle = await at(size.w, size.h / 2);
await page.mouse.move(handle.x, handle.y);
await page.mouse.down();
await page.mouse.move(handle.x + 120, handle.y, { steps: 8 });
await page.mouse.up();
await page.waitForTimeout(200);
const unit = await page.locator('[data-name="unit"]').inputValue();
const right = Number(await page.locator('[data-name="right"]').inputValue());
check(unit === "px" && right > 0, `枠を動かすと「画素で」と右の量が入る（右 ${right}px）`);
await page.selectOption('[data-name="unit"]', "mm");
await page.fill('[data-name="right"]', "0");
await page.fill('[data-name="left"]', "20");
await page.dispatchEvent('[data-name="left"]', "input");
await page.waitForTimeout(200);
const ext = await page.evaluate(() => window.v3Stage.extend);
check(ext.left === 40, `mm で入れた量が画面の枠になる（左 20mm → ${ext.left}px。コマの絵は 2px/mm）`);
await shot("outpaint_extend");

// ---- ペン（人の手の層に描く）
await page.click('.tool[data-tool="pen"]');
await drag([[30, 200], [80, 215], [140, 205], [200, 220]]);
await page.waitForFunction(() => document.querySelectorAll(".vrow").length >= 3);
await page.waitForTimeout(300);
await shot("pen_stroke");

// ---- 消しゴム（コマの絵の画素を消す）
await page.click('.tool[data-tool="erase"]');
await drag([[250, 30], [290, 60], [300, 100]]);
await page.waitForFunction(() => window.v3Stage.protCanvas !== null);
await page.waitForTimeout(500);
check(await page.locator('.tool[data-tool="erase"]').getAttribute("aria-pressed") === "true", "消した後も消しゴムのまま");
await shot("erase_pixels");

// ---- 指示で直す（このつなぎ先は持っていないので、つなぎ先が無いと出る）
await page.click('#process-list .chip[data-process="instruction_edit"]');
await shot("instruction_edit_form");

} catch (e) {
  await shot("failure");
  console.log(errors.join("\n"));
  await browser.close();
  throw e;
}
console.log(errors.length ? errors.join("\n") : "画面のエラーなし");
await browser.close();
if (errors.length) process.exit(1);
