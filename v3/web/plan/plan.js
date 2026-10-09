// 企画：企画の文（あらすじ・読者・入れないもの・メモ）、作品の決めごと（媒体・向き・判型・ページの寸法・言語）、
// 入稿の設定（色と解像度・2階調・安全線・ページ数の決まり・ノンブル・写植の組版）、作業ごとのAIの関与。
// 口：GET /works/{id}、GET /works/{id}/ai-involvement、POST /works/{id}/plan/extract-characters、
//     操作 set_work_plan・set_work_settings・set_ai_involvement
// 入稿の設定（preferences.print・nombre・typesetting）は worktree-agent-a4222899f5500b610 の口。まだ base に無い
import { t } from "../common/i18n.js";
import { html, render, nothing, api, icon, toast, fail, op, startShell, emptyNote, screenHref,
         MEDIUM, READING, TEXT_DIR, COLOR_MODE, PAGE_KIND, NOMBRE } from "../common/shell.js";
import { fieldsHtml, readFields } from "../common/form_fields.js";

const main = document.getElementById("main");
main.className = "screen side-r";
const dot = (list) => list.join("・");  // i18n:data（区切りの記号）
const S = { workId: null, work: null, ai: [], why: null, busy: false };

const MODE = { ai_auto: t("AIに任せる"), ai_proposes: t("AIが案を出し人が選ぶ"), human_makes_ai_checks: t("人が作りAIは検査だけ"), no_ai: t("AIを使わない") };

async function loadWork(id, why = null) {
  S.workId = id; S.why = why; S.work = null; S.ai = [];
  if (id) {
    try { [S.work, S.ai] = await Promise.all([api.get(`/works/${id}`), api.get(`/works/${id}/ai-involvement`)]); }
    catch (e) { fail(e, t("作品を読み込めませんでした")); S.why = api.errorText(e); }
  }
  draw();
}
async function run(what, fn) {
  if (S.busy) return;
  S.busy = true; draw();
  try { await fn(); } catch (e) { fail(e, what); } finally { S.busy = false; await loadWork(S.workId); }
}

// ---------------------------------------------------------------- 企画の文
const PLAN = [
  { key: "synopsis", label: t("あらすじ"), type: "textarea", rows: 6 },
  { key: "audience", label: t("読者"), type: "textarea", rows: 2 },
  { key: "exclusions", label: t("入れないもの"), type: "lines", rows: 3, hint: t("1行に1つ") },
  { key: "notes", label: t("メモ"), type: "textarea", rows: 3 },
];
function savePlan(e) {
  e.preventDefault();
  const now = readFields(e.target, PLAN) || { synopsis: null, audience: null, exclusions: [], notes: null };
  const before = S.work.work_plans[0] || {};
  const changes = {};
  for (const f of PLAN) {
    const a = JSON.stringify(now[f.key] ?? (f.type === "lines" ? [] : null));
    const b = JSON.stringify(before[f.key] ?? (f.type === "lines" ? [] : null));
    if (a !== b) changes[f.key] = now[f.key] ?? (f.type === "lines" ? [] : null);
  }
  if (!Object.keys(changes).length) { toast(t("変わった所がありません")); return; }
  run(t("企画を保存できませんでした"), async () => { await op(S.workId, { type: "set_work_plan", ...changes }); toast(t("企画を保存しました")); });
}
function extract() {
  run(t("人物を抜き出せませんでした"), async () => {
    const job = await api.post(`/works/${S.workId}/plan/extract-characters`, { params: {} });
    toast(t("人物を抜き出す依頼を入れました（{{status}}）。できた案は「設定資料」に案として入ります", { status: job.status }));
  });
}
function planCard() {
  const p = S.work.work_plans[0];
  const hand = new Set(p ? p.human_hand_fields : []);
  return html`<section class="card" aria-label=${t("企画の文")}>
    <div class="card-h"><span class="h2">${t("企画")}</span>
      <button class="btn ai-o sm" @click=${extract} ?disabled=${S.busy || !p} title=${t("企画の文から人物を抜き出して、設定資料に案として入れる")}>${icon("users")}${t("人物を抜き出す")}</button></div>
    <form class="form" @submit=${savePlan}>
      ${fieldsHtml(PLAN, p)}
      <div class="full acts"><button class="btn primary" ?disabled=${S.busy}>${icon("save")}${t("保存")}</button>
        ${hand.size ? html`<span class="meta">${t("人が書いた項目：{{fields}}（AIは変えずに判断待ちに置きます）", { fields: dot([...hand].map((k) => PLAN.find((f) => f.key === k)?.label || k)) })}</span>` : nothing}</div>
    </form></section>`;
}

