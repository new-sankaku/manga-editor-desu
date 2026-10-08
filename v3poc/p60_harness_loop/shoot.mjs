// P60 の画面を Playwright（Chromium）で開いて確かめ、絵を撮る。
// 実行: node shoot.mjs <名前> <URL の後ろ（?stage=… など）> [操作]
//   操作：detail=<作業ID>:<ノード>（ノードを押して詳細を出す）、approve（判断待ちの作業の「採用」を全部押す）、
//         reject=<作業ID>:<理由>（理由を入れて「却下して作り直す」を押す）
// CDN の3つは、コンテナの Chromium が中継の証明書を持たないので、curl で取った同じ版の写し（P60_CDN）を返す。
import { createRequire } from "module";
import fs from "fs";
import path from "path";
const require = createRequire(import.meta.url);
const { chromium } = require("/opt/node-tools/node_modules/playwright");

const [name, query = "", op = ""] = process.argv.slice(2);
const port = process.env.P60_API_PORT || "63262";
const cdn = process.env.P60_CDN;
const out = path.join(path.dirname(new URL(import.meta.url).pathname), "out");
const browser = await chromium.launch({ executablePath: undefined });
const page = await browser.newPage({ viewport: { width: 1500, height: 1250 } });
const errors = [];
page.on("pageerror", e => errors.push(String(e)));
page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
await page.route("https://cdn.jsdelivr.net/**", route => {
  const file = path.basename(new URL(route.request().url()).pathname);
  route.fulfill({ status: 200, contentType: "application/javascript", body: fs.readFileSync(path.join(cdn, file)) });
});
await page.goto(`http://127.0.0.1:${port}/${query}`);
await page.waitForFunction(() => document.querySelectorAll(".card").length > 0, null, { timeout: 30000 });
await page.waitForTimeout(2500);
const result = { name, op, errors };
if (op.startsWith("detail=")) {
  const id = op.slice(7);
  await page.evaluate(id => window.__focusUnit(id.split(":")[0]), id);
  await page.waitForTimeout(2500);
  const pos = await page.evaluate(id => { const cyEl = window.__cyLoop.getElementById(id); const p = cyEl.renderedPosition();
    const r = document.getElementById("cy-loop").getBoundingClientRect(); return { x: r.left + p.x, y: r.top + p.y + window.scrollY }; }, id);
  await page.mouse.click(pos.x, pos.y - (await page.evaluate(() => window.scrollY)));
  await page.waitForTimeout(800);
  result.detail = await page.locator("#detail").innerText();
}
if (op === "approve") {
  const btns = page.locator(".card .review button[data-a=approve]");
  result.approved = await btns.count();
  for (let i = 0; i < result.approved; i++) { await page.locator(".card .review button[data-a=approve]").first().click(); await page.waitForTimeout(2500); }
  result.messages = await page.locator(".card .msg").allInnerTexts();
}
if (op.startsWith("reject=")) {
  const [wf, reason] = op.slice(7).split(":");
  const card = page.locator(`.card[data-wf="${wf}"]`);
  await card.locator("input[data-r]").fill(reason);
  await card.locator("button[data-a=reject]").click();
  await page.waitForTimeout(1500);
  result.messages = await card.locator(".msg").allInnerTexts();
}
result.text = (await page.locator("main").innerText()).slice(0, 3000);
await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true });
fs.writeFileSync(path.join(out, `shot_${name}.json`), JSON.stringify(result, null, 1));
console.log(JSON.stringify({ name, errors, detail: result.detail?.slice(0, 200), approved: result.approved, messages: result.messages }));
await browser.close();
