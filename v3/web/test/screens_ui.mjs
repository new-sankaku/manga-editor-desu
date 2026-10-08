// 作品をまたぐ画面（作品と話・企画・構成・設定資料・書き出し・生成サービス・取り込み・翻訳・確認）を Playwright で通し、画面の写しを残す。
// 本物のサーバー（/web を出す）に、作品・話・ページ・文字・設定資料・訳文・確認の記録・つなぎ先を足してから見る。
// 使い方：
//   V3_WEB=http://127.0.0.1:8771/web/ SHOTS=v3/web/screenshots \
//   NODE_PATH=/opt/node22/lib/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node v3/web/test/screens_ui.mjs
// 前もって：利用者 scr-admin をサーバーの管理者にしておく（uv run python -m v3server.admin_command_line grant-admin scr-admin）
//
// 模擬（本物でない所）は下の MOCK だけ。どれも page.route で差し替え、写しの名前に mock を付ける。
// - POST /works/{id}/preflight：worktree-agent-a4222899f5500b610 にあり、この枝のサーバーには無い
// - POST /works/{id}/exports と、その進み具合・ファイル：本物は Temporal の作業者で書き出す（この環境では共有の Temporal に流さない）
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const WEB = process.env.V3_WEB;
const SHOTS = process.env.SHOTS;
if (!WEB || !SHOTS) throw new Error("V3_WEB・SHOTS を決めてください");
mkdirSync(SHOTS, { recursive: true });
const BASE = new URL("..", WEB).href.replace(/\/$/, "");
const FIXTURE = fileURLToPath(new URL("../../server/tests/fixtures/current_app_project_4pages.lz4", import.meta.url));

const AUTHOR = "scr-author", EDITOR = "scr-editor", TRANSLATOR = "scr-tr", ADMIN = "scr-admin";
const failures = [];
function check(ok, what) { if (!ok) { failures.push(what); console.log("NG", what); } else console.log("ok", what); }

// ---------------------------------------------------------------- サーバーに足す（本物）
async function req(user, method, path, body, form) {
  const r = await fetch(BASE + path, { method, headers: { "X-V3-User": user, ...(body ? { "Content-Type": "application/json" } : {}) },
                                       body: form || (body ? JSON.stringify(body) : undefined) });
  const text = await r.text();
  if (!r.ok) throw new Error(`${method} ${path} → ${r.status} ${text}`);
  return text ? JSON.parse(text) : null;
}
const opAs = (user, wid, body) => req(user, "POST", `/works/${wid}/ops`, body);

