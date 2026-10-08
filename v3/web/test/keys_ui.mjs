// キー・キーの一覧・キーを変える・絵だけ・全画面の試験（V3細部の決めごと 22章）。Playwright（Chromium）で通す。
//   NODE_PATH=/opt/node22/lib/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node v3/web/test/keys_ui.mjs
// 相手は偽のサーバー（下の MOCK。page.route で口を横取りして答える。本物ではない）。
// 画面のファイル（v3/web）はそのまま出す。偽なのは口の答えだけで、キーの受け方・窓・絵だけ・全画面は本物の画面のコード。
// 偽の口：/auth/mode・/me/settings（利用者ごとの設定。本物と同じく PUT は全部を書き換える）・作品・ページ・コマ・絵・候補・版・確認の記録
// 画面の写しは SHOTS=<フォルダ> を付けたときだけ撮る（ui_common.mjs）。普段は v3/web/test/run_ui.mjs から流す
import zlib from "node:zlib";
import { makeShot, openBrowser, serveWeb } from "./ui_common.mjs";
const ORIGIN = "http://keys.v3.test";
const USER = "key-author";

// ---------------------------------------------------------------- 絵（PNG を作る。試験の絵で、作品の絵ではない）
function png(w, h, px) {
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 3 + 1)] = 0;
    for (let x = 0; x < w; x++) raw.set(px(x, y), y * (w * 3 + 1) + 1 + x * 3);
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}
// 白い紙に黒い線の丸と、太さの違う斜めの線（variant で位置を変える）
function art(variant) {
  const W = 480, H = 360, cx = 170 + variant * 40, cy = 170, r = 90 + variant * 6;
  return png(W, H, (x, y) => {
    const d = Math.hypot(x - cx, y - cy);
    const ring = Math.abs(d - r) < 3 || Math.abs(d - r * 0.45) < 2;
    const hatch = x > 300 && (x + y + variant * 7) % 14 < 2;
    const ground = y > 290 && y < 294;
    return ring || hatch || ground ? [24, 24, 24] : [255, 255, 255];
  });
}
const IMAGES = { img0: art(0), c1: art(1), c2: art(2), c3: art(3), c4: art(-1) };

// ---------------------------------------------------------------- 偽の口
const settings = new Map();   // 利用者 → 設定
const WORK = {
  work: { id: "w1", title: "砂の町", reading_direction: "rtl", text_direction: "vertical", medium: "paper" },
  volumes: [], episodes: [{ id: "e1", volume_id: null, number: 1, title: "砂の町", removed: false }],
  pages: [1, 2, 3, 4].map((n) => ({ id: `p${n}`, episode_id: "e1", number: n, removed: false })),
  panels: [{ id: "pn1", page_id: "p1", order: 1, removed: false, image_id: "img0", image_placement: null }],
  text_items: [], panel_layers: [], page_items: [], spreads: [],
};
const CANDS = {
  panel_image_id: "img0",
  sets: [{ id: "s1", created_at: "2026-10-08T10:00:00Z", requested_params: { prompt: "夕方の砂漠の町、丸い月" }, process: "text_to_image",
    jobs: [{ id: "j1", status: "done" }],
    images: ["c1", "c2", "c3", "c4"].map((id, i) => ({ id, job_id: "j1", discarded: false, origin: "generated", seed: 4100 + i })) }],
};
const RECORDS = [{ id: "r1", target_kind: "page", target_id: "p2", from_status: "draft", to_status: "in_review", comment: "2ページの3コマ目、手の向きを見てください", actor_id: "key-editor", actor_kind: "human", created_at: "2026-10-08T09:00:00Z", reverts_record_id: null }];