// ---------------------------------------------------------------- 作品の決めごと
const WORK = [
  { key: "title", label: t("題") },
  { key: "medium", label: t("媒体"), type: "select", options: MEDIUM },
  { key: "reading_direction", label: t("読む向き"), type: "select", options: READING },
  { key: "text_direction", label: t("文字の向き"), type: "select", options: TEXT_DIR },
  { key: "trim_size", label: t("判型"), placeholder: t("例：B5") },
  { key: "default_page_count", label: t("1話のページ数"), type: "number", step: 1 },
  { key: "first_page_is_left", label: t("1ページ目"), type: "bool", yes: t("左に置く"), no: t("右に置く") },
  { key: "preferences.language", label: t("文字の言語"), placeholder: t("例：ja"), hint: t("元の言語。翻訳と言語ごとの書き出しに要ります") },
];
const SPEC = [
  { key: "trim_width_mm", label: t("仕上がりの幅"), type: "number", hint: "mm" },
  { key: "trim_height_mm", label: t("仕上がりの高さ"), type: "number", hint: "mm" },
  { key: "bleed_mm", label: t("塗り足し"), type: "number", hint: "mm" },
  { key: "frame_width_mm", label: t("基本枠の幅"), type: "number", hint: "mm" },
  { key: "frame_height_mm", label: t("基本枠の高さ"), type: "number", hint: "mm" },
  { key: "gutter_x_mm", label: t("コマの間（横）"), type: "number", hint: "mm" },
  { key: "gutter_y_mm", label: t("コマの間（縦）"), type: "number", hint: "mm" },
];
function saveWork(e) {
  e.preventDefault();
  const w = S.work.work;
  const v = readFields(e.target, WORK) || {};
  const spec = readFields(e.target, SPEC, "spec.");
  const body = { type: "set_work_settings" };
  for (const k of ["title", "medium", "reading_direction", "text_direction", "trim_size", "default_page_count", "first_page_is_left"]) {
    if (v[k] !== null && v[k] !== undefined && v[k] !== w[k]) body[k] = v[k];
  }
  const lang = v.preferences ? v.preferences.language : null;
  if (lang !== ((w.preferences || {}).language ?? null)) body.preferences = { ...(w.preferences || {}), language: lang };
  if (spec && JSON.stringify(spec) !== JSON.stringify(w.page_spec)) body.page_spec = spec;
  if (Object.keys(body).length === 1) { toast(t("変わった所がありません")); return; }
  run(t("決めごとを保存できませんでした"), async () => { await op(S.workId, body); toast(t("決めごとを保存しました")); });
}
function workCard() {
  const w = S.work.work;
  return html`<section class="card" aria-label=${t("決めごと")}>
    <div class="card-h"><span class="h2">${t("決めごと")}</span><span class="meta">${t("作品で共通")}</span></div>
    <form class="form" @submit=${saveWork}>
      ${fieldsHtml(WORK, w)}
      <span class="sub-h">${t("ページの寸法")}</span>
      ${fieldsHtml(SPEC, w.page_spec || {}, "spec.")}
      <div class="full acts"><button class="btn primary" ?disabled=${S.busy}>${icon("save")}${t("保存")}</button>
        ${w.page_spec ? nothing : html`<span class="meta">${t("ページの寸法が無いと、取り込みと書き出しができません")}</span>`}</div>
    </form></section>`;
}