async function seed(pngBytes) {
  // id は走らせるごとに変える（同じ DB で何度も走らせる）
  const stamp = Date.now().toString(36);
  const w = await req(AUTHOR, "POST", "/works", { title: "砂の町の配達人", reading_direction: "rtl", text_direction: "vertical",
                                                   medium: "paper", trim_size: "A4", default_page_count: 24 });
  const wid = w.id;
  const op = (b) => opAs(AUTHOR, wid, b);
  await op({ type: "set_work_settings", preferences: { language: "ja" },
             page_spec: { frame_width_mm: 180, frame_height_mm: 260, trim_width_mm: 210, trim_height_mm: 297, bleed_mm: 3, gutter_x_mm: 3, gutter_y_mm: 5 } });
  await op({ type: "set_work_plan", synopsis: "砂に埋もれた町で、少年が手紙を届けて回る。届かなかった手紙の宛先を探すうちに、町が沈んだ理由に近づく。",
             audience: "中高生から大人まで", exclusions: ["実在の地名"], notes: "1話完結を重ねる。各話の最後に次の宛先を出す" });
  const vol = "v" + stamp + "a";
  await op({ type: "add_volume", id: vol, number: 1, title: "第1巻" });
  const ep1 = "e" + stamp + "a", ep2 = "e" + stamp + "b";
  const soon = new Date(Date.now() + 9 * 86400e3).toISOString();
  await op({ type: "add_episode", id: ep1, volume_id: vol, number: 1, title: "届かない手紙", deadline: soon });
  await op({ type: "add_episode", id: ep2, volume_id: vol, number: 2, title: "砂時計の家" });
  const lines = [["少年", "この手紙、宛先が消えてる"], ["老人", "砂に呑まれた家じゃな"], [null, "町の東の外れ"], ["少年", "それでも届ける"],
                 ["少女", "あなたが配達人？"], ["少年", "うん、手紙があるんだ"], [null, "三日後"], ["少女", "これは……母の字"]];
  const pages = [];
  for (let n = 1; n <= 6; n += 1) {
    const pid = `p${stamp}${n}`; pages.push(pid);
    await op({ type: "add_page", id: pid, episode_id: ep1, number: n });
    for (let k = 1; k <= 2; k += 1) {
      const pan = `${pid}k${k}`;
      await op({ type: "add_panel", id: pan, page_id: pid, order: k });
      if (n <= 4) {
        const [speaker, text] = lines[((n - 1) * 2 + k - 1) % lines.length];
        await op({ type: "add_text_item", id: `${pan}t`, panel_id: pan, item_kind: speaker ? "balloon" : "caption", order: 1, text, speaker });
      }
    }
  }
  for (const [user, role] of [[EDITOR, "editor"], [TRANSLATOR, "translator"], ["scr-asst", "assistant"]]) await op({ type: "set_member", user, role, granted: true });
  await op({ type: "assign_page", page_id: pages[4], user: "scr-asst", assigned: true });
  // 設定資料（絵は1枚だけ本物を置く）
  const fd = new FormData();
  fd.append("image", new Blob([pngBytes], { type: "image/png" }), "boy.png");
  fd.append("role", "character_sheet"); fd.append("origin", "human_drawn");
  const img = await req(AUTHOR, "POST", `/works/${wid}/images`, null, fd);
  await op({ type: "add_material_entry", kind: "character", name: "ナギ", traits: "14歳。砂よけの布を首に巻く。黒い短髪、左の頬に傷",
             clothes: [{ name: "配達の服", description: "肩掛けかばんと砂よけのゴーグル", image_ids: [] }], image_ids: [img.id],
             generation: { prompt: "砂漠の町の少年、布を首に巻く、肩掛けかばん", negative_prompt: "派手な色", seed: 1234, loras: [], reference_image_ids: [] } });
  await op({ type: "add_material_entry", kind: "character", name: "ミオ", traits: "13歳。長い髪をひとつに束ねる" });
  await op({ type: "add_material_entry", kind: "background", name: "沈んだ郵便局", traits: "屋根まで砂に埋まり、窓から出入りする" });
  await op({ type: "add_material_entry", kind: "prop", name: "宛先の消えた手紙" });
  // 訳文（翻訳者）
  const tr = (n, k, text) => opAs(TRANSLATOR, wid, { type: "set_text_translation", text_item_id: `p${stamp}${n}k${k}t`, language: "en", text });
  await tr(1, 1, "The address on this letter is gone.");
  await tr(1, 2, "That house was swallowed by the sand.");
  await tr(2, 1, "The eastern edge of town.");
  // 確認：1 は確認待ち、2 は承認、3 は直しが要る
  const rv = (user, n, status, comment) => opAs(user, wid, { type: "set_review_status", target_kind: "page", target_id: pages[n - 1], status, ...(comment ? { comment } : {}) });
  for (const n of [1, 2, 3]) await rv(AUTHOR, n, "in_review");
  await rv(EDITOR, 2, "approved", "このままで良いです");
  await rv(EDITOR, 3, "needs_changes", "2コマ目の少女の表情をもう少し驚かせてください");
  return { wid, ep1, ep2, pages };
}