const HARNESS = {
  last_event_id: 0, stale: [], progress: [],
  stage_runs: ["S0", "S1", "S2", "S3", "S4", "S5"].map((stage) => ({ id: `r-${stage}`, stage, episode_id: "e1", status: stage === "S5" ? "running" : "done" })),
  units: [
    ...["S0", "S1", "S2", "S3", "S4"].map((st) => ({ unit_id: `u-${st}`, stage_run_id: `r-${st}`, kind: st === "S2" ? "name_draft" : "panel_image", status: "done", page_id: "p1", target_id: "pn1", attempt: 1, max_attempts: 3, step: "end" })),
    { unit_id: "u-S5a", stage_run_id: "r-S5", kind: "panel_image", status: "running", page_id: "p1", target_id: "pn1", attempt: 1, max_attempts: 3, step: "generate" },
    { unit_id: "u-S5b", stage_run_id: "r-S5", kind: "panel_image", status: "awaiting_review", page_id: "p1", target_id: "pn1", attempt: 2, max_attempts: 3, step: "review" },
  ],
};

function answer(method, path, body, user) {
  const u = new URL(path, ORIGIN);
  const p = u.pathname;
  const j = (json, status = 200, headers = {}) => ({ status, body: JSON.stringify(json), contentType: "application/json", headers });
  if (method === "GET" && p === "/auth/mode") return j({ mode: "dev_header" });
  if (p === "/me/settings") {
    if (method === "GET") return j(settings.get(user) ?? { user_id: user, language: null, autosave: null, autosave_interval_seconds: null, other: {}, updated_at: null });
    if (method === "PUT") {
      const extra = Object.keys(body).filter((k) => !["language", "autosave", "autosave_interval_seconds", "other"].includes(k));
      if (extra.length) return j({ detail: `余計な項目：${extra}` }, 422);
      const s = { user_id: user, ...body, updated_at: new Date().toISOString() };
      settings.set(user, s);
      return j(s);
    }
  }
  if (method === "GET" && p === "/works") return j([{ id: "w1", title: "砂の町", reading_direction: "rtl", text_direction: "vertical", medium: "paper" }]);
  if (method === "GET" && p === "/works/w1") return j(WORK);
  if (method === "GET" && p === "/services") return j([]);
  // 工程の画面：今の状態（流れの続きは送らない。つないだままにする）
  if (method === "GET" && p === "/works/w1/harness/snapshot") return j(HARNESS);
  if (method === "GET" && p === "/works/w1/harness/review-items") return j({ items: [] });
  if (method === "GET" && p === "/works/w1/image-processes") return j([]);
  if (method === "GET" && p === "/works/w1/review-records") return j(RECORDS);
  if (method === "GET" && p === "/works/w1/panels/pn1/layers") return j({ panel: {}, layers: [] });
  if (method === "GET" && p === "/works/w1/panels/pn1/candidates") return j(CANDS);
  if (method === "GET" && p === "/works/w1/panels/pn1/versions") return j({ versions: [] });
  const m = p.match(/^\/works\/w1\/images\/(\w+)\/(file|thumbnail|protected-mask)$/);
  if (method === "GET" && m) {
    if (m[2] === "protected-mask") return { status: 200, body: png(4, 4, () => [0, 0, 0]), contentType: "image/png", headers: { "X-V3-Region-Count": "0" } };
    return { status: 200, body: IMAGES[m[1]], contentType: "image/png" };
  }
  return j({ detail: `偽のサーバーに無い口：${method} ${p}` }, 404);
}
const misses = [];
async function install(page) {
  await serveWeb(page, ORIGIN, async (route, u) => {
    const req = route.request();
    if (u.pathname.endsWith("/harness/stream")) return;   // 流れは開いたまま何も送らない（route を閉じない）
    const r = answer(req.method(), u.pathname + u.search, req.postData() ? JSON.parse(req.postData()) : null, req.headers()["x-v3-user"]);
    if (r.status === 404) misses.push(`${req.method()} ${u.pathname}`);
    return route.fulfill(r);
  });
}

// ---------------------------------------------------------------- 試験
const failures = [];
function check(ok, what) { if (ok) console.log("ok", what); else { failures.push(what); console.log("NG", what); } }
let takeShot = null;
async function shot(_page, name) { await takeShot(name); }