// ---------------------------------------------------------------- 入稿の設定（name_structure/print_settings.py）
const MODES3 = ["bilevel", "grayscale", "color"];
const KINDS4 = ["cover", "color_page", "body", "blank"];
const PRINT = [
  { key: "file_code", label: t("略号"), hint: t("ファイル名の先頭（英数字・_・-）") },
  { key: "color_mode", label: t("色の種類の既定"), type: "select", options: COLOR_MODE },
  ...MODES3.map((m) => ({ key: `dpi_by_color_mode.${m}`, label: t("解像度（{{mode}}）", { mode: COLOR_MODE[m] }), type: "number", step: 1, hint: "dpi" })),
  { key: "safe_area.top_mm", label: t("安全線（天）"), type: "number", hint: "mm" },
  { key: "safe_area.bottom_mm", label: t("安全線（地）"), type: "number", hint: "mm" },
  { key: "safe_area.gutter_mm", label: t("安全線（ノド）"), type: "number", hint: "mm" },
  { key: "safe_area.outer_mm", label: t("安全線（小口）"), type: "number", hint: "mm" },
  { key: "page_count_multiple", label: t("ページ数のルール"), type: "select", numeric: true, options: { 4: t("4の倍数"), 8: t("8の倍数") }, hint: t("ルールが無い入稿先は空のまま") },
  { key: "page_count_scope", label: t("ページ数を数える範囲"), type: "select", options: { episode: t("話"), volume: t("巻") } },
];
const BILEVEL = [
  { key: "threshold", label: t("閾値"), type: "number", step: 1, hint: t("1〜255。これより暗いピクセルを黒にする") },
  { key: "image_screen.lines_per_inch", label: t("網点の線数"), type: "number" },
  { key: "image_screen.angle_deg", label: t("網点の角度"), type: "number", hint: t("度") },
  { key: "image_screen.dot_shape", label: t("網点の形"), type: "select", options: { round: t("丸"), line: t("線"), square: t("四角") } },
  { key: "pdf_codec", label: t("PDF の符号化"), type: "select", options: { flate: "Flate", ccitt_g4: "CCITT G4" } },
];
const NOMBRE_F = [
  { key: "font_family", label: t("書体") },
  { key: "font_size_pt", label: t("大きさ"), type: "number", hint: "pt" },
  { key: "hidden_font_size_pt", label: t("隠しの大きさ"), type: "number", hint: "pt" },
  { key: "color", label: t("色"), placeholder: "#000000" },   // 色の決め打ちを許す：入力の形の例として見せる文字
  { key: "start_number", label: t("始まりの番号"), type: "number", step: 1 },
  { key: "numbering_scope", label: t("数える範囲"), type: "select", options: { episode: t("話ごと"), volume: t("巻を通す") } },
  { key: "position.vertical", label: t("位置（上下）"), type: "select", options: { top: t("上"), bottom: t("下") } },
  { key: "position.horizontal", label: t("位置（横）"), type: "select", options: { outer: t("小口側"), center: t("真ん中") } },
  { key: "position.edge_mm", label: t("上下の端から"), type: "number", hint: "mm" },
  { key: "position.side_mm", label: t("小口の端から"), type: "number", hint: "mm" },
  { key: "hidden_position.bottom_mm", label: t("隠し：下の端から"), type: "number", hint: "mm" },
  { key: "hidden_position.gutter_mm", label: t("隠し：ノドの端から"), type: "number", hint: "mm" },
  ...KINDS4.map((k) => ({ key: `display_by_kind.${k}`, label: t("出し方（{{kind}}）", { kind: PAGE_KIND[k] }), type: "select", options: NOMBRE })),
];
const TYPESET = [
  { key: "line_spacing_ratio", label: t("行間"), type: "number", hint: t("文字の大きさとの比") },
  { key: "line_break", label: t("自動の改行"), type: "select", options: { none: t("しない"), character: t("字の間で"), phrase: t("文節で") } },
  { key: "tate_chu_yoko_max_digits", label: t("縦中横の桁数"), type: "number", step: 1, hint: t("0 は縦中横にしない") },
  { key: "tate_chu_yoko_marks", label: t("!? を縦中横に"), type: "bool" },
  { key: "align", label: t("揃え"), type: "select", options: { start: t("天・左"), center: t("真ん中") } },
];
function savePrint(e) {
  e.preventDefault();
  const f = e.target;
  const print = readFields(f, PRINT, "print.");
  if (print) print.bilevel = readFields(f, BILEVEL, "bilevel.");
  const prefs = { ...(S.work.work.preferences || {}), print, nombre: readFields(f, NOMBRE_F, "nombre."),
                  typesetting: readFields(f, TYPESET, "typeset.") };
  run(t("入稿の設定を保存できませんでした"), async () => { await op(S.workId, { type: "set_work_settings", preferences: prefs }); toast(t("入稿の設定を保存しました")); });
}
// 組ごとに畳む。決めてある組には「決めた」、無い組には「決まっていない」を出す
const group = (title, value, body) => html`<details class="more full" ?open=${!value}>
  <summary>${icon("chevron-right")}${title}<span class="flag ${value ? "mut" : "warn"}">${value ? t("決めた") : t("決まっていない")}</span></summary>
  <div class="form">${body}</div></details>`;