// つなぎ先（全作品で共通）。無ければ足す
async function seedServices() {
  const cur = await req(ADMIN, "GET", "/services");
  if (cur.services.some((s) => s.name === "手元のComfyUI")) return;
  const terms = { commercial_use: "yes", rights_holder: "自分", training_use: "no", credit_required: "no", terms_note: "試験用に入れた要点", checked_on: "2026-10-01" };
  const local = await req(ADMIN, "POST", "/services", { name: "手元のComfyUI", kind: "image", location: "local", adapter: "comfyui", endpoint: "http://127.0.0.1:8188",
                                                         send_mode: "serial", max_concurrency: 1, usage_terms: terms });
  const api = await req(ADMIN, "POST", "/services", { name: "画像API（試験）", kind: "image", location: "api", adapter: "litellm", send_mode: "parallel",
                                                       max_concurrency: 4, monthly_budget: 30000 });
  const text = await req(ADMIN, "POST", "/services", { name: "文のLLM（試験）", kind: "text", location: "api", adapter: "litellm", send_mode: "parallel",
                                                        max_concurrency: 2, monthly_budget: 5000 });
  const put = (sid, p, b) => req(ADMIN, "PUT", `/services/${sid}/processes/${p}`, b);
  await put(local.id, "text_to_image", { aptitude: "good", cost_per_call: 0, model: "手元のモデル" });
  await put(local.id, "inpaint", { aptitude: "normal", cost_per_call: 0 });
  await put(api.id, "text_to_image", { aptitude: "normal", cost_per_call: 6 });
  await put(api.id, "inpaint", { aptitude: "good", cost_per_call: 8 });
  await put(text.id, "extract_characters", { aptitude: "good", cost_per_call: 1, model: "試験のモデル" });
  const route = (p, sid, task, action) => req(ADMIN, "PUT", `/routes/${p}`, { service_id: sid, resend_limit: 2, regenerate_limit: 1, ai_task: task, ai_action: action });
  await route("text_to_image", local.id, "drawing", "propose");
  await route("inpaint", api.id, "drawing", "propose");
  await route("extract_characters", text.id, "settings_material", "propose");
  await req(ADMIN, "PATCH", `/services/${api.id}`, { state: "connected" });
  await req(ADMIN, "PATCH", `/services/${local.id}`, { state: "connected" });
}

// ---------------------------------------------------------------- 模擬（MOCK）
function mockPreflightAndExport(page, pages) {
  let polls = 0;
  page.route("**/works/*/preflight", (r) => r.fulfill({ json: {
    ok: false, errors: 1, warnings: 1, issues: [
      { page_id: pages[2], kind: "safe_area", severity: "error", message: "文字が安全線の外に出ています", location: { table: "text_items", id: `${pages[2]}k2t` } },
      { page_id: pages[4], kind: "image_resolution", severity: "warning", message: "絵の解像度が書き出しの dpi に足りません", location: { table: "panels", id: `${pages[4]}k1` } }] } }));
  page.route("**/works/*/exports", (r) => r.request().method() === "POST"
    ? r.fulfill({ status: 201, json: { id: "mockrun", status: "queued", format: "pdf", page_ids: pages, dpi: null, language: null, spread_output: null, outputs: [], note: null } })
    : r.continue());
  page.route("**/works/*/exports/mockrun", (r) => { polls += 1; r.fulfill({ json: polls < 2
    ? { id: "mockrun", status: "running", format: "pdf", page_ids: pages, outputs: [], note: null }
    : { id: "mockrun", status: "done", format: "pdf", page_ids: pages, outputs: [{ file: "episode1.pdf", bytes: 4_812_345 }], note: null } }); });
  page.route("**/works/*/exports/mockrun/files/*", (r) => r.fulfill({ body: "%PDF-1.4 mock", contentType: "application/pdf" }));
}

// ---------------------------------------------------------------- 画面を通す
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, acceptDownloads: true, locale: "ja-JP" });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/the server responded with a status of (403|422)/.test(m.text())) errors.push(`console: ${m.text()}`); });
page.on("dialog", (d) => d.accept("砂の商人"));

await page.setContent("<canvas id=c width=256 height=256></canvas>");
const dataUrl = await page.evaluate(() => { const c = document.getElementById("c").getContext("2d"); c.fillStyle = "#fff"; c.fillRect(0, 0, 256, 256);
  c.fillStyle = "#433F35"; c.beginPath(); c.arc(128, 90, 46, 0, 7); c.fill(); c.fillRect(88, 140, 80, 100); return document.getElementById("c").toDataURL("image/png"); });
const seeded = await seed(Buffer.from(dataUrl.split(",")[1], "base64"));
await seedServices();
console.log("seeded", seeded.wid);

// 利用者は localStorage の v3.user。同じ origin の空のページで入れてから、目当ての画面を開く
await page.goto(`${BASE}/health`);
async function open(screen, as, extra = "") {
  await page.evaluate((u) => localStorage.setItem("v3.user", u), as);
  await page.goto(`${WEB}${screen}?work=${seeded.wid}${extra}`);
  await page.waitForLoadState("networkidle");
}
async function shot(name, full = true) {
  const path = `${SHOTS}/${name}.png`;
  await page.screenshot({ path, fullPage: full });
  const kb = Math.round(statSync(path).size / 1024);
  check(kb < 1024, `${name}.png は 1MB 未満（${kb}KB）`);
}
const text = () => page.innerText("#main");