const browser = await openBrowser();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 860 }, locale: "ja-JP" });
await ctx.addInitScript((u) => { try { localStorage.setItem("v3.user", u); } catch { /* */ } }, USER);
const page = await ctx.newPage();
takeShot = makeShot(page, { onSize: (name, kb) => check(kb < 1024, `${name}.png が 1MB 未満（${kb}KB）`) });
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message} ${e.stack}`));
page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
page.on("dialog", (d) => d.accept());
await install(page);

const attr = (sel, name) => page.getAttribute(sel, name);
const tool = () => page.evaluate(() => document.querySelector(".ftb .tool[aria-pressed=true]")?.dataset.tool);
const html = (name) => page.evaluate((n) => document.documentElement.hasAttribute(n), name);
const keymapOf = () => settings.get(USER)?.other?.keymap ?? {};

// ===== 画像生成の画面
await page.goto(`${ORIGIN}/web/index.html`);
await page.waitForSelector(".cand[data-image=c4] img[src]", { state: "attached" });
await page.waitForFunction(() => document.querySelector("[data-tool=pen] kbd")?.textContent === "B");
check(await page.evaluate(async () => (await import("/web/common/keymap.js")).allConflicts().length) === 0, "初めの割り当てに重なりが無い");
check((await attr("[data-tool=pen]", "title")) === "ペン (B)", "ボタンに指を置くとキーが出る（title がペン (B)）");

// キーが効く
await page.keyboard.press("b");
check(await tool() === "pen", "B でペン");
await page.keyboard.press("e");
check(await tool() === "erase", "E で消しゴム");
await page.keyboard.press("v");
check(await tool() === "select", "V で見る");
const z0 = await page.evaluate(() => window.v3Stage.c.getZoom());
await page.keyboard.press("+");
check(await page.evaluate(() => window.v3Stage.c.getZoom()) > z0, "+ で広げる");

// 押している間：Space で手のひら、離すと戻る
await page.keyboard.press("b");
await page.keyboard.down("Space");
check(await tool() === "select", "Space を押している間は見る（動かす）");
await page.keyboard.up("Space");
check(await tool() === "pen", "Space を離すとペンに戻る");

// 入力の欄の中では効かない。Esc は欄から出る
await page.click("#user");
await page.keyboard.press("End");
await page.keyboard.press("v");
check(await tool() === "pen", "入力の欄で V を打っても道具は変わらない");
check((await page.inputValue("#user")).endsWith("v"), "入力の欄に v が入る");
await page.keyboard.press("Backspace");
await page.keyboard.press("Escape");
check(await page.evaluate(() => document.activeElement?.id !== "user"), "入力の欄で Esc を押すと欄から出る");

// IME の変換中（isComposing・keyCode 229）は効かない。欄の外に向けて送っても同じ
const imeIgnored = await page.evaluate(() => {
  const send = (init, code229) => {
    const e = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init });
    if (code229) Object.defineProperty(e, "keyCode", { get: () => 229 });
    document.body.dispatchEvent(e);
  };
  document.body.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true, data: "" }));
  send({ key: "v", code: "KeyV", isComposing: true });
  send({ key: "Process", code: "KeyE" }, true);
  send({ key: "e", code: "KeyE" }, true);
  document.body.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true, data: "べ" }));
  return document.querySelector(".ftb .tool[aria-pressed=true]").dataset.tool;
});
check(imeIgnored === "pen", "IME の変換中のキー（isComposing・keyCode 229）では道具が変わらない");
// 本物の IME の変換（CDP の Input.imeSetComposition）を入力の欄で行う間も効かない
const cdp = await ctx.newCDPSession(page);
await page.click("#user");
await cdp.send("Input.imeSetComposition", { text: "べ", selectionStart: 1, selectionEnd: 1 });
await page.keyboard.press("v");
await cdp.send("Input.insertText", { text: "べ" });
check(await tool() === "pen", "入力の欄で変換している間に V を押しても道具は変わらない");
await page.fill("#user", USER);
await page.keyboard.press("Escape");

// キーの一覧
await page.keyboard.press("Shift+?");
await page.waitForSelector("#v3-help[open]");
check(await page.isVisible("#v3-help tr[data-id='workbench.pen']"), "? でキーの一覧が開き、ペンが出る");
check(await page.isVisible("#v3-help [data-scope=global]"), "キーの一覧に「どの画面でも」が出る");
await page.fill("#v3-help-q", "消し");
check(await page.locator("#v3-help tr[data-id]").count() === 1, "キーの一覧を「消し」で探すと1件（消しゴム）");
await page.fill("#v3-help-q", "");
await shot(page, "13_keys_help");
await page.keyboard.press("Escape");
check(!(await page.isVisible("#v3-help")), "Esc でキーの一覧が閉じる");
// 探す欄に入ったまま閉じても、すぐ次のキーが効く（閉じた窓の欄に残ったままキーが止まっていたのを直した）

// 絵だけ・Tab・全画面・Esc の順
await page.keyboard.press("Shift+F");
check(await html("data-focus"), "Shift+F で絵だけになる");
check(!(await page.isVisible("header.top")) && !(await page.isVisible(".v3-nav")), "絵だけの間は上の帯と画面の帯を隠す");
check(await page.isVisible(".cand[data-image=c1]") && !(await page.isVisible("[data-pane=ask]")), "絵だけの間は候補の帯だけ残す");
check(await page.isVisible(".ftb") && await page.isVisible(".v3-viewbar"), "絵だけの間も道具の帯と小さい帯は出る");
await shot(page, "14_workbench_focus");
await page.keyboard.press("Tab");
check(await html("data-peek") && await page.isVisible("header.top"), "Tab でパネルを一時的に出す");
await page.keyboard.press("Tab");
check(!(await html("data-peek")) && !(await page.isVisible("header.top")), "もう一度 Tab で隠す");
await page.reload();
await page.waitForSelector(".cand[data-image=c1] img[src]", { state: "attached" });
check(await html("data-focus"), "絵だけは画面ごとに覚え、開き直しても絵だけのまま");

await page.keyboard.press("Control+Shift+F");
await page.waitForFunction(() => document.documentElement.hasAttribute("data-fullscreen"));
check(await page.evaluate(() => !!document.fullscreenElement), "Ctrl+Shift+F で全画面になる");
await page.keyboard.press("l");
await page.evaluate(() => { window.v3Stage.poly = [{ x: 10, y: 10 }, { x: 60, y: 10 }]; });
await page.keyboard.press("Escape");
const afterEsc1 = await page.evaluate(() => ({ poly: !!window.v3Stage.poly, focus: document.documentElement.hasAttribute("data-focus"), fs: !!document.fullscreenElement }));
check(!afterEsc1.poly && afterEsc1.focus && afterEsc1.fs, "Esc 1回目：道具（多角形）だけをやめる");
await page.keyboard.press("Escape");
const afterEsc2 = await page.evaluate(() => ({ focus: document.documentElement.hasAttribute("data-focus"), fs: !!document.fullscreenElement }));
check(!afterEsc2.focus && afterEsc2.fs, "Esc 2回目：絵だけから抜ける（全画面のまま）");
await page.keyboard.press("Escape");
await page.waitForFunction(() => !document.fullscreenElement);
check(!(await html("data-fullscreen")), "Esc 3回目：全画面から抜ける");
// ブラウザの側で全画面を抜けても、画面の状態が合う
await page.keyboard.press("Shift+F");
await page.keyboard.press("Control+Shift+F");
await page.waitForFunction(() => !!document.fullscreenElement);
await page.evaluate(() => document.exitFullscreen());
await page.waitForFunction(() => !document.documentElement.hasAttribute("data-fullscreen"));
check(await html("data-focus") && (await attr(".v3-viewbar [data-view=fullscreen]", "aria-pressed")) === "false",
  "ブラウザの側で全画面を抜けると、全画面の印が外れ、絵だけはそのまま");
await page.click(".v3-viewbar [data-view=exit]");
check(!(await html("data-focus")), "小さい帯の「抜ける」で絵だけから抜ける");
await page.keyboard.press("v");

// キーを変える：足す・残す・重なり・初めに戻す・今のアプリのキー
await page.click("#v3-keys");
await page.waitForSelector("#v3-keys[open]");
await page.click("#v3-keys tr[data-id='workbench.pen'] [data-add]");
await page.keyboard.press("k");
await page.waitForFunction(() => document.querySelector("#v3-keys tr[data-id='workbench.pen']")?.textContent.includes("変えた"));
check(JSON.stringify(keymapOf()["workbench.pen"]) === JSON.stringify(["b", "k"]), "ペンに K を足すと、利用者の設定（/me/settings の other.keymap）に残る");
await page.click("#v3-keys tr[data-id='workbench.erase'] [data-add]");
await page.keyboard.press("k");
await page.waitForSelector("#v3-keys .v3-conflict");
check((await page.textContent("#v3-keys .v3-conflict")).includes("ペン"), "消しゴムに K を割り当てると、ペンと重なると出る");
check(!(keymapOf()["workbench.erase"]), "重なりを選ぶ前は残さない");
await shot(page, "15_keys_settings_conflict");
await page.click("#v3-ks-take");
await page.waitForFunction(() => !document.querySelector("#v3-keys .v3-conflict"));
check(JSON.stringify(keymapOf()["workbench.erase"]) === JSON.stringify(["e", "k"]) && !keymapOf()["workbench.pen"], "「相手から外して割り当てる」で消しゴムが K、ペンは初めに戻る");
await page.keyboard.press("Escape");
await page.keyboard.press("k");
check(await tool() === "erase", "変えたキー K で消しゴムになる");
// 開き直しても（サーバーから読み直して）変えたキーが効く
await page.reload();
await page.waitForSelector(".cand[data-image=c1] img[src]", { state: "attached" });
await page.waitForFunction(() => document.querySelector("[data-tool=erase]")?.title.includes("K"));
await page.keyboard.press("k");
check(await tool() === "erase", "開き直しても変えたキーが効く");
// 今のアプリのキーを読み込む
await page.click("#v3-keys");
await page.click("#v3-ks-import");
check(await page.isVisible("#v3-ks-import-list"), "今のアプリで違うキーが並ぶ");
await page.click("#v3-ks-import-go");
await page.waitForFunction(() => !document.querySelector("#v3-ks-import-list"));
check((keymapOf()["workbench.zoomIn"] ?? []).includes("$mod+8") && (keymapOf()["view.help"] ?? []).includes("F1"), "読み込むと Ctrl+8（広げる）と F1（キーの一覧）が足される");
await page.keyboard.press("Escape");
const z1 = await page.evaluate(() => window.v3Stage.c.getZoom());
await page.keyboard.press("Control+8");
check(await page.evaluate(() => window.v3Stage.c.getZoom()) > z1, "読み込んだ Ctrl+8 で広げる");
await page.click("#v3-keys");
await page.click("#v3-ks-reset");
await page.waitForFunction(() => !document.querySelector("#v3-keys .flag.ai"));
check(Object.keys(keymapOf()).length === 0, "全部を初めに戻すと、変えた割り当てが無くなる");
await page.keyboard.press("Escape");
// 続けて押すキー：G のあと 8 は今の画面なので動かない。G のあと 0 で確認へ
await page.keyboard.press("g");
await page.keyboard.press("8");
check(new URL(page.url()).pathname === "/web/index.html", "G のあと 8（今の画面）では移らない");
await page.keyboard.press("g");
await page.keyboard.press("0");
await page.waitForURL(/\/web\/review\//);
check(true, "G のあと 0 で確認の画面へ");

// ===== 確認の画面（作品をまたぐ画面）：読み通す
await page.waitForSelector("[data-page=p1]");
await page.click("#read-through");
await page.waitForSelector(".reader-page");
check(await html("data-focus") && !(await page.isVisible("#top")), "「読み通す」で絵だけになり、ページを大きく出す");
const n = () => page.textContent(".reader-n");
check((await n()) === "1", "読み通すは 1 ページから");
await page.keyboard.press("ArrowLeft");
check((await n()) === "2", "右から左の作品では ← で次のページ");
await page.keyboard.press("ArrowRight");
check((await n()) === "1", "→ で前のページ");
await page.keyboard.press("PageDown");
check((await n()) === "2", "PageDown で次のページ");
check((await page.textContent(".reader-page")).includes("手の向き"), "ページのコメントが出る");
await shot(page, "16_review_read_through");
await page.keyboard.press("Escape");
check(!(await html("data-focus")) && await page.isVisible("#top"), "Esc で読み通すから抜ける");
await page.keyboard.press("ArrowLeft");
check(!(await page.isVisible(".reader-page")), "絵だけでないときは ← で何もしない");
await page.keyboard.press("Shift+?");
await page.waitForSelector("#v3-help[open]");
check(await page.isVisible("#v3-help tr[data-id='review.left']"), "確認の画面のキーの一覧に「左のページへ」が出る");
await page.keyboard.press("Escape");
await page.click("#comment");
await page.keyboard.press("Shift+?");
check(!(await page.isVisible("#v3-help")), "コメントの欄で ? を打ってもキーの一覧は開かない");
check((await page.inputValue("#comment")) === "?", "コメントの欄に ? が入る");

// ===== 工程の画面：絵だけは図だけ（見張る画面）
await page.goto(`${ORIGIN}/web/harness/?work=w1`);
await page.waitForSelector("#graph canvas");
await page.waitForFunction(() => document.querySelector("#fit kbd")?.textContent === "0");
const h0 = await page.evaluate(() => document.querySelector(".graph-wrap").getBoundingClientRect().height);
await page.keyboard.press("Shift+F");
// 図が広がり終わるのを待つ（決まった時間は待たない）。広がらなければ下の確かめで落ちる
await page.waitForFunction((h) => document.querySelector(".graph-wrap").getBoundingClientRect().height > h, h0, { timeout: 5000 }).catch(() => {});
const hv = await page.evaluate(() => ({ h: document.querySelector(".graph-wrap").getBoundingClientRect().height, vh: innerHeight,
  hidden: ["#side", ".table-box", "header.top", ".v3-nav"].every((q) => getComputedStyle(document.querySelector(q)).display === "none") }));
check(hv.hidden && hv.h > h0 && hv.h > hv.vh * 0.8, `工程の画面：Shift+F で図だけになり、図が画面の高さいっぱい（${Math.round(h0)} → ${Math.round(hv.h)}px）`);
await shot(page, "17_harness_focus");
await page.keyboard.press("Shift+?");
await page.waitForSelector("#v3-help[open]");
check(await page.isVisible("#v3-help tr[data-id='harness.fit']"), "工程の画面のキーの一覧に「図の全体を見る」が出る");
await page.keyboard.press("Escape");
await page.keyboard.press("0");
await page.keyboard.press("Escape");
check(!(await html("data-focus")) && await page.isVisible("#side"), "工程の画面：Esc で図だけから戻る");

// ===== ほかの画面にも帯のボタンとキーがある
// 偽のサーバーはこれらの画面の中身（話の一覧・進み・設定資料・つなぎ先など）を持たない。中身を読めずに出るエラーはここでは数えない
const errorsBeforeOthers = errors.length;
for (const s of ["works", "plan", "structure", "materials", "export", "services", "import", "translation"]) {
  await page.goto(`${ORIGIN}/web/${s}/`);
  await page.waitForSelector("#v3-keys");
  await page.keyboard.press("Shift+F");
  const ok = await html("data-focus") && !(await page.isVisible("#top"));
  await page.keyboard.press("Escape");
  check(ok && !(await html("data-focus")), `${s}：帯にキーのボタンがあり、Shift+F で絵だけ・Esc で戻る`);
}

console.log("偽のサーバーに無かった口：", [...new Set(misses)].join("、") || "なし");
console.log(`ほかの画面で中身を読めずに出たエラー（数えない）：${errors.length - errorsBeforeOthers} 件`);
const realErrors = errors.slice(0, errorsBeforeOthers);
check(realErrors.length === 0, `画面のエラーが無い ${realErrors.join(" / ")}`);
await browser.close();
if (failures.length) { console.log(`失敗 ${failures.length} 件`); process.exit(1); }
console.log("全部通りました");