function printCard() {
  const p = S.work.work.preferences || {};
  return html`<section class="card" aria-label=${t("入稿の設定")}>
    <div class="card-h"><span class="h2">${t("入稿の設定")}</span><span class="meta">${t("値は入稿先の規定から入れます。空の所は「決まっていない」として書き出しの前の確かめで止まります")}</span></div>
    <form class="form" @submit=${savePrint}>
      ${group(t("色と解像度・安全線・ページ数"), p.print, fieldsHtml(PRINT, p.print, "print."))}
      ${group(t("2階調の作り方（白黒2階調のページがあるとき）"), (p.print || {}).bilevel, fieldsHtml(BILEVEL, (p.print || {}).bilevel, "bilevel."))}
      ${group(t("ノンブル"), p.nombre, fieldsHtml(NOMBRE_F, p.nombre, "nombre."))}
      ${group(t("写植の組版の標準"), p.typesetting, fieldsHtml(TYPESET, p.typesetting, "typeset."))}
      <div class="full acts"><button class="btn primary" ?disabled=${S.busy}>${icon("save")}${t("保存")}</button>
        <a class="btn ghost sm" href=${screenHref("export")}>${icon("download")}${t("書き出しで確かめる")}</a></div>
    </form></section>`;
}

// ---------------------------------------------------------------- AIの関与
function setMode(task, mode) {
  run(t("AIの関与を変えられませんでした"), async () => { await op(S.workId, { type: "set_ai_involvement", task, mode: mode || null }); });
}
function aiCard() {
  return html`<section class="card" aria-label=${t("AIの関与")}>
    <div class="card-h"><span class="h2">${t("作業ごとのAIの関与")}</span></div>
    <div class="form">${S.ai.map((a) => html`
      <label class="k" for="ai-${a.task}">${a.title}</label>
      <div class="v"><select class="field" id="ai-${a.task}" @change=${(e) => setMode(a.task, e.target.value)} ?disabled=${S.busy}>
        <option value="" ?selected=${!a.chosen}>${t("設計の既定（{{mode}}）", { mode: MODE[a.mode] })}</option>
        ${Object.entries(MODE).map(([k, l]) => html`<option value=${k} ?selected=${a.chosen && a.mode === k}>${l}</option>`)}</select></div>`)}
    </div>
    <span class="meta">${t("工程ごとに止める所（毎回・外れた時・止めない）と、作り直しの回数・候補の数・予算は、サーバーにまだ持つ所が無いので出していません")}</span>
  </section>`;
}

function draw() {
  if (!S.work) { render(emptyNote(S.why || t("作品を選んでください"), S.why ? "need" : ""), main); return; }
  render(html`<div class="col">${planCard()}${printCard()}</div><div class="col">${workCard()}${aiCard()}</div>`, main);
}

await startShell({ screen: "plan", onWork: loadWork });