// 作品と話
await open("works/", AUTHOR);
check((await text()).includes("届かない手紙"), "作品と話：話が出る");
check((await text()).includes("scr-editor"), "作品と話：参加者が出る");
await shot("01_works");

// 企画
await open("plan/", AUTHOR);
check(await page.locator("textarea").first().inputValue() !== "", "企画：あらすじが入っている");
await shot("02_plan");

// 構成
await open("structure/", AUTHOR, `&episode=${seeded.ep1}`);
check(await page.locator(".pg[data-page]").count() === 6, "構成：6ページが出る");
await page.locator(`.pg[data-page="${seeded.pages[2]}"]`).click();
await page.waitForTimeout(300);
await shot("03_structure");

// 設定資料
await open("materials/", AUTHOR);
await page.getByText("ナギ").first().click();
await page.waitForTimeout(800);
check((await text()).includes("見た目の指示"), "設定資料：生成の設定が出る");
await shot("04_materials");

// 書き出し（preflight と書き出しは模擬）
mockPreflightAndExport(page, seeded.pages);
await open("export/", AUTHOR, `&episode=${seeded.ep1}`);
await page.getByRole("button", { name: "全部", exact: true }).click();
check(await page.locator("#export").isDisabled(), "書き出し：確かめる前は書き出せない");
await page.locator("#preflight").click();
await page.waitForTimeout(500);
check((await text()).includes("安全線の外"), "書き出し：確かめた問題が出る");
await shot("05_export_preflight_mock");
await page.locator("#export").click();
await page.waitForSelector("#run .flag.on", { timeout: 10000 });
const dl = page.waitForEvent("download");
await page.locator("#run button").first().click();
check((await dl).suggestedFilename() === "episode1.pdf", "書き出し：ファイルを保存できる");
await shot("06_export_done_mock");
await page.unrouteAll({ behavior: "ignoreErrors" });

// 生成サービス（管理者・参加者）
await open("services/", ADMIN);
check(await page.locator(".mc[data-process]").count() > 0, "生成サービス：管理者に送り先の表が出る");
await shot("07_services_admin_routes");
await page.locator('.tab[data-tab="cons"]').click();
await page.waitForTimeout(300);
await shot("08_services_admin_connections");
await open("services/", AUTHOR);
check(await page.locator("#member-services").count() === 1, "生成サービス：参加者には作品から見える一覧が出る");
await shot("09_services_member");

// 取り込み（本物：fixture の 4 ページを第2話へ）
await open("import/", AUTHOR, `&episode=${seeded.ep2}`);
await page.setInputFiles("#project", { name: "current_app_project_4pages.lz4", mimeType: "application/octet-stream", buffer: readFileSync(FIXTURE) });
await page.getByRole("button", { name: "取り込む" }).click();
await page.waitForSelector("#report table, #report .note", { timeout: 30000 });
check((await text()).includes("取り込みの報告"), "取り込み：報告が出る");
await shot("10_import_report");

// 翻訳（翻訳者）
await open("translation/", TRANSLATOR, `&episode=${seeded.ep1}&lang=en`);
const before = await page.locator(".pair .flag.warn").count();
const missing = page.locator(".pair", { has: page.locator(".flag.warn") }).first();
await missing.locator("textarea").fill("Even so, I'll deliver it.");
await missing.locator("[data-save]").click();
await page.waitForTimeout(800);
check(await page.locator(".pair .flag.warn").count() === before - 1, "翻訳：翻訳者が訳文を足せる（訳なしが 1 つ減る）");
await shot("11_translation");

// 確認（編集者）
await open("review/", EDITOR, `&episode=${seeded.ep1}&page=${seeded.pages[0]}`);
await page.locator('[data-move="needs_changes"]').click();
await page.waitForTimeout(300);
check((await page.innerText("#toast")).includes("コメント"), "確認：直しの依頼にはコメントが要る");
await page.locator('[data-move="approved"]').click();
await page.waitForTimeout(800);
check((await page.innerText("#cur-status")) === "承認", "確認：編集者が承認できる");
await page.locator(`.pg[data-page="${seeded.pages[2]}"]`).click();
await page.waitForTimeout(300);
await shot("12_review");

await browser.close();
for (const e of errors) console.log(e);
if (errors.length) failures.push(`画面の誤り ${errors.length} 件`);
console.log(failures.length ? `NG ${failures.length}` : "all ok");
process.exit(failures.length ? 1 : 0);
